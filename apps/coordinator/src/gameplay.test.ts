import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {catalogEntry} from '../../../packages/contracts/src/catalog.ts';
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
 for(let i=0;i<count;i++)for(let j=i+1;j<count;j++){
  const event=events[i].filter(item=>item.type==='room').at(-1);
  if(event?.type!=='room')throw Error('Missing member room view');
  const pair=event.room.peers.find(peer=>peer.member===members[j])!;
  for(const type of ['peerAck','peerConnected'])for(const who of [i,j])act(who,{type,pairId:pair.pairId,epoch:pair.epoch});
 }
 const load=(who:number)=>{if(who===0)act(0,{type:'prepareHost',roomId:view().id,membership:members[0],fingerprint});else{act(who,{type:'file',fingerprint});act(who,{type:'memberAcquisition',roomId:view().id,membership:members[who],phase:'loaded'});}};
 const ready=(who:number,extra={})=>act(who,{type:'gameReady',revision:view().game.controllers.revision,roomRevision:view().revision,frame:0,fresh:true,hash,delay:who===0?3:8,...extra});
 const start=()=>act(0,{type:'startRoom',roomId:view().id,membership:members[0],fingerprint});
 const begin=()=>{for(let i=0;i<count;i++)load(i);for(let i=0;i<count;i++)ready(i);const epoch=start().room!.game.epoch!;for(const who of count>1?[0,1]:[0])act(who,{type:'gameAck',epoch,hash});assert.equal(view().game.status,'countdown');now+=3000;rooms.sweep();assert.equal(view().game.status,'playing');return epoch;};
 const role=(slotId:string,role:string)=>act(0,{type:'slotRole',roomId:view().id,expectedRevision:view().revision,slotId,role});
 const captures=()=>events[0].filter(e=>e.type==='gameCapture');
 const authorize=(transfer:Extract<RoomEvent,{type:'gameCapture'}>,frame=917)=>{act(0,{type:'gameCaptured',epoch:transfer.epoch,transferId:transfer.transferId,frame,hash});const who=members.indexOf(transfer.recipient);act(who,{type:'gameCheckpointReady',epoch:transfer.epoch,transferId:transfer.transferId});return who;};
 const ack=(transfer:Extract<RoomEvent,{type:'gameCapture'}>,who:number,frame=917)=>act(who,{type:'gameCheckpointAck',epoch:transfer.epoch,transferId:transfer.transferId,frame,hash});
 return {rooms,sessions,senders,events,members,intents,act,view,load,ready,start,begin,role,captures,authorize,ack,advance(ms:number){while(ms>0){const step=Math.min(ms,10000);now+=step;ms-=step;for(let i=0;i<count;i++)act(i,{type:'heartbeat'});rooms.sweep();}}};
}
test('only controller owners are ready before initial Start; observers do not block',()=>{
 const t=setup();assert.throws(()=>t.ready(1),/game_prerequisites/);t.act(1,{type:'file',fingerprint:{...fingerprint,romSha256:otherHash}});assert.throws(()=>t.ready(1),/game_prerequisites/);
 t.load(0);t.load(1);t.ready(0);assert.throws(()=>t.start(),/game_prerequisites/);assert.equal(t.view().started,undefined);assert.equal(t.view().occupancy,5);
 t.ready(1);const epoch=t.start().room!.game.epoch!;assert.equal(t.view().game.delay,8);assert.equal(t.view().established,false);assert.equal(t.start().room!.game.epoch,epoch);
 assert.throws(()=>t.act(2,{type:'gameAck',epoch,hash}),/stale_game/);assert.throws(()=>t.act(1,{type:'gameAck',epoch,hash:otherHash}),/stale_game/);
 t.act(0,{type:'gameAck',epoch,hash});assert.equal(t.view().game.status,'starting');t.act(1,{type:'gameAck',epoch,hash});assert.equal(t.view().game.status,'countdown');assert.equal(t.view().established,false);assert.equal(t.view().game.startAt,4000);t.advance(2999);assert.equal(t.view().game.status,'countdown');t.advance(1);assert.equal(t.view().game.status,'playing');assert.equal(t.view().established,true);
 assert.equal(t.events[2].some(e=>e.type==='gamePrepare'),false);assert.equal(t.view().occupancy,5,'unprepared observers remain outside the owner acknowledgement barrier');
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
 const next=t.view().game.epoch!;for(const who of [0,1,2])t.act(who,{type:'gameAck',epoch:next,hash});assert.equal(t.view().game.status,'countdown');t.advance(3000);assert.equal(t.view().game.status,'playing');
});
test('departed stalled controller shifts the next member into P2 and synchronizes without the departed member',()=>{
 const t=setup(),epoch=t.begin(),old=t.view().game.controllers;
 t.act(0,{type:'memberRemove',roomId:t.view().id,membership:t.members[1],expectedRevision:t.view().revision});assert.equal(t.view().game.status,'pausing');assert.equal(t.view().slots[1].member?.id,t.members[2]);
 t.act(0,{type:'gameFrozen',epoch,frame:917,hash});assert.deepEqual(t.view().game.controllers,old);const transfer=t.captures().at(-1)!;assert.equal(transfer.recipient,t.members[2]);
 assert.throws(()=>t.act(1,{type:'gameAck',epoch,hash}),/not_in_room/);t.ack(transfer,t.authorize(transfer));assert.deepEqual(t.view().game.controllers.owners,[t.members[0],t.members[2]]);assert.equal(t.view().game.frame,917);
 const next=t.view().game.epoch!;for(const who of [0,2])t.act(who,{type:'gameAck',epoch:next,hash});assert.equal(t.view().game.status,'countdown');t.advance(3000);assert.equal(t.view().game.status,'playing');
});
test('controller departure replaces an in-flight role change with the new compacted roster',()=>{
 const t=setup(),epoch=t.begin();t.role('slot-3','player2');const old=t.view().game.pending!.id;
 t.act(0,{type:'memberRemove',roomId:t.view().id,membership:t.members[1],expectedRevision:t.view().revision});
 assert.equal(t.view().slots[1].member?.id,t.members[2]);assert.notEqual(t.view().game.pending?.id,old);assert.equal(t.view().game.status,'pausing');
 t.act(0,{type:'gameFrozen',epoch,frame:917,hash});const transfer=t.captures().at(-1)!;assert.equal(transfer.recipient,t.members[2]);
 t.ack(transfer,t.authorize(transfer));assert.deepEqual(t.view().game.controllers.owners,[t.members[0],t.members[2]]);
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
test('unready controller owner revokes initial readiness before Start',()=>{
 const t=setup(3);for(let i=0;i<3;i++){t.load(i);t.ready(i);}t.act(2,{type:'gameUnready',revision:t.view().game.controllers.revision});
 t.act(1,{type:'gameUnready',revision:t.view().game.controllers.revision});
 assert.equal(t.view().game.startRequested,false);assert.throws(()=>t.start(),/game_prerequisites/);assert.equal(t.view().started,undefined);
 t.ready(1);assert.equal(t.start().room!.game.status,'starting');
});
test('a disconnected or failed observer does not block initial Start',()=>{
 const failed=setup(3);for(let i=0;i<3;i++){failed.load(i);failed.ready(i);}
 failed.act(2,{type:'memberAcquisition',roomId:failed.view().id,membership:failed.members[2],phase:'failed'});
 assert.equal(failed.view().game.ready.includes(failed.members[2]),false);assert.equal(failed.start().room!.game.status,'starting');
 const disconnected=setup(3);for(let i=0;i<3;i++){disconnected.load(i);disconnected.ready(i);}
 disconnected.rooms.detach(disconnected.sessions[2].token,disconnected.senders[2]);
 assert.equal(disconnected.view().game.ready.includes(disconnected.members[2]),false);assert.equal(disconnected.start().room!.game.status,'starting');
});
test('observer link loss leaves controller Ready and initial Start intact',()=>{
 const pairBetweenMembers=(t:ReturnType<typeof setup>)=>{
  const event=t.events[1].filter(item=>item.type==='room').at(-1);
  if(event?.type!=='room')throw Error('Missing member room view');
  const pair=event.room.peers.find(peer=>peer.member===t.members[2]);
  if(!pair)throw Error('Missing non-host pair');
  return pair;
 };
 const waiting=setup(3);for(let i=0;i<3;i++){waiting.load(i);waiting.ready(i);}
 const oldPair=pairBetweenMembers(waiting);
 waiting.act(1,{type:'peerRetry',pairId:oldPair.pairId,epoch:oldPair.epoch});
 assert.equal(waiting.view().game.ready.includes(waiting.members[1]),true);
 assert.equal(waiting.view().game.ready.includes(waiting.members[2]),false);
 assert.equal(waiting.start().room!.game.status,'starting');
 const retry=pairBetweenMembers(waiting);
 for(const type of ['peerAck','peerConnected'])for(const who of [1,2])waiting.act(who,{type,pairId:retry.pairId,epoch:retry.epoch});
 const startingPair=pairBetweenMembers(waiting);
 waiting.act(1,{type:'peerRetry',pairId:startingPair.pairId,epoch:startingPair.epoch});
 assert.equal(waiting.view().game.status,'starting');
 assert.equal(waiting.view().game.startRequested,true);

 const playing=setup(3);playing.begin();const livePair=pairBetweenMembers(playing);
 playing.act(1,{type:'peerRetry',pairId:livePair.pairId,epoch:livePair.epoch});
 assert.equal(playing.view().game.status,'playing');
});
test('slot availability revision while checkpoint is in flight invalidates all pending role publication',()=>{
 const t=setup(3),epoch=t.begin(),old=t.view().game.controllers;t.role('slot-3','player2');t.act(0,{type:'gameFrozen',epoch,frame:917,hash});const transfer=t.captures().at(-1)!,recipient=t.authorize(transfer);
 t.act(0,{type:'slotAvailability',roomId:t.view().id,slotId:'slot-5',open:false,expectedRevision:t.view().revision});
 assert.equal(t.view().game.pending?.status,'failed');assert.equal(t.view().game.status,'paused');assert.deepEqual(t.view().game.controllers,old);assert.equal(t.view().slots[2].role,'observer');assert.equal(t.view().game.frame,917);
 assert.throws(()=>t.ack(transfer,recipient),/stale_checkpoint/);
});
test('new member invalidates held role import; host retry refreshes roster and rejects stale acknowledgements',()=>{
 const t=setup(3),epoch=t.begin(),old=t.view().game.controllers;t.role('slot-3','player2');t.act(0,{type:'gameFrozen',epoch,frame:917,hash});const transfer=t.captures().at(-1)!,recipient=t.authorize(transfer);
 const newcomer=t.rooms.attach(undefined,()=>{},()=>{});const command=parseRoomCommand({type:'join',invite:t.view().invite,intent:randomUUID(),requestId:randomUUID()});assert.ok(command&&command.type!=='hello');t.rooms.handle(newcomer.token,command);
 assert.equal(t.view().game.pending?.status,'failed');assert.equal(t.view().game.status,'paused');assert.deepEqual(t.view().game.controllers,old);assert.equal(t.view().game.frame,917);assert.throws(()=>t.ack(transfer,recipient),/stale_checkpoint/);
 const transactionId=t.view().game.pending!.id;
 assert.throws(()=>t.act(1,{type:'gameRoleRetry',transactionId}),/stale_controllers/);
 t.act(0,{type:'gameRoleRetry',transactionId});
 assert.equal(t.view().game.pending?.revision,t.view().revision);
 assert.equal(t.view().game.pending?.status,'freezing');
 t.act(0,{type:'gameFrozen',epoch,frame:917,hash});
 const retry=t.captures().at(-1)!;assert.notEqual(retry.transferId,transfer.transferId);
 t.ack(retry,t.authorize(retry));
 assert.equal(t.view().game.pending,undefined);assert.equal(t.view().game.frame,917);
 assert.deepEqual(t.view().game.controllers.owners,[t.members[0],t.members[2]]);
 assert.throws(()=>t.ack(transfer,recipient),/stale_game/);
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
test('countdown is shared and a player becoming unready cancels play',()=>{
 const t=setup(2);t.load(0);t.load(1);t.ready(0);t.ready(1);const epoch=t.start().room!.game.epoch!;
 t.act(0,{type:'gameAck',epoch,hash});t.act(1,{type:'gameAck',epoch,hash});
 assert.equal(t.view().game.status,'countdown');assert.equal(t.view().game.startAt,4000);
 assert.equal(t.events[0].some(event=>event.type==='gameStart'),false);
 t.act(1,{type:'gameUnready',revision:t.view().game.controllers.revision});t.advance(3000);
 assert.notEqual(t.view().game.status,'playing');assert.equal(t.events[0].some(event=>event.type==='gameStart'),false);
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
 t.act(0,{type:'gameAck',epoch:next,hash});t.act(1,{type:'gameAck',epoch:next,hash});assert.equal(t.view().game.status,'countdown');t.advance(3000);assert.equal(t.view().game.status,'playing');assert.equal(t.view().established,true);assert.equal(t.view().game.frame,0);
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
 for(let i=0;i<3;i++)t.ready(i);const epoch=t.start().room!.game.epoch!;for(const who of [0,1])t.act(who,{type:'gameAck',epoch,hash});assert.equal(t.view().game.status,'countdown');t.advance(3000);assert.equal(t.view().game.status,'playing');
});
test('observing host remains an authority readiness owner when retrying the first barrier',()=>{
 const t=setup(2);t.role('slot-1','observer');t.load(0);t.load(1);t.ready(0);t.ready(1);const prior=t.start().room!.game.epoch!;t.advance(10000);
 assert.equal(t.view().established,false);t.ready(0);t.ready(1);const epoch=t.view().game.epoch!;assert.notEqual(epoch,prior);
 t.act(1,{type:'gameAck',epoch,hash});assert.equal(t.view().game.status,'starting');t.act(0,{type:'gameAck',epoch,hash});assert.equal(t.view().game.status,'countdown');t.advance(3000);assert.equal(t.view().game.status,'playing');assert.equal(t.view().slots[0].role,'observer');
});

test('restored host timeline initializes paused once, then synchronizes current owners before resume',()=>{
 const t=setup(2);t.load(0);t.load(1);
 const restore={type:'gameRestore',revision:t.view().game.controllers.revision,roomRevision:t.view().revision,frame:917,hash};
 assert.throws(()=>t.act(1,restore),/game_prerequisites/);
 assert.throws(()=>t.act(0,{...restore,roomRevision:999}),/game_prerequisites/);
 t.act(0,restore);const epoch=t.view().game.epoch!;
 assert.equal(t.view().game.status,'paused');assert.equal(t.view().game.frame,917);assert.equal(t.view().started,'shared');
 assert.throws(()=>t.act(0,restore),/game_prerequisites/);assert.throws(()=>t.act(0,{type:'gameResume',epoch}),/resume_not_ready/);
 t.ready(0,{frame:917,fresh:false});t.ready(1,{frame:0,fresh:true,hash:otherHash});
 const transfer=t.captures().at(-1)!;t.authorize(transfer);t.ack(transfer,1);
 assert.equal(t.view().game.status,'resume_ready');t.act(0,{type:'gameResume',epoch});
 assert.notEqual(t.view().game.epoch,epoch);assert.equal(t.view().game.frame,917);
});

test('a new controller in a restored lobby cannot bypass explicit preparation and host resume',()=>{
 const t=setup(3);for(const who of [0,1,2])t.load(who);
 t.act(0,{type:'gameRestore',revision:t.view().game.controllers.revision,roomRevision:t.view().revision,frame:917,hash});const epoch=t.view().game.epoch!;
 t.role('slot-3','player2');t.act(0,{type:'gameFrozen',epoch,frame:917,hash});
 const transfer=t.captures().at(-1)!;const who=t.authorize(transfer);t.ack(transfer,who);
 assert.equal(t.view().game.pending,undefined);assert.equal(t.view().game.status,'paused');assert.equal(t.view().game.epoch,epoch);
 assert.throws(()=>t.act(0,{type:'gameResume',epoch}),/resume_not_ready/);
 t.ready(0,{frame:917,fresh:false});t.ready(2,{frame:917,fresh:false});assert.equal(t.view().game.status,'resume_ready');
 t.act(0,{type:'gameResume',epoch});assert.equal(t.view().game.status,'starting');
});

test('only the interrupted host can replace a failed timeline, once, under current authority',()=>{
 const t=setup(2),epoch=t.begin();
 t.rooms.detach(t.sessions[0].token,t.senders[0]);
 const disconnected=t.events[1].filter(event=>event.type==='room').at(-1)!;
 assert.equal(disconnected.type==='room'&&disconnected.room.game.status,'pausing');assert.equal(t.view().game.hostRecovery,undefined);
 const restore=()=>({type:'gameRestore',previousEpoch:epoch,revision:t.view().game.controllers.revision,roomRevision:t.view().revision,frame:917,hash});
 assert.throws(()=>t.act(0,restore()),/game_prerequisites/);
 t.advance(10000);t.rooms.attach(t.sessions[0].token,t.senders[0],()=>{});
 assert.equal(t.view().game.hostRecovery,epoch);
 assert.throws(()=>t.act(1,restore()),/game_prerequisites/);
 assert.throws(()=>t.act(0,{...restore(),roomRevision:999}),/game_prerequisites/);
 assert.throws(()=>t.act(0,{...restore(),previousEpoch:'x'.repeat(22)}),/game_prerequisites/);
 assert.throws(()=>t.ready(0),/host_recovery_required/);
 t.act(0,restore());const recovered=t.view().game.epoch!;
 assert.notEqual(recovered,epoch);assert.equal(t.view().game.hostRecovery,undefined);assert.equal(t.view().game.status,'paused');assert.equal(t.view().game.frame,917);
 assert.throws(()=>t.act(0,restore()),/game_prerequisites/);assert.throws(()=>t.act(1,{type:'gameAck',epoch,hash}),/stale_game/);
 reconnectPlayers(t);t.ready(0,{frame:917,fresh:false});t.ready(1,{frame:917,fresh:false});assert.equal(t.view().game.status,'resume_ready');
 t.act(0,{type:'gameResume',epoch:recovered});assert.equal(t.view().game.status,'starting');
});
test('a guest interruption cannot authorize host replacement, while a retained host can resume normally',()=>{
 const t=setup(2),epoch=t.begin();t.rooms.detach(t.sessions[1].token,t.senders[1]);t.advance(10000);
 assert.equal(t.view().game.hostRecovery,undefined);
 assert.throws(()=>t.act(0,{type:'gameRestore',previousEpoch:epoch,revision:t.view().game.controllers.revision,roomRevision:t.view().revision,frame:0,hash}),/game_prerequisites/);
 const u=setup(2),old=u.begin();u.rooms.detach(u.sessions[0].token,u.senders[0]);u.advance(10000);u.rooms.attach(u.sessions[0].token,u.senders[0],()=>{});
 reconnectPlayers(u);u.ready(0,{frame:917,fresh:false});u.ready(1,{frame:917,fresh:false});u.act(0,{type:'gameResume',epoch:old});const next=u.view().game.epoch!;
 assert.equal(u.view().game.hostRecovery,undefined);assert.notEqual(next,old);
});

function reconnectPlayers(t:ReturnType<typeof setup>){
 const peer=t.view().peers[0];
 for(const type of ['peerAck','peerConnected'])for(const who of [0,1])t.act(who,{type,pairId:peer.pairId,epoch:peer.epoch});
}

function requestLoad(t:ReturnType<typeof setup>,frame=20){
 const epoch=t.begin();t.act(0,{type:'gameLoadPropose',revision:t.view().game.controllers.revision,roomRevision:t.view().revision,frame,hash:otherHash,identity:'e'.repeat(64),savedAt:1000});
 const load=t.view().game.load!;assert.equal(load.phase,'freezing');
 t.act(0,{type:'gameFrozen',epoch,frame:917,hash});
 for(const who of [0,1])t.act(who,{type:'gameLoadBoundary',transactionId:load.id,frame:917,hash});
 assert.equal(t.view().game.load!.phase,'staging');return {epoch,id:load.id,target:load.epoch};
}
function rollbackLoad(t:ReturnType<typeof setup>,transactionId:string){for(const who of [0,1])t.act(who,{type:'gameLoadRolledBack',transactionId,frame:917,hash});}

test('shared Load automatically stages and requires every native acknowledgment before its new epoch',()=>{
 const t=setup(3),load=requestLoad(t);
 assert.throws(()=>t.act(2,{type:'gameLoadCommitted',transactionId:load.id,frame:20,hash:otherHash}),/controller_only/);
 assert.throws(()=>t.act(1,{type:'gameLoadCommitted',transactionId:load.id,frame:20,hash:otherHash}),/stale_load/);
 assert.equal(t.view().game.load!.phase,'staging');
 const transfer=t.captures().at(-1)!;assert.equal(transfer.purpose,'load');
 t.act(0,{type:'gameLoadPrepared',transactionId:load.id,frame:20,hash:otherHash});
 t.act(0,{type:'gameCaptured',epoch:load.target,transferId:transfer.transferId,frame:20,hash:otherHash});
 t.act(1,{type:'gameCheckpointReady',epoch:load.target,transferId:transfer.transferId});
 t.act(1,{type:'gameCheckpointAck',epoch:load.target,transferId:transfer.transferId,frame:20,hash:otherHash});assert.equal(t.view().game.load!.phase,'committing');
 t.act(0,{type:'gameLoadCommitted',transactionId:load.id,frame:20,hash:otherHash});assert.equal(t.view().game.epoch,load.epoch);
 t.act(1,{type:'gameLoadCommitted',transactionId:load.id,frame:20,hash:otherHash});assert.equal(t.view().game.load,undefined);assert.equal(t.view().game.epoch,load.target);assert.equal(t.view().game.frame,20);
 for(const who of [0,1])t.act(who,{type:'gameAck',epoch:load.target,hash:otherHash});t.advance(3000);assert.equal(t.view().game.status,'playing');
 assert.throws(()=>t.act(0,{type:'gameAck',epoch:load.epoch,hash}),/stale_game/);
 assert.equal(t.events[2].some(event=>event.type==='gameLoadCommit'),false,'observer incorrectly gated or imported controller commit');
});

test('native boundary failure and actual staging deadline retain prior frame/hash and epoch',()=>{
 for(const mode of ['failure','timeout']){
  const t=setup(2),load=requestLoad(t);if(mode==='failure')t.act(0,{type:'gameLoadFailed',transactionId:load.id});else {t.advance(29999);assert.equal(t.view().game.load!.phase,'staging');t.advance(1);}
  assert.equal(t.view().game.load!.phase,'rolling_back');rollbackLoad(t,load.id);
  assert.equal(t.view().game.load,undefined);assert.equal(t.view().game.frame,917);assert.equal(t.view().game.epoch,load.epoch);assert.equal(t.view().game.status,'paused');
  assert.throws(()=>t.act(1,{type:'gameLoadCommitted',transactionId:load.id,frame:20,hash:otherHash}),/stale_load/);
 }
});

test('a partial native Load commit rolls all controllers back and never starts the replacement',()=>{
 const t=setup(2),load=requestLoad(t);
 assert.throws(()=>t.act(1,{type:'gameLoadPrepared',transactionId:load.id,frame:20,hash:otherHash}),/checkpoint_required/);
 t.act(0,{type:'gameLoadPrepared',transactionId:load.id,frame:20,hash:otherHash});
 const transfer=t.captures().at(-1)!;t.act(0,{type:'gameCaptured',epoch:load.target,transferId:transfer.transferId,frame:20,hash:otherHash});t.act(1,{type:'gameCheckpointReady',epoch:load.target,transferId:transfer.transferId});t.act(1,{type:'gameCheckpointAck',epoch:load.target,transferId:transfer.transferId,frame:20,hash:otherHash});
 t.act(0,{type:'gameLoadCommitted',transactionId:load.id,frame:20,hash:otherHash});t.act(1,{type:'gameLoadFailed',transactionId:load.id});
 assert.equal(t.view().game.load!.phase,'rolling_back');assert.equal(t.view().game.epoch,load.epoch);rollbackLoad(t,load.id);
 assert.equal(t.view().game.frame,917);assert.equal(t.view().game.status,'paused');assert.equal(t.view().game.epoch,load.epoch);
 assert.equal(t.events[0].some(event=>event.type==='gamePrepare'&&event.epoch===load.target),false);
});

test('only host proposes Load; concurrency, roles and stale metadata cannot change its prior timeline',()=>{
 const t=setup(2),load=requestLoad(t),proposal={type:'gameLoadPropose',revision:t.view().game.controllers.revision,roomRevision:t.view().revision,frame:20,hash:otherHash,identity:'e'.repeat(64),savedAt:1000};
 assert.throws(()=>t.act(1,proposal),/host_only/);assert.throws(()=>t.act(0,proposal),/timeline_change_pending/);
 assert.throws(()=>t.role('slot-2','observer'),/timeline_change_pending/);
 assert.throws(()=>t.act(0,{type:'gameLoadFailed',transactionId:'x'.repeat(22)}),/stale_load/);
 t.act(0,{type:'gameLoadFailed',transactionId:load.id});rollbackLoad(t,load.id);assert.equal(t.view().game.frame,917);
 assert.throws(()=>t.act(0,{...proposal,roomRevision:999}),/room_changed/);
});

test('Load can initialize an unused solo lobby with validated saved progress and a fresh epoch',()=>{
 const t=setup(1);t.load(0);t.act(0,{type:'gameLoadPropose',revision:t.view().game.controllers.revision,roomRevision:t.view().revision,frame:20,hash:otherHash,identity:'e'.repeat(64),savedAt:1000});const load=t.view().game.load!;
 t.act(0,{type:'gameLoadBoundary',transactionId:load.id,frame:0,hash});assert.equal(t.view().game.load!.phase,'staging');
 t.act(0,{type:'gameLoadPrepared',transactionId:load.id,frame:20,hash:otherHash});t.act(0,{type:'gameLoadCommitted',transactionId:load.id,frame:20,hash:otherHash});assert.equal(t.view().started,'shared');assert.equal(t.view().game.epoch,load.epoch);
 assert.equal(t.view().game.status,'resume_ready');t.act(0,{type:'gameResume',epoch:load.epoch});const resumed=t.view().game.epoch!;t.act(0,{type:'gameAck',epoch:resumed,hash:otherHash});t.advance(3000);assert.equal(t.view().game.status,'playing');assert.equal(t.view().game.frame,20);
});

test('Load transfer failure and native preparation deadline preserve exact prior progress',()=>{
 for(const failure of ['transfer','deadline']){
  const t=setup(2),load=requestLoad(t);
  if(failure==='transfer'){const transfer=t.captures().at(-1)!;t.act(1,{type:'gameCheckpointFailed',epoch:load.target,transferId:transfer.transferId});}else t.advance(30000);
  assert.equal(t.view().game.load!.phase,'rolling_back');rollbackLoad(t,load.id);assert.equal(t.view().game.frame,917);assert.equal(t.view().game.epoch,load.epoch);assert.equal(t.view().game.status,'paused');
 }
});

test('reconnected host receives pending rollback again and cannot resume a partially replaced timeline',()=>{
 const t=setup(2),load=requestLoad(t);
 t.rooms.detach(t.sessions[0].token,t.senders[0]);const guestView=t.events[1].filter(e=>e.type==='room').at(-1)!;assert.equal(guestView.type==='room'&&guestView.room.game.load!.phase,'rolling_back');
 t.act(1,{type:'gameLoadRolledBack',transactionId:load.id,frame:917,hash});const previous=t.events[0].filter(e=>e.type==='gameLoadRollback').length;
 t.rooms.attach(t.sessions[0].token,t.senders[0],()=>{});t.act(0,{type:'heartbeat'});assert.equal(t.events[0].filter(e=>e.type==='gameLoadRollback').length,previous+1);
 t.act(0,{type:'gameLoadRolledBack',transactionId:load.id,frame:917,hash});assert.equal(t.view().game.load,undefined);assert.equal(t.view().game.frame,917);assert.equal(t.view().game.epoch,load.epoch);assert.equal(t.view().game.status,'paused');
});

test('ROM selection and manual Load cannot overlap in an unused lobby',()=>{
 const t=setup(1);t.load(0);const selection={type:'beginGameSelection',roomId:t.view().id,intent:randomUUID(),expectedRevision:t.view().revision,fingerprint:{...fingerprint,romSha256:otherHash},title:'Another game'},proposal={type:'gameLoadPropose',revision:t.view().game.controllers.revision,roomRevision:t.view().revision,frame:20,hash:otherHash,identity:'e'.repeat(64),savedAt:1000};
 t.act(0,selection);assert.throws(()=>t.act(0,proposal),/game_selection_pending/);t.act(0,{type:'cancelGameSelection',roomId:t.view().id,intent:selection.intent});
 t.act(0,proposal);assert.throws(()=>t.act(0,{...selection,intent:randomUUID()}),/timeline_change_pending/);assert.equal(t.view().fingerprint!.romSha256,fingerprint.romSha256);assert.equal(t.view().game.load!.phase,'freezing');
});

test('Load supersedes observer catch-up without letting stale completion gate or commit the new timeline',()=>{
 const t=setup(3),epoch=t.begin();t.act(2,{type:'gameObserve',revision:t.view().game.controllers.revision});
 const transfer=t.captures().at(-1)!;t.authorize(transfer,917);
 const proposal={type:'gameLoadPropose',revision:t.view().game.controllers.revision,roomRevision:t.view().revision,frame:20,hash:otherHash,identity:'e'.repeat(64),savedAt:1000};
 assert.throws(()=>t.act(2,proposal),/host_only/);
 assert.equal(t.events[2].some(event=>event.type==='gameSyncStop'&&event.transferId===transfer.transferId),false,'invalid Load cancelled the observer');
 t.act(0,proposal);const load=t.view().game.load!;
 assert.ok(load);assert.deepEqual(load.required,[t.members[0],t.members[1]]);
 assert.ok(t.events[2].some(event=>event.type==='gameSyncStop'&&event.transferId===transfer.transferId));
 assert.throws(()=>t.act(2,{type:'gameCheckpointAck',epoch,transferId:transfer.transferId,frame:917,hash}),/timeline_change_pending/);
 assert.throws(()=>t.act(2,{type:'gameObserved',epoch,transferId:transfer.transferId,frame:917}),/timeline_change_pending/);
 assert.equal(t.view().game.load!.phase,'freezing');
 t.act(0,{type:'gameFrozen',epoch,frame:917,hash});
 for(const who of [0,1])t.act(who,{type:'gameLoadBoundary',transactionId:load.id,frame:917,hash});
 t.act(0,{type:'gameLoadFailed',transactionId:load.id});rollbackLoad(t,load.id);
 assert.equal(t.view().game.load,undefined);assert.equal(t.view().game.status,'paused');
 t.ready(0,{frame:917,fresh:false});t.ready(1,{frame:917,fresh:false});t.act(0,{type:'gameResume',epoch});
 const resumed=t.view().game.epoch!;for(const who of [0,1])t.act(who,{type:'gameAck',epoch:resumed,hash});t.advance(3000);
 assert.equal(t.view().game.status,'playing');assert.notEqual(resumed,epoch);
 t.act(2,{type:'gameObserve',revision:t.view().game.controllers.revision});assert.notEqual(t.captures().at(-1)!.transferId,transfer.transferId);
});

test('observer failure preserves automatic Load staging while controller failure still rolls it back',()=>{
 const t=setup(3),epoch=t.begin();
 t.act(0,{type:'gameLoadPropose',revision:t.view().game.controllers.revision,roomRevision:t.view().revision,frame:20,hash:otherHash,identity:'e'.repeat(64),savedAt:1000});
 const load=t.view().game.load!;
 t.act(2,{type:'gameAbort',epoch,reason:'network'});assert.equal(t.view().game.load!.phase,'freezing');
 t.act(0,{type:'gameFrozen',epoch,frame:917,hash});for(const who of [0,1])t.act(who,{type:'gameLoadBoundary',transactionId:load.id,frame:917,hash});
 assert.equal(t.view().game.load!.phase,'staging');t.act(2,{type:'gameAbort',epoch,reason:'network'});assert.equal(t.view().game.load!.phase,'staging');
 t.act(1,{type:'gameAbort',epoch,reason:'network'});assert.equal(t.view().game.load!.phase,'rolling_back');rollbackLoad(t,load.id);
 assert.equal(t.view().game.load,undefined);assert.equal(t.view().game.status,'paused');
});

test('automatic Load preserves a previously paused game and permits explicit Resume',()=>{
 const t=setup(2),epoch=t.begin();t.act(0,{type:'gamePause',epoch,frame:917,reason:'user'});t.act(0,{type:'gameFrozen',epoch,frame:917,hash});
 t.act(0,{type:'gameLoadPropose',revision:t.view().game.controllers.revision,roomRevision:t.view().revision,frame:20,hash:otherHash,identity:'e'.repeat(64),savedAt:1000});const load=t.view().game.load!;
 for(const who of [0,1])t.act(who,{type:'gameLoadBoundary',transactionId:load.id,frame:917,hash});assert.equal(t.view().game.load!.phase,'staging');
 const transfer=t.captures().at(-1)!;t.act(0,{type:'gameLoadPrepared',transactionId:load.id,frame:20,hash:otherHash});t.act(0,{type:'gameCaptured',epoch:load.epoch,transferId:transfer.transferId,frame:20,hash:otherHash});t.act(1,{type:'gameCheckpointReady',epoch:load.epoch,transferId:transfer.transferId});t.act(1,{type:'gameCheckpointAck',epoch:load.epoch,transferId:transfer.transferId,frame:20,hash:otherHash});
 for(const who of [0,1])t.act(who,{type:'gameLoadCommitted',transactionId:load.id,frame:20,hash:otherHash});
 assert.equal(t.view().game.status,'resume_ready');assert.equal(t.view().game.frame,20);assert.equal(t.view().game.epoch,load.epoch);t.advance(3000);assert.equal(t.view().game.status,'resume_ready');
 t.act(0,{type:'gameResume',epoch:load.epoch});const resumed=t.view().game.epoch!;for(const who of [0,1])t.act(who,{type:'gameAck',epoch:resumed,hash:otherHash});t.advance(3000);assert.equal(t.view().game.status,'playing');
});


test('cartridge replacement freezes old controllers, commits new capability atomically and retains the group',()=>{
 const t=setup(3),oldEpoch=t.begin(),old=t.view();
 const entry=catalogEntry('from-below-1.0'),one:Fingerprint={...fingerprint,romSha256:entry.sha256,cartridge:{format:entry.format,mapper:entry.mapper,submapper:entry.submapper,region:entry.region,bytes:entry.bytes}};
 const intent=randomUUID();t.act(0,{type:'beginGameSelection',roomId:old.id,intent,expectedRevision:old.revision,fingerprint:one,title:entry.title});
 assert.deepEqual(t.view().fingerprint,old.fingerprint,'validation changed active cartridge');
 t.act(0,{type:'gameLoadPropose',selectionIntent:intent,revision:old.game.controllers.revision,roomRevision:old.revision,frame:0,hash:otherHash,identity:'e'.repeat(64),savedAt:1000});
 const load=t.view().game.load!;assert.deepEqual(load.freezeRequired,[t.members[0],t.members[1]]);assert.deepEqual(load.required,[t.members[0]]);
 t.act(0,{type:'gameFrozen',epoch:oldEpoch,frame:917,hash});
 for(const who of [0,1])t.act(who,{type:'gameLoadBoundary',transactionId:load.id,frame:917,hash});
 assert.equal(t.view().game.load!.phase,'staging');assert.equal(t.view().slots[1].role,'player2');
 t.act(0,{type:'gameLoadPrepared',transactionId:load.id,frame:0,hash:otherHash});
 assert.throws(()=>t.act(1,{type:'gameLoadCommitted',transactionId:load.id,frame:0,hash:otherHash}),/controller_only/);
 t.act(0,{type:'gameLoadCommitted',transactionId:load.id,frame:0,hash:otherHash});
 const selected=t.view();assert.deepEqual(selected.fingerprint,one);assert.equal(selected.game.status,'waiting');assert.equal(selected.game.epoch,undefined);assert.equal(selected.started,undefined);assert.equal(selected.established,false);assert.deepEqual(selected.game.ready,[]);
 assert.deepEqual(selected.slots.map(slot=>({id:slot.id,open:slot.open,member:slot.member?.id})),old.slots.map(slot=>({id:slot.id,open:slot.open,member:slot.member?.id})));
 assert.equal(selected.slots[1].role,'observer');assert.equal(selected.slots[2].role,'observer');assert.equal(selected.invite,old.invite);assert.equal(selected.accessRevision,old.accessRevision);assert.equal(selected.occupancy,3);
 assert.throws(()=>t.act(0,{type:'startRoom',roomId:selected.id,membership:t.members[0],fingerprint:one}),/game_prerequisites/);
 assert.equal(t.events[2].some(event=>event.type==='gameLoadHold'||event.type==='gameLoadCommit'),false);
});

test('failed cartridge staging restores the old cartridge, roles and native boundary before retry',()=>{
 const t=setup(3),epoch=t.begin(),old=t.view(),entry=catalogEntry('from-below-1.0');
 const candidate:Fingerprint={...fingerprint,romSha256:entry.sha256,cartridge:{format:entry.format,mapper:entry.mapper,submapper:entry.submapper,region:entry.region,bytes:entry.bytes}};
 const intent=randomUUID();t.act(0,{type:'beginGameSelection',roomId:old.id,intent,expectedRevision:old.revision,fingerprint:candidate,title:entry.title});
 assert.throws(()=>t.act(1,{type:'gameLoadPropose',selectionIntent:intent,revision:old.game.controllers.revision,roomRevision:old.revision,frame:0,hash:otherHash,identity:'e'.repeat(64),savedAt:1000}),/game_selection_changed/);
 assert.throws(()=>t.rooms.beginDownload(t.sessions[2].token,old.id,t.members[2],intent),/game_selection_changed/);
 t.act(0,{type:'gameLoadPropose',selectionIntent:intent,revision:old.game.controllers.revision,roomRevision:old.revision,frame:0,hash:otherHash,identity:'e'.repeat(64),savedAt:1000});
 const id=t.view().game.load!.id;t.act(0,{type:'gameFrozen',epoch,frame:917,hash});
 for(const who of [0,1])t.act(who,{type:'gameLoadBoundary',transactionId:id,frame:917,hash});
 t.act(0,{type:'gameLoadFailed',transactionId:id});assert.equal(t.view().game.load!.phase,'rolling_back');
 for(const who of [0,1])t.act(who,{type:'gameLoadRolledBack',transactionId:id,frame:917,hash});
 const restored=t.view();assert.equal(restored.game.status,'paused');assert.equal(restored.game.frame,917);assert.equal(restored.game.load,undefined);assert.deepEqual(restored.fingerprint,old.fingerprint);assert.deepEqual(restored.slots,old.slots);
 t.act(0,{type:'cancelGameSelection',roomId:old.id,intent});assert.deepEqual(t.view().slots,old.slots);
 t.act(0,{type:'beginGameSelection',roomId:old.id,intent:randomUUID(),expectedRevision:restored.revision,fingerprint:candidate,title:entry.title});
});
