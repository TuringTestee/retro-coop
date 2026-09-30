export type MicrophoneState = {
 phase:'off'|'requesting'|'ready'|'error'; mode:'open'|'push'; muted:boolean;
 transmitting:boolean; device:string; error?:string; connectionFailure?:boolean;
};
type Sender = Pick<RTCRtpSender,'replaceTrack'>;
type Capture = (constraints:MediaStreamConstraints)=>Promise<MediaStream>;
/** One explicit capture fans out to independently owned room peer senders. */
export class Microphone {
 private senders=new Map<string,{sender:Sender;serial:Promise<void>}>();
 private stream?:MediaStream;
 private generation=0;
 private held=false;
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
 private replace(binding:{sender:Sender;serial:Promise<void>},track:MediaStreamTrack|null,generation:number){
  const operation=binding.serial.then(async()=>{if(this.generation===generation && [...this.senders.values()].includes(binding))await binding.sender.replaceTrack(track);});
  binding.serial=operation.catch(()=>{});return operation;
 }
 async bind(id:string,sender:Sender){
  const existing=this.senders.get(id);
  if(existing?.sender===sender){await this.replace(existing,this.stream?.getAudioTracks()[0]??null,this.generation);return;}
  if(!this.senders.has(id)&&this.senders.size>=4)throw Error('Voice supports at most four remote peers.');
  this.unbind(id);const binding={sender,serial:Promise.resolve()};this.senders.set(id,binding);
  await this.replace(binding,this.stream?.getAudioTracks()[0]??null,this.generation);
 }
 unbind(id:string){
  const binding=this.senders.get(id);if(!binding)return;this.senders.delete(id);
  // Finish any already-dispatched replace before detaching this old sender.
  void binding.serial.then(()=>binding.sender.replaceTrack(null)).catch(()=>{});
 }
 close(){this.disable();for(const id of this.senders.keys())this.unbind(id);}
 private async replaceAll(track:MediaStreamTrack|null,generation:number){
  const bindings=[...this.senders.values()];
  const results=await Promise.allSettled(bindings.map(binding=>this.replace(binding,track,generation)));
  const failed=results.some((result,index)=>result.status==='rejected'&&[...this.senders.values()].includes(bindings[index]));
  if(this.generation===generation&&failed)this.publish({error:'A peer microphone connection failed. Retry that connection.',connectionFailure:true});
  return !failed;
 }
 async retryConnection(){if(this.state.phase!=='ready'||!this.stream||!this.state.connectionFailure)return;const generation=this.generation;if(await this.replaceAll(this.stream.getAudioTracks()[0],generation)&&this.generation===generation)this.publish({error:undefined,connectionFailure:false});}
 async enable(device=this.state.device,unmute=true){
  if(!this.senders.size){this.publish({phase:'error',error:'Connect to another participant before enabling your microphone.'});return;}
  const generation=++this.generation;this.stopTracks();
  this.publish({phase:'requesting',device,muted:!unmute,error:undefined,connectionFailure:false});
  try{
   await this.replaceAll(null,generation);
   if(this.generation!==generation)return;
   const stream=await this.capture({audio:{echoCancellation:true,noiseSuppression:true,...(device==='default'?{}:{deviceId:{exact:device}})},video:false});
   stream.getTracks().forEach(track=>{track.enabled=false;});
   if(this.generation!==generation){stream.getTracks().forEach(track=>track.stop());return;}
   this.stream=stream;const track=stream.getAudioTracks()[0];
   if(!track)throw Error('The selected device did not provide microphone audio.');
   track.addEventListener('ended',()=>{if(this.generation===generation)this.unavailable('Microphone disconnected. Choose a device and try again.');});
   await this.replaceAll(track,generation);
   if(this.generation!==generation)return;
   this.publish({phase:'ready'});
  }catch(error){
   if(this.generation!==generation)return;
   const name=error instanceof Error?error.name:'';
   this.unavailable(name==='NotAllowedError'?'Microphone access was denied. Text chat still works.':name==='NotFoundError'||name==='OverconstrainedError'?'Microphone unavailable. Choose another device and try again.':'Voice could not start. Retry without restarting your game.');
  }
 }
 private unavailable(error:string){this.disable();this.publish({phase:'error',error,connectionFailure:false});}
 disable(){const generation=++this.generation;this.stopTracks();this.publish({phase:'off',muted:true,error:undefined,connectionFailure:false});void this.replaceAll(null,generation);}
 mute(muted:boolean){this.held=false;this.publish({muted});}
 // Focus releases momentary input; only an explicit action changes microphone mute.
 blur(){this.hold(false);}
 selectDevice(device:string){this.publish({device});}
 mode(mode:'open'|'push'){this.held=false;this.publish({mode});}
 hold(held:boolean){if(this.held!==held){this.held=held;this.publish();}}
}
