import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {Rooms} from './rooms.ts';
import {parseRoomCommand,type RoomEvent,type RoomView,type Fingerprint} from '../../../packages/contracts/src/rooms.ts';
const hash='c'.repeat(64),otherHash='d'.repeat(64);
const fingerprint:Fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:1,submapper:0,region:'NTSC',bytes:32784}};
function setup(count=5){
 let now=1000;const rooms=new Rooms(()=>now),events:RoomEvent[][]=Array.from({length:count},()=>[]),senders=events.map(list=>(event:RoomEvent)=>list.push(event)),sessions=senders.map(send=>rooms.attach(undefined,send,()=>{}));let latest!:RoomView;
 function act(who:number,input:Record<string,unknown>){const command=parseRoomCommand({...input,requestId:randomUUID()});assert.ok(command&&command.type!=='hello',`invalid command ${input.type}`);const result=rooms.handle(sessions[who].token,command);if(result.room)latest=result.room;return result;}
 const intent=randomUUID();act(0,{type:'create',intent,visibility:'public',fingerprint});act(0,{type:'confirmCreate',intent});
 const members=[latest.chatMembership],intents:string[]=[intent];
 for(let i=1;i<count;i++){const joined=act(i,{type:'join',invite:latest.invite,intent:randomUUID()}).room!;members.push(joined.chatMembership);intents.push(joined.reservationIntent);}
 function view(){const event=events[0].filter(e=>e.type==='room').at(-1);return event?.type==='room'?event.room:latest;}
 for(let i=1;i<count;i++){
  const pair=view().peers.find(p=>p.member===members[i])!;
  for(const type of ['peerAck','peerConnected'])for(const who of [0,i])act(who,{type,pairId:pair.pairId,epoch:pair.epoch});
 }
 const load=(who:number)=>{if(who===0)act(0,{type:'prepareHost',roomId:view().id,membership:members[0],fingerprint});else{act(who,{type:'file',fingerprint});act(who,{type:'memberAcquisition',roomId:view().id,membership:members[who],phase:'loaded'});}};
 const ready=(who:number,extra={})=>act(who,{type:'gameReady',revision:view().game.controllers.revision,roomRevision:view().revision,frame:0,fresh:true,hash,delay:who===0?3:8,...extra});
 const start=()=>act(0,{type:'startRoom',roomId:view().id,membership:members[0],fingerprint});
 const begin=()=>{for(let i=0;i<count;i++)load(i);for(let i=0;i<count;i++)ready(i);const epoch=start().room!.game.epoch!;for(const who of count>1?[0,1]:[0])act(who,{type:'gameAck',epoch,hash});return epoch;};
 const role=(slotId:string,role:string)=>act(0,{type:'slotRole',roomId:view().id,expectedRevision:view().revision,slotId,role});
 const captures=()=>events[0].filter(e=>e.type==='gameCapture');
 const authorize=(transfer:Extract<RoomEvent,{type:'gameCapture'}>,frame=917)=>{act(0,{type:'gameCaptured',epoch:transfer.epoch,transferId:transfer.transferId,frame,hash});const who=members.indexOf(transfer.recipient);act(who,{type:'gameCheckpointReady',epoch:transfer.epoch,transferId:transfer.transferId});return who;};
 const ack=(transfer:Extract<RoomEvent,{type:'gameCapture'}>,who:number,frame=917)=>act(who,{type:'gameCheckpointAck',epoch:transfer.epoch,transferId:transfer.transferId,frame,hash});
 return {rooms,sessions,senders,events,members,intents,act,view,load,ready,start,begin,role,captures,authorize,ack,advance(ms:number){while(ms>0){const step=Math.min(ms,10000);now+=step;ms-=step;for(let i=0;i<count;i++)act(i,{type:'heartbeat'});rooms.sweep();}}};
}
test('every occupied member is ready before initial Start; only owners acknowledge live play',()=>{
 const t=setup();assert.throws(()=>t.ready(1),/game_prerequisites/);t.act(1,{type:'file',fingerprint:{...fingerprint,romSha256:otherHash}});assert.throws(()=>t.ready(1),/game_prerequisites/);
 for(let i=0;i<5;i++)t.load(i);for(let i=0;i<4;i++)t.ready(i);assert.throws(()=>t.start(),/game_prerequisites/);assert.equal(t.view().started,undefined);assert.equal(t.view().occupancy,5);
 t.ready(4);assert.notEqual(t.view().game.status,'starting');const epoch=t.start().room!.game.epoch!;assert.equal(t.view().game.delay,8);assert.equal(t.view().established,false);assert.equal(t.start().room!.game.epoch,epoch);
 assert.throws(()=>t.act(2,{type:'gameAck',epoch,hash}),/stale_game/);assert.throws(()=>t.act(1,{type:'gameAck',epoch,hash:otherHash}),/stale_game/);
 t.act(0,{type:'gameAck',epoch,hash});assert.equal(t.view().game.status,'starting');t.act(1,{type:'gameAck',epoch,hash});assert.equal(t.view().game.status,'playing');assert.equal(t.view().established,true);
 assert.equal(t.events[2].some(e=>e.type==='gamePrepare'),false);assert.equal(t.view().occupancy,5,'prepared observers remain outside the owner acknowledgement barrier');
});
test('host membership/file authority and explicit readiness cancellation remain enforced',()=>{
 const t=setup(2),room=t.view();
 for(const type of ['prepareHost','startRoom']){
  assert.throws(()=>t.act(1,{type,roomId:room.id,membership:t.members[1],fingerprint}),/host_only/);
  assert.throws(()=>t.act(0,{type,roomId:room.id,membership:randomUUID(),fingerprint}),/membership_changed/);
  assert.throws(()=>t.act(0,{type,roomId:room.id,membership:t.members[0],fingerprint:{...fingerprint,romSha256:otherHash}}),/game_mismatch/);
 }
 t.load(0);t.load(1);assert.throws(()=>t.start(),/game_prerequisites/);t.ready(1);t.act(1,{type:'gameUnready',revision:t.view().game.controllers.revision});assert.deepEqual(t.view().game.ready,[]);assert.throws(()=>t.start(),/game_prerequisites/);
 assert.throws(()=>t.act(1,{type:'gameUnready',revision:999}),/stale_controllers/);
});
test('progressed initial state and expired start barrier cannot silently promote members',()=>{
 const t=setup(2);t.load(0);t.load(1);t.ready(1);t.ready(0,{frame:12,fresh:false});t.start();assert.equal(t.view().game.status,'failed');assert.equal(t.view().started,undefined);assert.equal(t.view().established,false);
 // A new attempt needs explicit fresh offers; the failed attempt cannot ack.
 const u=setup(2);u.load(0);u.load(1);u.ready(1);u.ready(0);const epoch=u.start().room!.game.epoch!;u.advance(10000);assert.equal(u.view().game.status,'failed');assert.throws(()=>u.act(1,{type:'gameAck',epoch,hash}),/stale_game/);
});
test('unready host or member cannot Start or silently remove anyone',()=>{
 const t=setup(2);t.load(0);t.load(1);t.ready(1);assert.throws(()=>t.start(),/game_prerequisites/);assert.equal(t.view().game.startRequested,false);assert.equal(t.view().occupancy,2);
 t.ready(0);assert.equal(t.start().room!.game.status,'starting');
 const u=setup(2);u.load(0);u.ready(0);assert.throws(()=>u.start(),/game_prerequisites/);assert.equal(u.view().occupancy,2);assert.equal(u.events[1].some(e=>e.type==='ended'),false);
});
test('stalled host freezes exact completed state and resume needs authenticated checkpoint acknowledgement',()=>{
 const t=setup(3),epoch=t.begin();t.act(1,{type:'gamePause',epoch,frame:910,reason:'network'});assert.ok(t.events[0].some(e=>e.type==='gameFreeze'));
 assert.throws(()=>t.act(1,{type:'gameFrozen',epoch,frame:917,hash}),/stale_game/);t.act(0,{type:'gameFrozen',epoch,frame:917,hash});
 t.ready(0,{frame:917,fresh:false});t.ready(1,{frame:910,fresh:false,hash:otherHash});const transfer=t.captures().at(-1)!;assert.equal(transfer.recipient,t.members[1]);
 assert.throws(()=>t.act(0,{type:'gameResume',epoch}),/resume_not_ready/);const who=t.authorize(transfer);
 assert.throws(()=>t.ack(transfer,2),/stale_checkpoint/);assert.throws(()=>t.ack(transfer,who,910),/stale_checkpoint/);t.ack(transfer,who);
 assert.equal(t.view().game.status,'resume_ready');assert.throws(()=>t.act(1,{type:'gameResume',epoch}),/resume_not_ready/);
 t.act(0,{type:'gameResume',epoch});const next=t.view().game.epoch!;assert.notEqual(next,epoch);assert.equal(t.view().game.frame,917);assert.throws(()=>t.act(1,{type:'gameAck',epoch,hash}),/stale_game/);
});
test('host may become observer; role labels and controller mapping commit only after all proposed owners sync',()=>{
 const t=setup(),epoch=t.begin(),old=t.view();t.role('slot-3','player1');const pending=t.view().game.pending!;
 assert.deepEqual(t.view().game.controllers,old.game.controllers);assert.equal(t.view().slots[0].role,'player1');
 assert.throws(()=>t.act(1,{type:'gameRoleCancel',transactionId:pending.id}),/stale_controllers/);
 t.act(0,{type:'gameFrozen',epoch,frame:917,hash});const transfers=t.captures();assert.deepEqual(new Set(transfers.map(e=>e.recipient)),new Set([t.members[1],t.members[2]]));
 // This unrelated observer retracting a local offer must not cancel the transaction.
 t.act(4,{type:'gameUnready',revision:old.game.controllers.revision});assert.equal(t.view().game.pending?.status,'synchronizing');
 const first=t.authorize(transfers[0]);t.ack(transfers[0],first);assert.equal(t.view().game.pending?.id,pending.id);assert.deepEqual(t.view().game.controllers,old.game.controllers);
 const second=t.authorize(transfers[1]);t.ack(transfers[1],second);assert.equal(t.view().game.pending,undefined);assert.equal(t.view().slots[0].role,'observer');assert.equal(t.view().hostMembership,t.members[0]);assert.deepEqual(t.view().game.controllers.owners,[t.members[2],t.members[1]]);assert.equal(t.view().game.frame,917);
 const next=t.view().game.epoch!;for(const who of [0,1,2])t.act(who,{type:'gameAck',epoch:next,hash});assert.equal(t.view().game.status,'playing');
});
test('departed stalled controller can be replaced without another packet or acknowledgement from that member',()=>{
 const t=setup(),epoch=t.begin(),old=t.view().game.controllers;
 t.act(0,{type:'memberRemove',roomId:t.view().id,membership:t.members[1],expectedRevision:t.view().revision});assert.equal(t.view().game.status,'pausing');t.role('slot-3','player2');
 t.act(0,{type:'gameFrozen',epoch,frame:917,hash});assert.deepEqual(t.view().game.controllers,old);const transfer=t.captures().at(-1)!;assert.equal(transfer.recipient,t.members[2]);
 assert.throws(()=>t.act(1,{type:'gameAck',epoch,hash}),/not_in_room/);t.ack(transfer,t.authorize(transfer));assert.deepEqual(t.view().game.controllers.owners,[t.members[0],t.members[2]]);assert.equal(t.view().game.frame,917);
 const next=t.view().game.epoch!;for(const who of [0,2])t.act(who,{type:'gameAck',epoch:next,hash});assert.equal(t.view().game.status,'playing');
});
test('failed checkpoint retry preserves prior roles until commit; cancel preserves exact paused boundary',()=>{
 const t=setup(),epoch=t.begin(),old=t.view().game.controllers;t.role('slot-3','player2');const transactionId=t.view().game.pending!.id;t.act(0,{type:'gameFrozen',epoch,frame:917,hash});let transfer=t.captures().at(-1)!;
 t.act(2,{type:'gameCheckpointFailed',epoch,transferId:transfer.transferId});assert.equal(t.view().game.pending?.status,'failed');assert.deepEqual(t.view().game.controllers,old);assert.equal(t.view().game.frame,917);
 t.act(0,{type:'gameRoleRetry',transactionId});t.act(0,{type:'gameFrozen',epoch,frame:917,hash});const previous=transfer;transfer=t.captures().at(-1)!;assert.notEqual(transfer.transferId,previous.transferId);assert.throws(()=>t.ack(previous,2),/stale_checkpoint/);
 t.act(0,{type:'gameRoleCancel',transactionId});assert.equal(t.view().game.pending,undefined);assert.deepEqual(t.view().game.controllers,old);assert.equal(t.view().game.frame,917);assert.equal(t.view().game.status,'paused');assert.throws(()=>t.ack(transfer,2),/stale_checkpoint/);
});
test('membership change invalidates pending transaction; ordinary observer departure does not pause play',()=>{
 const t=setup(),epoch=t.begin();t.rooms.detach(t.sessions[4].token,t.senders[4]);assert.equal(t.view().game.status,'playing');
 t.role('slot-3','player2');t.act(0,{type:'gameFrozen',epoch,frame:917,hash});const old=t.view().game.controllers;
 t.act(0,{type:'memberRemove',roomId:t.view().id,membership:t.members[3],expectedRevision:t.view().revision});assert.equal(t.view().game.pending?.status,'failed');assert.deepEqual(t.view().game.controllers,old);assert.equal(t.view().game.frame,917);
});
test('observer checkpoint failures are isolated and duplicate acknowledgements cannot renew catch-up deadline',()=>{
 const t=setup(),epoch=t.begin();t.act(2,{type:'gameObserve',revision:t.view().game.controllers.revision});let transfer=t.captures().at(-1)!;t.ack(transfer,t.authorize(transfer));
 const ackCount=t.events[0].filter(e=>e.type==='gameCatchup').length;t.advance(10000);t.ack(transfer,2);assert.equal(t.events[0].filter(e=>e.type==='gameCatchup').length,ackCount);t.advance(5000);
 assert.equal(t.view().game.status,'playing');assert.ok(t.events[2].some(e=>e.type==='gameSyncStop'&&e.transferId===transfer.transferId));assert.throws(()=>t.ack(transfer,2),/stale_checkpoint/);
 t.act(2,{type:'gameObserve',revision:t.view().game.controllers.revision});transfer=t.captures().at(-1)!;t.act(2,{type:'gameCheckpointFailed',epoch,transferId:transfer.transferId});assert.equal(t.view().game.status,'playing');
 assert.throws(()=>t.act(2,{type:'gamePause',epoch,frame:917,reason:'user'}),/controller_only/);
});

test('fresh retry after initial state mismatch starts a new barrier instead of stranding the room',()=>{
 const t=setup(2);t.load(0);t.load(1);t.ready(0,{frame:12,fresh:false});t.ready(1);t.start();assert.equal(t.view().game.status,'failed');
 t.ready(0);t.ready(1);t.start();assert.equal(t.view().game.status,'starting');
});
test('unready member revokes initial readiness before Start',()=>{
 const t=setup(3);for(let i=0;i<3;i++){t.load(i);t.ready(i);}t.act(2,{type:'gameUnready',revision:t.view().game.controllers.revision});
 assert.equal(t.view().game.startRequested,false);assert.throws(()=>t.start(),/game_prerequisites/);assert.equal(t.view().started,undefined);
 t.ready(2);assert.equal(t.start().room!.game.status,'starting');
});
test('a disconnected or failed observer loses Ready before initial Start',()=>{
 const failed=setup(3);for(let i=0;i<3;i++){failed.load(i);failed.ready(i);}
 failed.act(2,{type:'memberAcquisition',roomId:failed.view().id,membership:failed.members[2],phase:'failed'});
 assert.equal(failed.view().game.ready.includes(failed.members[2]),false);assert.throws(()=>failed.start(),/game_prerequisites/);
 const disconnected=setup(3);for(let i=0;i<3;i++){disconnected.load(i);disconnected.ready(i);}
 disconnected.rooms.detach(disconnected.sessions[2].token,disconnected.senders[2]);
 assert.equal(disconnected.view().game.ready.includes(disconnected.members[2]),false);assert.throws(()=>disconnected.start(),/game_prerequisites/);
});
test('slot availability revision while checkpoint is in flight invalidates all pending role publication',()=>{
 const t=setup(3),epoch=t.begin(),old=t.view().game.controllers;t.role('slot-3','player2');t.act(0,{type:'gameFrozen',epoch,frame:917,hash});const transfer=t.captures().at(-1)!,recipient=t.authorize(transfer);
 t.act(0,{type:'slotAvailability',roomId:t.view().id,slotId:'slot-5',open:false,expectedRevision:t.view().revision});
 assert.equal(t.view().game.pending?.status,'failed');assert.equal(t.view().game.status,'paused');assert.deepEqual(t.view().game.controllers,old);assert.equal(t.view().slots[2].role,'observer');assert.equal(t.view().game.frame,917);
 assert.throws(()=>t.ack(transfer,recipient),/stale_checkpoint/);
});
test('new member joining while role import is held invalidates the old transaction before late ack',()=>{
 const t=setup(3),epoch=t.begin(),old=t.view().game.controllers;t.role('slot-3','player2');t.act(0,{type:'gameFrozen',epoch,frame:917,hash});const transfer=t.captures().at(-1)!,recipient=t.authorize(transfer);
 const newcomer=t.rooms.attach(undefined,()=>{},()=>{});const command=parseRoomCommand({type:'join',invite:t.view().invite,intent:randomUUID(),requestId:randomUUID()});assert.ok(command&&command.type!=='hello');t.rooms.handle(newcomer.token,command);
 assert.equal(t.view().game.pending?.status,'failed');assert.equal(t.view().game.status,'paused');assert.deepEqual(t.view().game.controllers,old);assert.equal(t.view().game.frame,917);assert.throws(()=>t.ack(transfer,recipient),/stale_checkpoint/);
});
test('role checkpoint deadline preserves mapping and frame, permits explicit retry, and rejects expired transfer',()=>{
 const t=setup(),epoch=t.begin(),old=t.view().game.controllers;t.role('slot-3','player2');const transactionId=t.view().game.pending!.id;t.act(0,{type:'gameFrozen',epoch,frame:917,hash});const expired=t.captures().at(-1)!;t.authorize(expired);
 t.advance(30000);assert.equal(t.view().game.pending?.status,'failed');assert.equal(t.view().game.frame,917);assert.deepEqual(t.view().game.controllers,old);assert.throws(()=>t.ack(expired,2),/stale_checkpoint/);
 t.act(0,{type:'gameRoleRetry',transactionId});t.act(0,{type:'gameFrozen',epoch,frame:917,hash});assert.equal(t.view().game.pending?.status,'synchronizing');const retry=t.captures().at(-1)!;assert.notEqual(retry.transferId,expired.transferId);t.ack(retry,t.authorize(retry));assert.deepEqual(t.view().game.controllers.owners,[t.members[0],t.members[2]]);
});
test('retracted starting owner cannot use an already issued barrier acknowledgement',()=>{
 const t=setup(2);t.load(0);t.load(1);t.ready(0);t.ready(1);const epoch=t.start().room!.game.epoch!;
 t.act(1,{type:'gameUnready',revision:t.view().game.controllers.revision});assert.notEqual(t.view().game.status,'starting');assert.throws(()=>t.act(1,{type:'gameAck',epoch,hash}),/stale_game/);assert.equal(t.view().established,false);
});
test('unready Start rejection remains waiting until all members explicitly prepare',()=>{
 const t=setup(2);t.load(0);t.load(1);t.ready(1);assert.throws(()=>t.start(),/game_prerequisites/);t.advance(10000);assert.equal(t.view().game.status,'waiting');
 t.ready(0);t.start();assert.equal(t.view().game.status,'starting');assert.equal(t.view().occupancy,2);
});
test('expired initial barrier retries from explicit fresh offers without becoming an unreachable resume state',()=>{
 const t=setup(2);t.load(0);t.load(1);t.ready(1);t.ready(0);const old=t.start().room!.game.epoch!;t.advance(10000);
 assert.equal(t.view().game.status,'failed');assert.equal(t.view().established,false);
 t.ready(1);t.ready(0);const next=t.view().game.epoch!;assert.notEqual(next,old);assert.equal(t.view().game.status,'starting');
 assert.throws(()=>t.act(1,{type:'gameAck',epoch:old,hash}),/stale_game/);
 t.act(0,{type:'gameAck',epoch:next,hash});t.act(1,{type:'gameAck',epoch:next,hash});assert.equal(t.view().game.status,'playing');assert.equal(t.view().established,true);assert.equal(t.view().game.frame,0);
});

test('ordinary pause retains bounded observer catch-up while a fresh epoch cancels it without a barrier',()=>{
 const t=setup(3),epoch=t.begin();t.act(2,{type:'gameObserve',revision:t.view().game.controllers.revision});const transfer=t.captures().at(-1)!;const who=t.authorize(transfer,100);t.ack(transfer,who,100);
 t.act(0,{type:'gamePause',epoch,frame:150,reason:'user'});t.act(0,{type:'gameFrozen',epoch,frame:150,hash});
 assert.equal(t.events[2].some(e=>e.type==='gameSyncStop'&&e.transferId===transfer.transferId),false);
 t.ready(0,{frame:150,fresh:false});t.ready(1,{frame:150,fresh:false});assert.equal(t.view().game.status,'resume_ready','observer cannot delay controller readiness');
 t.act(0,{type:'gameResume',epoch});assert.notEqual(t.view().game.epoch,epoch);assert.ok(t.events[2].some(e=>e.type==='gameSyncStop'&&e.transferId===transfer.transferId));
});

test('pre-Start room and role revisions revoke old Ready offers',()=>{
 const t=setup(3);for(let i=0;i<3;i++){t.load(i);t.ready(i);}
 const priorRevision=t.view().revision;t.act(0,{type:'slotAvailability',roomId:t.view().id,slotId:'slot-5',open:false,expectedRevision:priorRevision});assert.deepEqual(t.view().game.ready,[]);assert.throws(()=>t.ready(1,{roomRevision:priorRevision}),/room_changed/);assert.deepEqual(t.view().game.ready,[]);assert.throws(()=>t.start(),/game_prerequisites/);
 for(let i=0;i<3;i++)t.ready(i);t.role('slot-1','observer');assert.deepEqual(t.view().game.ready,[]);assert.throws(()=>t.start(),/game_prerequisites/);
 for(let i=0;i<3;i++)t.ready(i);const epoch=t.start().room!.game.epoch!;for(const who of [0,1])t.act(who,{type:'gameAck',epoch,hash});assert.equal(t.view().game.status,'playing');
});
test('observing host remains an authority readiness owner when retrying the first barrier',()=>{
 const t=setup(2);t.role('slot-1','observer');t.load(0);t.load(1);t.ready(0);t.ready(1);const prior=t.start().room!.game.epoch!;t.advance(10000);
 assert.equal(t.view().established,false);t.ready(0);t.ready(1);const epoch=t.view().game.epoch!;assert.notEqual(epoch,prior);
 t.act(1,{type:'gameAck',epoch,hash});assert.equal(t.view().game.status,'starting');t.act(0,{type:'gameAck',epoch,hash});assert.equal(t.view().game.status,'playing');assert.equal(t.view().slots[0].role,'observer');
});
