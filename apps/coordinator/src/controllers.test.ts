import {test} from 'node:test';
import assert from 'node:assert/strict';
import {GameSession} from './gameplay.ts';
import {parseGameCommand,type GameCommand,type GameEvent,type ControllerAssignment,type RoleTransaction} from '../../../packages/contracts/src/gameplay.ts';
import {parseRoomCommand} from '../../../packages/contracts/src/rooms.ts';
const host='h'.repeat(32),player='p'.repeat(32),observer='o'.repeat(32),hash='a'.repeat(64),requestId='r'.repeat(32);
function setup(){let now=0;const events:GameEvent[]=[];let committed:ControllerAssignment={owners:[host,player],revision:0};const game=new GameSession(()=>now,(_member,event)=>events.push(event),()=>committed={owners:[observer,player],revision:1});const members=[host,player,observer].map(id=>({id,connected:true,loaded:true,transport:true}));game.configure(host,members,committed);const send=(member:string,command:Record<string,unknown>)=>game.handle(member,{...command,...(command.type==='gameReady'?{roomRevision:0}:{}),requestId} as GameCommand);for(const member of [host,player,observer])send(member,{type:'gameReady',revision:0,frame:0,fresh:true,hash,delay:6});game.requestStart();const epoch=game.view().epoch!;for(const member of [host,player])send(member,{type:'gameAck',epoch,hash});const pending:RoleTransaction={id:'t'.repeat(32),revision:1,roles:[{slotId:'slot-1',role:'observer'},{slotId:'slot-3',role:'player1'}],status:'freezing'};return {game,events,send,epoch,pending,members,request(){game.requestRoles({...pending},{owners:[observer,player],revision:1});},advance(){now+=30000;game.sweep();}};}
// Replaces the two-party consent success path: host authorization is exercised in
// slots.test.ts; controller authority commits only after all proposed owners sync.
test('atomic role change preserves old owners until matching checkpoints complete',()=>{
 const t=setup();t.request();assert.throws(()=>t.request(),/role_change_pending/);
 assert.throws(()=>t.send(observer,{type:'gameRoleCancel',transactionId:t.pending.id}),/stale_controllers/);
 assert.throws(()=>t.send(player,{type:'gameReady',revision:0,frame:20,fresh:false,hash,delay:6}),/game_prerequisites/);
 t.send(host,{type:'gameFrozen',epoch:t.epoch,frame:20,hash});
 const captures=t.events.filter(event=>event.type==='gameCapture');assert.equal(captures.length,2);
 for(const [index,capture] of captures.entries()){
  assert.deepEqual(t.game.view().controllers.owners,[host,player]);
  t.send(host,{type:'gameCaptured',epoch:t.epoch,transferId:capture.transferId,frame:20,hash});
  t.send(capture.recipient,{type:'gameCheckpointReady',epoch:t.epoch,transferId:capture.transferId});
  assert.throws(()=>t.send(capture.recipient,{type:'gameCheckpointAck',epoch:t.epoch,transferId:capture.transferId,frame:21,hash}),/stale_checkpoint/);
  t.send(capture.recipient,{type:'gameCheckpointAck',epoch:t.epoch,transferId:capture.transferId,frame:20,hash});
  if(index===0)assert.ok(t.game.view().pending);
 }
 assert.deepEqual(t.game.view().controllers,{owners:[observer,player],revision:1});assert.equal(t.game.view().frame,20);assert.equal(t.game.view().pending,undefined);assert.notEqual(t.game.view().epoch,t.epoch);
 assert.throws(()=>t.send(player,{type:'gameAck',epoch:t.epoch,hash}),/stale_game/);
});
// Decline is no longer a product action. Cancellation, timeout, disconnection and
// changed membership retain their previous-assignment/progress safety obligations.
test('cancel timeout disconnect and membership change cannot reuse failed role authority',()=>{
 for(const action of ['cancel','timeout','disconnect','replacement']){
  const t=setup();t.request();t.send(host,{type:'gameFrozen',epoch:t.epoch,frame:20,hash});
  if(action==='cancel')t.send(host,{type:'gameRoleCancel',transactionId:t.pending.id});
  if(action==='timeout')t.advance();
  if(action==='disconnect')t.game.configure(host,t.members.map(member=>({...member,connected:member.id!==observer})),t.game.view().controllers,1);
  if(action==='replacement')t.game.configure(host,t.members.filter(member=>member.id!==observer),t.game.view().controllers,2);
  assert.deepEqual(t.game.view().controllers.owners,[host,player],action);assert.equal(t.game.view().frame,20);assert.equal(t.game.view().status,'paused');assert.deepEqual(t.game.view().ready,[]);
  assert.throws(()=>t.send(host,{type:'gameRoleRetry',transactionId:'x'.repeat(32)}),/stale_controllers/);
  const old=t.events.find(event=>event.type==='gameCapture')!;assert.equal(old.type,'gameCapture');
  assert.throws(()=>t.send(player,{type:'gameCheckpointAck',epoch:t.epoch,transferId:old.transferId,frame:20,hash}),/stale_checkpoint/);
 }
});
test('retry uses fresh checkpoint authority and cannot consume earlier readiness',()=>{
 const t=setup();t.request();t.send(host,{type:'gameFrozen',epoch:t.epoch,frame:20,hash});const old=t.events.filter(event=>event.type==='gameCapture').map(event=>event.transferId);t.advance();
 t.send(host,{type:'gameRoleRetry',transactionId:t.pending.id});t.send(host,{type:'gameFrozen',epoch:t.epoch,frame:20,hash});
 assert.ok(t.events.filter(event=>event.type==='gameCapture').slice(-2).every(event=>!old.includes(event.transferId)));
 assert.throws(()=>t.send(player,{type:'gameReady',revision:999,frame:20,fresh:false,hash,delay:6}),/stale_controllers/);
 assert.throws(()=>t.send(host,{type:'gameResume',epoch:t.epoch}),/resume_not_ready/);
});
test('wire schema rejects superseded consent and forged role revisions and authority',()=>{
 for(const type of ['gameControllerPropose','gameControllerRespond','gameControllerCancel'])assert.equal(parseGameCommand({type,requestId,peerEpoch:requestId,revision:0,mode:'shared',p1:'guest'}),undefined);
 const command={type:'slotRole',requestId,roomId:requestId,expectedRevision:0,slotId:'slot-3',role:'player1'};assert.ok(parseRoomCommand(command));
 for(const patch of [{role:'coop'},{slotId:'slot-6'},{expectedRevision:-1},{expectedRevision:0.5},{host:true}])assert.equal(parseRoomCommand({...command,...patch}),undefined);
 const ready={type:'gameReady',requestId,revision:1,roomRevision:2,frame:20,fresh:false,hash,delay:6};assert.ok(parseGameCommand(ready));const {revision,...missing}=ready;assert.equal(parseGameCommand(missing),undefined);const {roomRevision,...staleRoom}=ready;assert.equal(parseGameCommand(staleRoom),undefined);assert.equal(parseGameCommand({...ready,controllerRevision:1}),undefined);
});
