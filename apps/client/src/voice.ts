import {defaults,GamepadInput,modifiedKey,type Controls} from './controls.ts';
import {Microphone,type MicrophoneState} from './microphone.ts';
export type VoiceState={microphone:MicrophoneState;connected:boolean;listening:boolean;remoteMuted:boolean;volume:number;devices:{id:string;label:string}[];deviceError?:string;playbackError?:string;connectionError?:string};
type VoicePeer={pc:RTCPeerConnection;audio:HTMLAudioElement;connected:boolean;binding?:number;playback?:number;connectionError?:string;playbackError?:string};
/** One explicit microphone capture shares up to four authenticated peer transports. */
export class VoiceSession {
 readonly microphone:Microphone;
 private peers=new Map<string,VoicePeer>();
 private disposed=false;
 private deviceRequest=0;
 private controls:Controls=defaults();private keys=new Set<string>();private animation=0;private gamepadInput=new GamepadInput();private pointerHeld=false;
 private state:VoiceState={microphone:{phase:'off',mode:'open',muted:true,transmitting:false,device:'default'},connected:false,listening:false,remoteMuted:false,volume:1,devices:[]};
 private update:(state:VoiceState)=>void;
 constructor(update:(state:VoiceState)=>void){
  this.update=update;this.microphone=new Microphone(constraints=>navigator.mediaDevices.getUserMedia(constraints),microphone=>this.publish({microphone}));
  window.addEventListener('gamepadconnected',this.deviceChanged);window.addEventListener('gamepaddisconnected',this.deviceChanged);
  window.addEventListener('blur',this.blur);document.addEventListener('visibilitychange',this.visibility);
  navigator.mediaDevices?.addEventListener('devicechange',this.devicesChanged);
  window.addEventListener('keydown',this.down);window.addEventListener('keyup',this.up);this.animation=requestAnimationFrame(this.input);
 }
 current(){return this.state;}
 private publish(patch:Partial<VoiceState>){if(!this.disposed){this.state={...this.state,...patch};this.update(this.state);}}
 private deviceChanged=(event:GamepadEvent)=>{if(this.controls.device?.index===event.gamepad.index&&this.controls.device.id===event.gamepad.id)this.gamepadInput.release(this.controls.device);};
 private blur=()=>{this.keys.clear();this.gamepadInput.release(this.controls.device);this.pointerHeld=false;this.microphone.blur();};
 private editable(){const element=document.activeElement;return !!element?.closest('input,textarea,select,[contenteditable="true"],dialog,[role="dialog"],[role="alertdialog"]');}
 private down=(event:KeyboardEvent)=>{if(this.state.microphone.phase==='ready' && this.state.microphone.mode==='push' && !this.state.microphone.muted && !event.repeat && !modifiedKey(event) && !this.editable() && this.controls.keyboard.pushToTalk.includes(event.code)){event.preventDefault();this.keys.add(event.code);}};
 private up=(event:KeyboardEvent)=>{this.keys.delete(event.code);};
 private input=()=>{
  this.animation=requestAnimationFrame(this.input);
  if(this.editable()){this.keys.clear();this.gamepadInput.release(this.controls.device);this.pointerHeld=false;this.microphone.hold(false);return;}
  const {pressed}=this.gamepadInput.sample(this.controls.device);
  const held=this.controls.keyboard.pushToTalk.some(binding=>this.keys.has(binding)) || this.controls.gamepad.pushToTalk.some(binding=>pressed.has(binding));
  this.microphone.hold(document.hasFocus() && (this.pointerHeld || !this.editable() && held));
 };
 configureControls(controls:Controls){this.controls=controls;this.keys.clear();this.gamepadInput.release(this.controls.device);this.pointerHeld=false;this.microphone.hold(false);}
 hold(held:boolean){this.pointerHeld=held;this.microphone.hold(held);}

 private visibility=()=>{if(document.hidden)this.blur();};
 private devicesChanged=()=>{void this.listDevices();};
 async listDevices(){
  const request=++this.deviceRequest;
  try{const devices=await navigator.mediaDevices.enumerateDevices();if(request!==this.deviceRequest)return;this.publish({devices:devices.filter(device=>device.kind==='audioinput' && device.deviceId && device.deviceId!=='default').map((device,index)=>({id:device.deviceId,label:device.label||`Microphone ${index+1}`})),deviceError:undefined});}
  catch{if(request===this.deviceRequest)this.publish({deviceError:'Microphone devices could not be listed. Retry or use the default device.'});}
 }
 private summarize(){this.publish({connected:[...this.peers.values()].some(peer=>peer.connected),connectionError:[...this.peers.values()].find(peer=>peer.connectionError)?.connectionError,playbackError:[...this.peers.values()].find(peer=>peer.playbackError)?.playbackError});}
 private closePeer(id:string,peer:VoicePeer){
  if(this.peers.get(id)!==peer)return;
  this.peers.delete(id);this.microphone.unbind(id);peer.audio.pause();peer.audio.srcObject=null;this.summarize();
 }
 private bind(id:string,peer:VoicePeer,sender:RTCRtpSender){
  const binding=peer.binding=(peer.binding??0)+1;
  void this.microphone.bind(id,sender).then(()=>{if(this.peers.get(id)===peer&&peer.binding===binding){peer.connectionError=undefined;this.summarize();}}).catch(()=>{if(this.peers.get(id)===peer&&peer.binding===binding){peer.connectionError='Voice negotiation is unavailable for a participant. Text and gameplay can still connect.';this.summarize();}});
 }
 forPeer(id:string){
  let peer:VoicePeer|undefined;
  return {
   prepare:(pc:RTCPeerConnection,offerer:boolean)=>{
    if(this.disposed)return;
    if(peer)this.closePeer(id,peer);
    const old=this.peers.get(id);if(old)this.closePeer(id,old);
    if(this.peers.size>=4)throw Error('Voice supports at most four remote peers.');
    const current:VoicePeer={pc,audio:new Audio(),connected:false};peer=current;this.peers.set(id,current);
    current.audio.muted=this.state.remoteMuted;current.audio.volume=this.state.volume;
    pc.addEventListener('track',event=>{if(this.peers.get(id)===current&&event.track.kind==='audio'){current.audio.srcObject=new MediaStream([event.track]);if(this.state.listening)void this.playPeer(id,current);}});
    try{if(offerer)this.bind(id,current,pc.addTransceiver('audio',{direction:'sendrecv'}).sender);}
    catch{current.connectionError='Voice negotiation is unavailable for a participant. Text and gameplay can still connect.';this.summarize();}
   },
   answer:(pc:RTCPeerConnection)=>{
    if(!peer||peer.pc!==pc||this.peers.get(id)!==peer)return;
    try{const audio=pc.getTransceivers().find(item=>item.receiver.track.kind==='audio');if(!audio)throw Error('Audio was not offered');audio.direction='sendrecv';this.bind(id,peer,audio.sender);}
    catch{peer.connectionError='Voice negotiation is unavailable for a participant. Text and gameplay can still connect.';this.summarize();}
   },
   connected:()=>{if(peer&&this.peers.get(id)===peer){peer.connected=true;this.summarize();}},
   close:()=>{if(peer)this.closePeer(id,peer);},
  };
 }
 retryBinding(){
  for(const [id,peer] of this.peers){
   const audio=peer.pc.getTransceivers().find(item=>item.receiver.track.kind==='audio'&&item.currentDirection&&item.currentDirection!=='inactive');
   if(!audio){peer.connectionError='Voice was not negotiated with a participant. Text and gameplay remain available.';continue;}
   this.bind(id,peer,audio.sender);
  }
  this.summarize();
 }
 close(){this.deviceRequest++;for(const [id,peer] of this.peers)this.closePeer(id,peer);this.blur();this.microphone.close();this.publish({connected:false,listening:false,connectionError:undefined,playbackError:undefined});}
 async enable(){
  if(!this.state.connected)return;
  this.publish({listening:true});void this.play();await this.microphone.enable();await this.listDevices();
 }
 async device(id:string){if(this.state.microphone.phase==='ready')await this.microphone.enable(id,false);else this.microphone.selectDevice(id);await this.listDevices();}
 private async playPeer(id:string,peer:VoicePeer){
  if(!this.state.listening||this.peers.get(id)!==peer)return;
  peer.audio.muted=this.state.remoteMuted;peer.audio.volume=this.state.volume;
  if(!peer.audio.srcObject)return;
  const playback=peer.playback=(peer.playback??0)+1;
  try{await peer.audio.play();if(this.peers.get(id)===peer&&peer.playback===playback&&this.state.listening){peer.playbackError=undefined;this.summarize();}}
  catch{if(this.peers.get(id)===peer&&peer.playback===playback&&this.state.listening){peer.playbackError='Remote voice playback was blocked.';this.summarize();}}
 }
 async play(){await Promise.all([...this.peers].map(([id,peer])=>this.playPeer(id,peer)));}
 retrySound(){this.publish({listening:true});void this.play();}
 remoteMute(remoteMuted:boolean){for(const peer of this.peers.values())peer.audio.muted=remoteMuted;this.publish({remoteMuted});if(!remoteMuted)void this.play();}
 volume(volume:number){if(!Number.isFinite(volume)||volume<0||volume>1)return;for(const peer of this.peers.values())peer.audio.volume=volume;this.publish({volume});}
 dispose(){window.removeEventListener('gamepadconnected',this.deviceChanged);window.removeEventListener('gamepaddisconnected',this.deviceChanged);this.close();this.disposed=true;window.removeEventListener('blur',this.blur);document.removeEventListener('visibilitychange',this.visibility);navigator.mediaDevices?.removeEventListener('devicechange',this.devicesChanged);window.removeEventListener('keydown',this.down);window.removeEventListener('keyup',this.up);cancelAnimationFrame(this.animation);}
}
