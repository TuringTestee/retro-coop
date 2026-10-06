import test from 'node:test';
import assert from 'node:assert/strict';
import {VoiceSession} from './voice.ts';
import {defaults} from './controls.ts';
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function environment(){
 const tracks:({enabled:boolean;stopped:boolean}&EventTarget)[]=[],audios:AudioMock[]=[];let captures=0;
 class AudioMock{srcObject:unknown;muted=false;volume=1;paused=false;plays=0;playResult?:()=>Promise<void>;constructor(){audios.push(this);}pause(){this.paused=true;}async play(){this.plays++;await this.playResult?.();}}
 class Stream{tracks:unknown[];constructor(tracks:unknown[]){this.tracks=tracks;}getTracks(){return this.tracks;}getAudioTracks(){return this.tracks;}}
 const win=new EventTarget(),doc=Object.assign(new EventTarget(),{hidden:false,activeElement:null,hasFocus:()=>false});
 const media=Object.assign(new EventTarget(),{enumerateDevices:async()=>[],getUserMedia:async()=>{captures++;const track=Object.assign(new EventTarget(),{enabled:true,stopped:false,stop(){this.stopped=true;}});tracks.push(track);return new Stream([track]);}});
 const globals={Audio:AudioMock,MediaStream:Stream,window:win,document:doc,navigator:{mediaDevices:media,getGamepads:()=>[]},requestAnimationFrame:()=>1,cancelAnimationFrame:()=>{}};
 const saved=new Map<string,PropertyDescriptor|undefined>();for(const [key,value] of Object.entries(globals)){saved.set(key,Object.getOwnPropertyDescriptor(globalThis,key));Object.defineProperty(globalThis,key,{configurable:true,value});}
 return {tracks,audios,win,doc,media,captures:()=>captures,restore(){for(const [key,descriptor] of saved){if(descriptor)Object.defineProperty(globalThis,key,descriptor);else Reflect.deleteProperty(globalThis,key);}}};
}
function connection(){
 const sent:(MediaStreamTrack|null)[]=[],target=new EventTarget(),sender={replaceTrack:async(track:MediaStreamTrack|null)=>{sent.push(track);}},transceiver={sender,receiver:{track:{kind:'audio'}},direction:'sendrecv',currentDirection:'sendrecv'};
 const pc=Object.assign(target,{addTransceiver:()=>transceiver,getTransceivers:()=>[transceiver]}) as unknown as RTCPeerConnection;
 return {pc,sent,track(){target.dispatchEvent(Object.assign(new Event('track'),{track:{kind:'audio'}}));}};
}
test('voice mesh owns four independent audio peers with one focus-independent capture',async()=>{
 const env=environment(),voice=new VoiceSession(()=>{});
 try{
  const peers=Array.from({length:4},(_,i)=>({adapter:voice.forPeer(String(i)),connection:connection()}));
  for(const p of peers){p.adapter.prepare(p.connection.pc,true);p.adapter.connected();p.connection.track();}
  await tick();await voice.enable();assert.equal(env.captures(),1);assert.equal(env.audios.length,4);
  for(const p of peers)assert.equal(p.connection.sent.at(-1),env.tracks[0]);
  env.win.dispatchEvent(new Event('blur'));env.doc.hidden=true;env.doc.dispatchEvent(new Event('visibilitychange'));assert.equal(env.tracks[0].enabled,true);
  voice.remoteMute(true);voice.volume(.25);for(const audio of env.audios){assert.equal(audio.muted,true);assert.equal(audio.volume,.25);}
  voice.microphone.mute(true);peers[0].adapter.close();assert.equal(voice.current().connected,true);assert.equal(voice.current().listening,true);assert.equal(env.tracks[0].stopped,false);assert.equal(env.audios[0].srcObject,null);
  const replacement=connection();peers[0].adapter.prepare(replacement.pc,true);peers[0].adapter.connected();replacement.track();await tick();
  assert.equal(replacement.sent.at(-1),env.tracks[0]);assert.equal(env.tracks[0].enabled,false);assert.equal(env.captures(),1);assert.equal(env.audios[4].muted,true);assert.equal(env.audios[4].volume,.25);
  voice.microphone.mute(false);env.win.dispatchEvent(new Event('blur'));assert.equal(env.tracks[0].enabled,true);
  assert.throws(()=>voice.forPeer('fifth').prepare(connection().pc,true),/four/);
  voice.close();await tick();assert.equal(env.tracks[0].stopped,true);assert.equal(voice.current().connected,false);assert.equal(voice.current().listening,false);for(const audio of env.audios)assert.equal(audio.srcObject,null);
 }finally{voice.dispose();env.restore();}
});
test('answerer binding and stale peer close/track events cannot disturb replacement or other peers',async()=>{
 const env=environment(),voice=new VoiceSession(()=>{});
 try{
  const first=voice.forPeer('pair'),old=connection();first.prepare(old.pc,false);assert.equal(old.sent.length,0);first.answer(old.pc);first.connected();
  const other=voice.forPeer('other'),stable=connection();other.prepare(stable.pc,true);other.connected();await tick();await voice.enable();
  const replacement=voice.forPeer('pair'),fresh=connection();replacement.prepare(fresh.pc,false);replacement.answer(fresh.pc);replacement.connected();fresh.track();await tick();
  first.close();first.answer(old.pc);old.track();await tick();
  assert.equal(fresh.sent.at(-1),env.tracks[0]);assert.equal(stable.sent.at(-1),env.tracks[0]);assert.equal(env.tracks[0].stopped,false);assert.equal(env.tracks[0].enabled,true);assert.equal(env.audios[0].srcObject,null);assert.notEqual(env.audios[2].srcObject,null);assert.equal(voice.current().connected,true);
 }finally{voice.dispose();env.restore();}
});

test('a late playback failure cannot replace a newer successful retry',async()=>{
 const env=environment(),voice=new VoiceSession(()=>{});
 try{
  const peer=voice.forPeer('pair'),pc=connection();peer.prepare(pc.pc,true);peer.connected();pc.track();await voice.enable();
  let reject!:(error:Error)=>void;
  env.audios[0].playResult=()=>new Promise<void>((_resolve,no)=>{reject=no;});
  const stale=voice.play();await tick();env.audios[0].playResult=undefined;await voice.play();
  reject(Error('old playback failed'));await stale;
  assert.equal(voice.current().playbackError,undefined);
  env.audios[0].playResult=()=>new Promise<void>((_resolve,no)=>{reject=no;});
  const replaced=voice.play();await tick();const fresh=connection();peer.prepare(fresh.pc,true);peer.connected();fresh.track();await tick();
  reject(Error('replaced playback failed'));await replaced;assert.equal(voice.current().playbackError,undefined);
  env.audios.at(-1)!.playResult=()=>new Promise<void>((_resolve,no)=>{reject=no;});
  const departed=voice.play();await tick();voice.close();reject(Error('departed playback failed'));await departed;
  assert.equal(voice.current().playbackError,undefined);assert.equal(voice.current().listening,false);
 }finally{voice.dispose();env.restore();}
});
test('a late device-list failure cannot replace a newer successful refresh',async()=>{
 const env=environment(),voice=new VoiceSession(()=>{});
 try{
  let reject!:(error:Error)=>void;
  env.media.enumerateDevices=()=>new Promise((_resolve,no)=>{reject=no;});
  const stale=voice.listDevices();env.media.enumerateDevices=async()=>[];await voice.listDevices();
  reject(Error('old enumeration failed'));await stale;
  assert.equal(voice.current().deviceError,undefined);
  env.media.enumerateDevices=()=>new Promise((_resolve,no)=>{reject=no;});
  const departed=voice.listDevices();voice.close();reject(Error('departed enumeration failed'));await departed;
  assert.equal(voice.current().deviceError,undefined);
 }finally{voice.dispose();env.restore();}
});

test('missing preferred gamepad preserves keyboard and pointer push-to-talk without muting open voice',async()=>{
 const {defaults}=await import('./controls.ts'),env=environment(),voice=new VoiceSession(()=>{});
 let connected=false,held=false;
 Object.defineProperty(navigator,'getGamepads',{configurable:true,value:()=>[connected?{index:0,id:'Preferred pad',connected:true,buttons:Array.from({length:11},(_,i)=>({pressed:i===10&&held})),axes:[]}:null]});
 Object.defineProperty(env.doc,'hasFocus',{value:()=>true});
 try{
  const peer=voice.forPeer('p2'),channel=connection();peer.prepare(channel.pc,true);peer.connected();await tick();
  await voice.enable();voice.microphone.mode('push');const controls=defaults();controls.device={index:0,id:'Preferred pad'};voice.configureControls(controls);
  const input=(voice as unknown as {input:()=>void}).input;
  const key=(type:string)=>env.win.dispatchEvent(Object.assign(new Event(type),{code:'KeyV',repeat:false}));
  key('keydown');input();assert.equal(voice.current().microphone.transmitting,true);
  key('keyup');input();assert.equal(voice.current().microphone.transmitting,false);
  voice.hold(true);input();assert.equal(voice.current().microphone.transmitting,true);voice.hold(false);
  connected=true;held=true;input();assert.equal(voice.current().microphone.transmitting,false,'return hold must not start speaking');
  held=false;input();held=true;input();assert.equal(voice.current().microphone.transmitting,true);
  connected=false;input();assert.equal(voice.current().microphone.transmitting,false);assert.equal(voice.current().microphone.muted,false);
  voice.microphone.mode('open');input();assert.equal(voice.current().microphone.transmitting,true,'optional pad loss cannot mute open speech');
 }finally{voice.dispose();env.restore();}
});
test('capture dialogs release push-to-talk and require a fresh pad press after dismissal',async()=>{
 const env=environment();let animation!:FrameRequestCallback,dialog=false;
 const pad={index:0,id:'Test pad',connected:true,buttons:Array.from({length:11},()=>({pressed:false})),axes:[]};
 Object.defineProperty(globalThis,'requestAnimationFrame',{configurable:true,value:(callback:FrameRequestCallback)=>{animation=callback;return 1;}});
 Object.defineProperty(env.doc,'activeElement',{configurable:true,get:()=>dialog?{closest:()=>({})}:null});Object.defineProperty(env.doc,'hasFocus',{configurable:true,value:()=>true});
 navigator.getGamepads=()=>[pad as unknown as Gamepad];
 const voice=new VoiceSession(()=>{}),sample=()=>animation(0);
 try{
  const peer=voice.forPeer('pair'),pc=connection();peer.prepare(pc.pc,true);peer.connected();await tick();await voice.enable();
  voice.configureControls({...defaults(),device:{index:0,id:pad.id}});voice.microphone.mode('push');
  sample();pad.buttons[10].pressed=true;sample();assert.equal(voice.current().microphone.transmitting,true);
  dialog=true;sample();assert.equal(voice.current().microphone.transmitting,false);assert.equal(env.tracks[0].enabled,false);
  dialog=false;sample();assert.equal(voice.current().microphone.transmitting,false);
  pad.buttons[10].pressed=false;sample();pad.buttons[10].pressed=true;sample();assert.equal(voice.current().microphone.transmitting,true);
  voice.microphone.mode('open');dialog=true;sample();assert.equal(voice.current().microphone.transmitting,true);assert.equal(env.tracks[0].enabled,true);
 }finally{voice.dispose();env.restore();}
});
