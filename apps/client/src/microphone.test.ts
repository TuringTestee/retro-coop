import test from 'node:test';
import assert from 'node:assert/strict';
import {Microphone,type MicrophoneState} from './microphone.ts';
function fixture(){
 let state:MicrophoneState|undefined;
 const pending:Array<(stream:MediaStream)=>void>=[],sent:Array<MediaStreamTrack|null>=[];
 const microphone=new Microphone(()=>new Promise(resolve=>pending.push(resolve)),value=>{state=value;});
 microphone.endpoint({replaceTrack:async track=>{sent.push(track);}});
 function stream(){const track=Object.assign(new EventTarget(),{enabled:true,stopped:false,stop(){this.stopped=true;}});return {track,stream:{getTracks:()=>[track],getAudioTracks:()=>[track]} as unknown as MediaStream};}
 return {microphone,pending,sent,stream,state:()=>state!};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
test('late permission grant after leaving stops capture and cannot attach to replacement peer',async()=>{
 const f=fixture(),operation=f.microphone.enable();await tick();f.microphone.endpoint();const media=f.stream();f.pending[0](media.stream);await operation;
 assert.equal(media.track.stopped,true);assert.equal(f.sent.some(Boolean),false);assert.equal(f.state().phase,'off');
});
test('blur during permission request stays muted; push-to-talk release and device end stop transmission',async()=>{
 const f=fixture(),operation=f.microphone.enable();await tick();f.microphone.blur();const media=f.stream();f.pending[0](media.stream);await operation;
 assert.equal(media.track.enabled,false);f.microphone.mute(false);assert.equal(media.track.enabled,true);
 f.microphone.mode('push');assert.equal(media.track.enabled,false);f.microphone.hold(true);assert.equal(media.track.enabled,true);
 f.microphone.blur();f.microphone.hold(true);assert.equal(media.track.enabled,false);
 media.track.dispatchEvent(new Event('ended'));assert.equal(media.track.stopped,true);assert.equal(f.state().phase,'error');
});
test('switching devices stops the old capture and requires deliberate unmute',async()=>{
 const f=fixture();let operation=f.microphone.enable();await tick();const first=f.stream();f.pending[0](first.stream);await operation;
 operation=f.microphone.enable('replacement',false);assert.equal(first.track.stopped,true);await tick();const next=f.stream();f.pending[1](next.stream);await operation;
 assert.equal(next.track.enabled,false);assert.equal(f.state().device,'replacement');f.microphone.mute(false);assert.equal(next.track.enabled,true);
 f.microphone.disable();assert.equal(next.track.stopped,true);await tick();assert.equal(f.sent.at(-1),null);
});
test('permission denial preserves a useful retry state without touching gameplay',async()=>{
 let state:MicrophoneState|undefined;const microphone=new Microphone(async()=>{throw new DOMException('denied','NotAllowedError');},value=>{state=value;});
 microphone.endpoint({replaceTrack:async()=>{}});await microphone.enable();assert.equal(state!.phase,'error');assert.match(state!.error!,/Text chat still works/);assert.equal(state!.transmitting,false);
});

test('leaving before queued setup begins never asks for microphone permission',async()=>{
 const f=fixture(),operation=f.microphone.enable();f.microphone.endpoint();await operation;
 assert.equal(f.pending.length,0);assert.equal(f.state().phase,'off');
});
