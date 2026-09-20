import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {Rooms} from './rooms.ts';
import type {RoomCommand,RoomEvent,Fingerprint} from '../../../packages/contracts/src/rooms.ts';
const fingerprint:Fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:1,submapper:0,region:'NTSC',bytes:32784}};
function setup(){
 let now=1000;const rooms=new Rooms(()=>now),events:RoomEvent[][]=[[],[]];
 const host=rooms.attach(undefined,e=>events[0].push(e),()=>{}),guest=rooms.attach(undefined,e=>events[1].push(e),()=>{});
 const act=(who:number,c:Record<string,unknown>)=>rooms.handle([host.token,guest.token][who],{...c,requestId:randomUUID()} as Exclude<RoomCommand,{type:'hello'}>);
 const intent=randomUUID();const room=act(0,{type:'create',intent,visibility:'public',fingerprint}).room!;act(0,{type:'confirmCreate',intent});const joined=act(1,{type:'join',invite:room.invite,intent:randomUUID()}).room!;
 const peerEpoch=joined.peer.epoch!;for(const who of [0,1])act(who,{type:'peerAck',epoch:peerEpoch});for(const who of [0,1])act(who,{type:'peerConnected',epoch:peerEpoch});
 const ready=(who:number,extra={})=>act(who,{type:'gameReady',peerEpoch,frame:0,fresh:true,hash:'c'.repeat(64),delay:who===0?3:8,...extra});
 return {rooms,events,act,ready,joined,advance(ms:number){now+=ms;rooms.sweep();}};
}
test('exact file prerequisites and both initial acknowledgements precede established membership',()=>{
 const t=setup();assert.throws(()=>t.ready(1),/game_prerequisites/);t.act(1,{type:'file',fingerprint:{...fingerprint,romSha256:'d'.repeat(64)}});assert.throws(()=>t.ready(1),/game_prerequisites/);
 t.act(1,{type:'file',fingerprint});t.ready(1);assert.ok(t.events[0].some(e=>e.type==='gameInspect'));
 const preparing=t.ready(0).room!;assert.equal(preparing.game?.status,'starting');assert.equal(preparing.game.delay,8);assert.equal(preparing.established,false);assert.equal(preparing.reservationUntil,t.joined.reservationUntil);
 const epoch=preparing.game.epoch;assert.throws(()=>t.act(1,{type:'gameAck',epoch,hash:'d'.repeat(64)}),/stale_game/);
 assert.equal(t.act(0,{type:'gameAck',epoch,hash:'c'.repeat(64)}).room!.established,false);
 const playing=t.act(1,{type:'gameAck',epoch,hash:'c'.repeat(64)}).room!;assert.equal(playing.established,true);assert.equal(playing.reservationUntil,undefined);assert.equal(playing.status,'playing');
 assert.equal(t.act(1,{type:'gamePause',epoch,frame:128,reason:'focus'}).room!.game?.status,'pausing');
 assert.throws(()=>t.act(0,{type:'gamePaused',epoch,frame:127,hash:'c'.repeat(64)}),/stale_game/);
 assert.equal(t.act(0,{type:'gamePaused',epoch,frame:128,hash:'c'.repeat(64)}).room!.game?.status,'pausing');
 assert.equal(t.act(1,{type:'gamePaused',epoch,frame:128,hash:'c'.repeat(64)}).room!.game?.status,'paused');
 t.ready(1,{frame:128,fresh:false});const resumed=t.ready(0,{frame:128,fresh:false}).room!;assert.equal(resumed.game?.status,'resume_ready');
 assert.throws(()=>t.act(1,{type:'gameResume',epoch}),/resume_not_ready/);
 const next=t.act(0,{type:'gameResume',epoch}).room!;assert.equal(next.game?.status,'starting');assert.notEqual(next.game?.epoch,epoch);
 assert.throws(()=>t.act(1,{type:'gameAck',epoch,hash:'c'.repeat(64)}),/stale_game/);
 for(const who of [0,1])t.act(who,{type:'gameAck',epoch:next.game?.epoch,hash:'c'.repeat(64)});
});
test('progressed hosts, timeout, cancellation and changed peers cannot silently start or promote',()=>{
 const t=setup();t.act(1,{type:'file',fingerprint});t.ready(1);const late=t.ready(0,{frame:12,fresh:false}).room!;assert.equal(late.game?.status,'late_join');assert.equal(late.established,false);assert.equal(late.reservationUntil,t.joined.reservationUntil);
 t.ready(1);const ready=t.ready(0).room!;t.events[1].length=0;t.advance(10_000);const failed=t.events[1].filter(e=>e.type==='room').at(-1)!;assert.equal(failed.room.game?.status,'failed');assert.equal(failed.room.reservationUntil,t.joined.reservationUntil);
 assert.throws(()=>t.act(1,{type:'gameAck',epoch:ready.game?.epoch,hash:'c'.repeat(64)}),/stale_game/);
 t.act(1,{type:'leave',intent:t.joined.reservationIntent});assert.throws(()=>t.ready(1),/not_in_room/);
});
