import test from 'node:test';
import assert from 'node:assert/strict';
import {VoiceSession} from './voice.ts';
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function environment(){
 const tracks:({enabled:boolean;stopped:boolean}&EventTarget)[]=[],audios:AudioMock[]=[];let captures=0;
 class AudioMock{srcObject:unknown;muted=false;volume=1;paused=false;plays=0;constructor(){audios.push(this);}pause(){this.paused=true;}async play(){this.plays++;}}
 class Stream{tracks:unknown[];constructor(tracks:unknown[]){this.tracks=tracks;}getTracks(){return this.tracks;}getAudioTracks(){return this.tracks;}}
 const win=new EventTarget(),doc=Object.assign(new EventTarget(),{hidden:false,activeElement:null,hasFocus:()=>false});
 const media=Object.assign(new EventTarget(),{enumerateDevices:async()=>[],getUserMedia:async()=>{captures++;const track=Object.assign(new EventTarget(),{enabled:true,stopped:false,stop(){this.stopped=true;}});tracks.push(track);return new Stream([track]);}});
 const globals={Audio:AudioMock,MediaStream:Stream,window:win,document:doc,navigator:{mediaDevices:media,getGamepads:()=>[]},requestAnimationFrame:()=>1,cancelAnimationFrame:()=>{}};
 const saved=new Map<string,PropertyDescriptor|undefined>();for(const [key,value] of Object.entries(globals)){saved.set(key,Object.getOwnPropertyDescriptor(globalThis,key));Object.defineProperty(globalThis,key,{configurable:true,value});}
 return {tracks,audios,win,doc,captures:()=>captures,restore(){for(const [key,descriptor] of saved){if(descriptor)Object.defineProperty(globalThis,key,descriptor);else Reflect.deleteProperty(globalThis,key);}}};
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
