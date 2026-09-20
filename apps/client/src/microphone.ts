export type MicrophoneState = {
 phase:'off'|'requesting'|'ready'|'error'; mode:'open'|'push'; muted:boolean;
 transmitting:boolean; device:string; error?:string;
};
type Sender = Pick<RTCRtpSender,'replaceTrack'>;
type Capture = (constraints:MediaStreamConstraints)=>Promise<MediaStream>;
/** Capture and transmission have one owner. Transport replacement invalidates all pending capture. */
export class Microphone {
 private sender?:Sender;
 private stream?:MediaStream;
 private generation=0;
 private held=false;
 private serial:Promise<void>=Promise.resolve();
 private state:MicrophoneState={phase:'off',mode:'open',muted:true,transmitting:false,device:'default'};
 private capture:Capture;private update:(state:MicrophoneState)=>void;
 constructor(capture:Capture,update:(state:MicrophoneState)=>void){this.capture=capture;this.update=update;}
 private publish(patch:Partial<MicrophoneState>={}){
  this.state={...this.state,...patch};
  const transmitting=this.state.phase==='ready' && !this.state.muted && (this.state.mode==='open'||this.held);
  this.stream?.getAudioTracks().forEach(track=>{track.enabled=transmitting;});
  this.state={...this.state,transmitting};this.update({...this.state});
 }
 private stopTracks(){this.stream?.getTracks().forEach(track=>track.stop());this.stream=undefined;this.held=false;}
 private replace(track:MediaStreamTrack|null,generation:number){
  const sender=this.sender;
  const operation=this.serial.then(async()=>{if(this.generation===generation && this.sender===sender && sender)await sender.replaceTrack(track);});
  this.serial=operation.catch(()=>{});return operation;
 }
 endpoint(sender?:Sender){
  ++this.generation;this.stopTracks();this.sender=sender;this.serial=Promise.resolve();
  this.publish({phase:'off',muted:true,error:undefined});
 }
 async enable(device=this.state.device,unmute=true){
  if(!this.sender){this.publish({phase:'error',error:'Connect to the other player before enabling your microphone.'});return;}
  const generation=++this.generation;this.stopTracks();
  this.publish({phase:'requesting',device,muted:!unmute,error:undefined});
  try{
   await this.replace(null,generation);
   if(this.generation!==generation)return;
   const stream=await this.capture({audio:{echoCancellation:true,noiseSuppression:true,...(device==='default'?{}:{deviceId:{exact:device}})},video:false});
   stream.getTracks().forEach(track=>{track.enabled=false;});
   if(this.generation!==generation){stream.getTracks().forEach(track=>track.stop());return;}
   this.stream=stream;const track=stream.getAudioTracks()[0];
   if(!track)throw Error('The selected device did not provide microphone audio.');
   track.addEventListener('ended',()=>{if(this.generation===generation)this.unavailable('Microphone disconnected. Choose a device and try again.');});
   await this.replace(track,generation);
   if(this.generation!==generation)return;
   this.publish({phase:'ready'});
  }catch(error){
   if(this.generation!==generation)return;
   const name=error instanceof Error?error.name:'';
   this.unavailable(name==='NotAllowedError'?'Microphone access was denied. Text chat still works.':name==='NotFoundError'||name==='OverconstrainedError'?'Microphone unavailable. Choose another device and try again.':'Voice could not start. Retry without restarting your game.');
  }
 }
 private unavailable(error:string){this.disable();this.publish({phase:'error',error});}
 disable(){const generation=++this.generation;this.stopTracks();this.publish({phase:'off',muted:true,error:undefined});void this.replace(null,generation).catch(()=>{});}
 mute(muted:boolean){this.held=false;this.publish({muted});}
 blur(){this.mute(true);}
 selectDevice(device:string){this.publish({device});}
 mode(mode:'open'|'push'){this.held=false;this.publish({mode});}
 hold(held:boolean){if(this.held!==held){this.held=held;this.publish();}}
}
