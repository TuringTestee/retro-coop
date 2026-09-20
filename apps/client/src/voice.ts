import {defaults,padInputs,type Controls} from './controls.ts';
import {Microphone,type MicrophoneState} from './microphone.ts';
export type VoiceState={microphone:MicrophoneState;connected:boolean;listening:boolean;remoteMuted:boolean;volume:number;devices:{id:string;label:string}[];deviceError?:string;playbackError?:string;connectionError?:string};
/** One audio transceiver shares the authenticated peer transport; capture is always an explicit action. */
export class VoiceSession {
 readonly microphone:Microphone;
 private audio=new Audio();
 private pc?:RTCPeerConnection;
 private disposed=false;
 private controls:Controls=defaults();private keys=new Set<string>();private animation=0;private padArmed=false;private pointerHeld=false;
 private state:VoiceState={microphone:{phase:'off',mode:'open',muted:true,transmitting:false,device:'default'},connected:false,listening:false,remoteMuted:false,volume:1,devices:[]};
 private update:(state:VoiceState)=>void;
 constructor(update:(state:VoiceState)=>void){
  this.update=update;this.microphone=new Microphone(constraints=>navigator.mediaDevices.getUserMedia(constraints),microphone=>this.publish({microphone}));
  window.addEventListener('blur',this.blur);document.addEventListener('visibilitychange',this.visibility);
  navigator.mediaDevices?.addEventListener('devicechange',this.devicesChanged);
  window.addEventListener('keydown',this.down);window.addEventListener('keyup',this.up);this.animation=requestAnimationFrame(this.input);
 }
 current(){return this.state;}
 private publish(patch:Partial<VoiceState>){if(!this.disposed){this.state={...this.state,...patch};this.update(this.state);}}
 private blur=()=>{this.keys.clear();this.padArmed=false;this.pointerHeld=false;this.microphone.blur();};
 private editable(){const element=document.activeElement;return !!element?.closest('input,textarea,select,[contenteditable="true"],dialog');}
 private down=(event:KeyboardEvent)=>{if(this.state.microphone.phase==='ready' && this.state.microphone.mode==='push' && !this.state.microphone.muted && !event.repeat && !event.ctrlKey && !event.metaKey && !event.altKey && !this.editable() && this.controls.keyboard.pushToTalk.includes(event.code)){event.preventDefault();this.keys.add(event.code);}};
 private up=(event:KeyboardEvent)=>{this.keys.delete(event.code);};
 private input=()=>{
  this.animation=requestAnimationFrame(this.input);
  const device=this.controls.device,pad=device?navigator.getGamepads()[device.index]:undefined;
  const available=!device||!!pad&&pad.connected&&pad.id===device.id;
  if(!available){if(this.state.microphone.transmitting)this.blur();return;}
  const held=device?this.controls.gamepad.pushToTalk.some(binding=>padInputs(pad).has(binding)):this.controls.keyboard.pushToTalk.some(binding=>this.keys.has(binding));
  if(!held)this.padArmed=true;
  this.microphone.hold(document.hasFocus() && (this.pointerHeld || !this.editable() && held && this.padArmed));
 };
 configureControls(controls:Controls){this.controls=controls;this.keys.clear();this.padArmed=false;this.pointerHeld=false;this.microphone.hold(false);}
 hold(held:boolean){this.pointerHeld=held;this.microphone.hold(held);}

 private visibility=()=>{if(document.hidden)this.blur();};
 private devicesChanged=()=>{void this.listDevices();};
 async listDevices(){
  try{const devices=await navigator.mediaDevices.enumerateDevices();this.publish({devices:devices.filter(device=>device.kind==='audioinput' && device.deviceId && device.deviceId!=='default').map((device,index)=>({id:device.deviceId,label:device.label||`Microphone ${index+1}`})),deviceError:undefined});}
  catch{this.publish({deviceError:'Microphone devices could not be listed. Retry or use the default device.'});}
 }
 prepare(pc:RTCPeerConnection,role:'host'|'guest'){
  this.close();this.pc=pc;
  pc.addEventListener('track',event=>{if(this.pc===pc && event.track.kind==='audio'){this.audio.srcObject=new MediaStream([event.track]);if(this.state.listening)void this.play();}});
  try{if(role==='host')this.microphone.endpoint(pc.addTransceiver('audio',{direction:'sendrecv'}).sender);}
  catch{this.publish({connectionError:'Voice negotiation is unavailable. Text and gameplay can still connect.'});}
 }
 answer(pc:RTCPeerConnection){
  if(this.pc!==pc)return;
  try{
   const audio=pc.getTransceivers().find(item=>item.receiver.track.kind==='audio');
   if(!audio)throw Error('Audio was not offered');
   audio.direction='sendrecv';this.microphone.endpoint(audio.sender);
  }catch{this.publish({connectionError:'Voice negotiation is unavailable. Text and gameplay can still connect.'});}
 }
 retryBinding(){
  const pc=this.pc;if(!pc)return;
  const audio=pc.getTransceivers().find(item=>item.receiver.track.kind==='audio' && item.currentDirection && item.currentDirection!=='inactive');
  if(!audio){this.publish({connectionError:'Voice was not negotiated on this connection. Text and gameplay remain available.'});return;}
  this.microphone.endpoint(audio.sender);this.publish({connectionError:undefined});
 }
 connected(){this.publish({connected:true});}
 close(){this.pc=undefined;this.microphone.endpoint();this.audio.pause();this.audio.srcObject=null;this.publish({connected:false,listening:false,connectionError:undefined,playbackError:undefined});}
 async enable(){
  if(!this.state.connected||this.state.connectionError)return;
  this.publish({listening:true});void this.play();await this.microphone.enable();await this.listDevices();
 }
 async device(id:string){if(this.state.microphone.phase==='ready')await this.microphone.enable(id,false);else this.microphone.selectDevice(id);await this.listDevices();}
 async play(){
  if(!this.state.listening)return;
  this.audio.muted=this.state.remoteMuted;this.audio.volume=this.state.volume;
  if(!this.audio.srcObject)return;
  const pc=this.pc;
  try{await this.audio.play();if(this.pc===pc && this.state.listening)this.publish({playbackError:undefined});}
  catch{if(this.pc===pc && this.state.listening)this.publish({playbackError:'Remote voice playback was blocked. Enable voice sound to retry.'});}
 }
 retrySound(){this.publish({listening:true});void this.play();}
 remoteMute(remoteMuted:boolean){this.audio.muted=remoteMuted;this.publish({remoteMuted});if(!remoteMuted)void this.play();}
 volume(volume:number){if(!Number.isFinite(volume)||volume<0||volume>1)return;this.audio.volume=volume;this.publish({volume});}
 dispose(){this.close();this.disposed=true;window.removeEventListener('blur',this.blur);document.removeEventListener('visibilitychange',this.visibility);navigator.mediaDevices?.removeEventListener('devicechange',this.devicesChanged);window.removeEventListener('keydown',this.down);window.removeEventListener('keyup',this.up);cancelAnimationFrame(this.animation);}
}
