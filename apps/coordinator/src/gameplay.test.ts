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
 const start=()=>act(0,{type:'startRoom',roomId:room.id,membership:room.chatMembership,fingerprint});
 return {rooms,events,act,ready,start,hostRoom:room,joined,advance(ms:number){now+=ms;rooms.sweep();}};
}
test('exact file prerequisites and both initial acknowledgements precede established membership',()=>{
 const t=setup();assert.throws(()=>t.ready(1),/game_prerequisites/);t.act(1,{type:'file',fingerprint:{...fingerprint,romSha256:'d'.repeat(64)}});assert.throws(()=>t.ready(1),/game_prerequisites/);
 t.act(1,{type:'file',fingerprint});t.ready(1);assert.equal(t.events[0].some(e=>e.type==='gameInspect'),false);
 assert.notEqual(t.ready(0).room!.game?.status,'starting','both ready must not auto-start');
 const preparing=t.start().room!;assert.equal(preparing.game?.status,'starting');assert.equal(preparing.game.delay,8);assert.equal(preparing.established,false);assert.equal(preparing.reservationUntil,t.joined.reservationUntil);
 assert.equal(t.start().room?.game?.epoch,preparing.game.epoch,'repeat Start must not create another timeline');
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
 const t=setup();t.act(1,{type:'file',fingerprint});t.ready(1);t.ready(0,{frame:12,fresh:false});const late=t.start().room!;assert.equal(late.game?.status,'late_join');assert.equal(late.established,false);assert.equal(late.reservationUntil,t.joined.reservationUntil);
 t.ready(1);const ready=t.ready(0).room!;t.events[1].length=0;t.advance(10_000);const failed=t.events[1].filter(e=>e.type==='room').at(-1)!;assert.equal(failed.room.game?.status,'failed');assert.equal(failed.room.reservationUntil,t.joined.reservationUntil);
 assert.throws(()=>t.act(1,{type:'gameAck',epoch:ready.game?.epoch,hash:'c'.repeat(64)}),/stale_game/);
 t.act(1,{type:'leave',intent:t.joined.reservationIntent});assert.throws(()=>t.ready(1),/not_in_room/);
});

test('authenticated room routing protects controller requests and replacement guests',()=>{
 const t=setup(),peerEpoch=t.joined.peer.epoch!;
 const request={type:'gameControllerPropose',peerEpoch,revision:0,mode:'shared',p1:'guest'};
 assert.throws(()=>t.act(1,request),/host_only/);
 const proposed=t.act(0,request).room!,proposalId=proposed.game!.controllerProposal!.id;
 const accept={type:'gameControllerRespond',peerEpoch,proposalId,accept:true};
 t.act(0,accept);assert.equal(t.act(1,accept).room!.game!.controllers!.p1,'guest');
 t.act(1,{type:'leave',intent:t.joined.reservationIntent});
 const replacement=t.act(1,{type:'join',invite:t.joined.invite,intent:randomUUID()}).room!;
 assert.equal(replacement.game!.controllers!.p1,'host');assert.equal(replacement.game!.controllers!.mode,'separate');assert.equal(replacement.game!.status,'paused');
 assert.throws(()=>t.act(1,accept),/stale_game/);
});

test('host Start releases an unready guest, starts solo, and closes later admission',()=>{
 const t=setup(),guest=t.joined;
 assert.throws(()=>t.act(1,{type:'startRoom',roomId:guest.id,membership:guest.chatMembership,fingerprint}),/host_only/);
 assert.throws(()=>t.act(0,{type:'startRoom',roomId:guest.id,membership:'stale',fingerprint}),/membership_changed/);
 assert.throws(()=>t.act(0,{type:'startRoom',roomId:guest.id,membership:t.hostRoom.chatMembership,fingerprint:{...fingerprint,romSha256:'d'.repeat(64)}}),/game_mismatch/);
 const started=t.start().room!;
 assert.equal(started.started,'solo');assert.equal(started.status,'playing');assert.equal(started.occupancy,1);assert.equal(started.established,false);
 assert.equal(t.start().room!.started,'solo','repeated Start is idempotent');
 assert.ok(t.events[1].some(event=>event.type==='ended'&&event.reason==='host_started_solo'));
 assert.throws(()=>t.ready(1),/not_in_room/);
 const newcomer=t.rooms.attach(undefined,()=>{},()=>{});
 assert.throws(()=>t.rooms.handle(newcomer.token,{type:'joinCode',code:started.code!,intent:randomUUID(),requestId:randomUUID()}),/room_started/);
 assert.equal(t.rooms.handle(newcomer.token,{type:'directory',requestId:randomUUID()}).directory!.find(row=>row.id===started.id)?.status,'playing');
});

test('host Start with a prepared guest requests host inspection and one shared barrier',()=>{
 const t=setup();t.act(1,{type:'file',fingerprint});t.ready(1);
 const started=t.start().room!;assert.equal(started.started,'shared');assert.notEqual(started.game?.status,'starting');
 assert.equal(t.events[0].filter(event=>event.type==='gameInspect').length,1);
 const preparing=t.ready(0).room!;assert.equal(preparing.game?.status,'starting');
 assert.equal(t.start().room?.game?.epoch,preparing.game?.epoch);
 for(const who of [0,1])t.act(who,{type:'gameAck',epoch:preparing.game?.epoch,hash:'c'.repeat(64)});
 assert.equal(t.start().room?.game?.status,'playing');
 t.act(1,{type:'leave',intent:t.joined.reservationIntent});
 const observer=t.rooms.attach(undefined,()=>{},()=>{});
 assert.throws(()=>t.rooms.handle(observer.token,{type:'joinCode',code:started.code!,intent:randomUUID(),requestId:randomUUID()}),/room_started/);
});
