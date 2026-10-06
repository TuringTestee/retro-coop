import {test} from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {CHECKPOINT_TIMEOUT_MS} from '../../../packages/contracts/src/checkpoint.ts';
import {GameClient,type GameplayState} from './game-client.ts';
import type {LocalPlayer} from './player.ts';
import type {Fingerprint,RoomView} from '../../../packages/contracts/src/rooms.ts';
const host='h'.repeat(22),member='m'.repeat(22),peerEpoch='p'.repeat(22),epoch='e'.repeat(22),hash='c'.repeat(64);
const fingerprint:Fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:1,submapper:0,region:'NTSC',bytes:32784}};
const room=(self=member):RoomView=>({id:'r'.repeat(22),label:'Room',visibility:'public',status:'waiting',host:'Host',occupancy:2,openSlots:3,hostReady:true,established:false,chatMembership:self,hostMembership:host,invite:'i'.repeat(22),role:self===host?'host':'member',slot:self===host?'slot-1':'slot-2',revision:1,accessRevision:0,controllerRoles:['player1','player2'],connectionPolicy:'standard',peers:[],reservationIntent:'j'.repeat(22),fingerprint,matches:true,game:{status:'waiting',controllers:{owners:[host,member],revision:1},ready:[],startRequested:false},slots:[{id:'slot-1',role:'player1',open:true,revision:0,member:{id:host,nickname:'Host',connected:true,matches:true,acquisition:'loaded'}},{id:'slot-2',role:'player2',open:true,revision:0,member:{id:member,nickname:'Member',connected:true,matches:true,acquisition:'loaded'}},...(['slot-3','slot-4','slot-5'] as const).map(id=>({id,role:'observer' as const,open:true,revision:0}))]});
function setup(self=member,connected=true){
 const commands:{type:string;[key:string]:unknown}[]=[],updates:GameplayState[]=[],holds:Array<(value:{frame:number;hash:string;fresh:boolean})=>void>=[];let deferHold=false,holdError:Error|undefined,sendHook:((command:{type:string})=>Promise<void>)|undefined;
 const player={isLoaded:()=>true,frameRate:()=>60,holdForGame:()=>holdError?Promise.reject(holdError):deferHold?new Promise(resolve=>holds.push(resolve)):Promise.resolve({frame:0,hash,fresh:true}),cancelPeerCheckpoint(){},sampleGameInput:()=>0,stopGame(){},allowLocalPlay(){},releaseControllers(){}} as unknown as LocalPlayer;
 const game=new GameClient(()=>player,async command=>{commands.push(command);await sendHook?.(command);},state=>updates.push(state));
 const channel={readyState:'open',bufferedAmount:0,send(){},onmessage:undefined} as unknown as RTCDataChannel;
 game.enter(room(self));game.selected(fingerprint);if(connected)game.ready(self===host?member:host,channel,peerEpoch);
 return {game,player,commands,updates,channel,holds,defer:()=>{deferHold=true;},failHold:(error?:Error)=>{holdError=error;},send:(hook:typeof sendHook)=>{sendHook=hook;}};
}
const tick=()=>setImmediate();
test('Ready intent waits for the local peer channel and then reaches the coordinator',async()=>{
 const t=setup(member,false);try{
  t.game.playIntent();await tick();assert.equal(t.commands.some(command=>command.type==='gameReady'),false);
  t.game.ready(host,t.channel,peerEpoch);await tick();assert.equal(t.commands.filter(command=>command.type==='gameReady').length,1);
 }finally{t.game.dispose();}
});
test('paused preparation waits for authoritative file match and retries only retained explicit intent',async()=>{
 const t=setup();try{
  const paused=room();paused.started='shared';paused.game={...paused.game,status:'paused',epoch};paused.matches=false;
  t.game.enter(paused);await t.game.resumeReady();assert.equal(t.commands.length,0);
  t.game.enter({...paused,matches:true});await tick();assert.equal(t.commands.filter(c=>c.type==='gameReady').length,1);
  t.game.enter({...paused,matches:true});await tick();assert.equal(t.commands.filter(c=>c.type==='gameReady').length,1);
  t.game.cancelIntent();t.game.enter(paused);t.game.enter({...paused,matches:true});await tick();assert.equal(t.commands.filter(c=>c.type==='gameReady').length,1);
 }finally{t.game.dispose();}
});
test('failed preparation exposes the reason, stops retrying in the background, and accepts an explicit retry',async()=>{
 const t=setup();try{
  t.failHold(Error('The emulator could not prepare its state.'));
  t.game.playIntent();await tick();
  assert.equal(t.updates.at(-1)?.preparationError,'The emulator could not prepare its state.');
  assert.equal(t.updates.at(-1)?.intent,false);
  t.game.enter(room());await tick();assert.equal(t.commands.filter(command=>command.type==='gameReady').length,0);
  t.failHold();t.game.playIntent();await tick();
  assert.equal(t.updates.at(-1)?.preparationError,undefined);
  assert.equal(t.commands.filter(command=>command.type==='gameReady').length,1);
 }finally{t.game.dispose();}
});
test('rejected readiness can be retried without hiding the error or sending in the background',async()=>{
 const t=setup();try{
  t.send(command=>command.type==='gameReady'?Promise.reject(Error('The lobby service did not respond. Retry or cancel.')):Promise.resolve());
  t.game.playIntent();await tick();
  assert.equal(t.updates.at(-1)?.preparationError,'Lobby service did not respond. Try again.');
  assert.equal(t.updates.at(-1)?.intent,false);
  t.game.enter(room());await tick();assert.equal(t.commands.filter(command=>command.type==='gameReady').length,1);
  t.send(undefined);t.game.playIntent();await tick();
  assert.equal(t.updates.at(-1)?.preparationError,undefined);
  assert.equal(t.commands.filter(command=>command.type==='gameReady').length,2);
 }finally{t.game.dispose();}
});
test('replaced peer channel cannot mutate current game through delayed malformed message',()=>{
 const t=setup(),current={readyState:'open',bufferedAmount:0,send(){}} as unknown as RTCDataChannel;try{
  t.game.ready(host,current,'n'.repeat(22));const count=t.updates.length;t.channel.onmessage!.call(t.channel,new MessageEvent('message',{data:'bad'}));assert.equal(t.updates.length,count);
  current.onmessage!.call(current,new MessageEvent('message',{data:'bad'}));assert.ok(t.updates.length>count);
 }finally{t.game.dispose();}
});
test('completed old readiness cannot overwrite a later membership change',async()=>{
 const t=setup();let finish!:()=>void;t.send(()=>new Promise(resolve=>{finish=resolve;}));try{
  t.game.playIntent();await tick();assert.equal(typeof finish,'function');t.game.enter(undefined);const latest=t.updates.at(-1);finish();await tick();assert.deepEqual(t.updates.at(-1),latest);
 }finally{t.game.dispose();}
});
test('cancelling an in-flight offer releases only that operation and newer readiness remains exclusive',async()=>{
 for(const oldFirst of [true,false]){const t=setup();t.defer();try{
  t.game.playIntent();assert.equal(t.holds.length,1);t.game.cancelIntent();if(oldFirst){t.holds[0]({frame:0,hash,fresh:true});await tick();}
  t.game.playIntent();assert.equal(t.holds.length,2);if(!oldFirst){t.holds[0]({frame:0,hash,fresh:true});await tick();}t.game.retry();assert.equal(t.holds.length,2);
  t.holds[1]({frame:0,hash,fresh:true});await tick();assert.deepEqual(t.commands.map(c=>c.type),['gameUnready','gameReady']);
 }finally{t.game.dispose();}}
});
test('host explicit retry works regardless of previous stop and does not duplicate readiness',async()=>{
 const t=setup(host);try{t.game.handle({type:'gameStop',reason:'Timed out'});t.game.retry();await tick();t.game.enter(room(host));await tick();assert.equal(t.commands.filter(c=>c.type==='gameReady').length,1);}finally{t.game.dispose();}
});
test('wrong selected file cannot prepare until matching file and explicit intent are supplied',async()=>{
 const t=setup();try{t.game.selected({...fingerprint,romSha256:'f'.repeat(64)});t.game.playIntent();await tick();assert.equal(t.commands.length,0);t.game.cancelIntent();t.game.selected(fingerprint);await tick();assert.deepEqual(t.commands.map(c=>c.type),['gameUnready']);t.game.playIntent();await tick();assert.equal(t.commands.at(-1)?.type,'gameReady');assert.equal(t.commands.at(-1)?.roomRevision,1);}finally{t.game.dispose();}
});
test('changing an already prepared member file explicitly revokes its readiness',async()=>{
 const t=setup();try{t.game.playIntent();await tick();assert.equal(t.commands.at(-1)?.type,'gameReady');t.game.selected({...fingerprint,romSha256:'f'.repeat(64)});await tick();assert.deepEqual(t.commands.map(c=>c.type),['gameReady','gameUnready']);}finally{t.game.dispose();}
});
test('file replacement during worker hold invalidates stale readiness before it reaches coordinator',async()=>{
 const t=setup();t.defer();try{t.game.playIntent();t.game.selected({...fingerprint,romSha256:'f'.repeat(64)});t.holds[0]({frame:0,hash,fresh:true});await tick();assert.equal(t.commands.some(c=>c.type==='gameReady'),false);}finally{t.game.dispose();}
});
test('room revision invalidates an unfinished Ready click until the member chooses Ready again',async()=>{
 const t=setup();t.defer();try{
  t.game.playIntent();assert.equal(t.holds.length,1);
  const changed=room();changed.revision=2;changed.slots[1].revision=1;t.game.enter(changed);
  t.holds[0]({frame:0,hash,fresh:true});await tick();
  assert.equal(t.commands.some(c=>c.type==='gameReady'),false);
  assert.equal(t.updates.at(-1)?.intent,false);
  t.game.playIntent();assert.equal(t.holds.length,2);
  t.holds[1]({frame:0,hash,fresh:true});await tick();
  assert.equal(t.commands.at(-1)?.type,'gameReady');assert.equal(t.commands.at(-1)?.roomRevision,2);
 }finally{t.game.dispose();}
});
test('late configured controller offers readiness for activation rather than requesting observer sync',async()=>{
 const t=setup();try{const late=room();late.started='shared';late.established=true;late.game={...late.game,status:'playing',epoch,controllers:{owners:[host,null],revision:2}};t.game.enter(late);t.commands.length=0;t.game.playIntent();await tick();assert.equal(t.commands.some(c=>c.type==='gameObserve'),false);assert.ok(t.commands.some(c=>c.type==='gameReady'&&c.revision===2));}finally{t.game.dispose();}
});

test('prepared timeline retains ordered peer packets arriving before the local Start event',async()=>{
 for(const self of [host,member]){
  const t=setup(self);let clock:Parameters<LocalPlayer['startGame']>[0]|undefined;
  t.player.bindGameEpoch=async()=>{};t.player.startGame=value=>{clock=value;};t.player.wakeGame=()=>{};
  try{
   const controllers=room(self).game.controllers,context={epoch,authority:host,frame:0,hash,delay:6,controllers};
   t.game.handle({type:'gamePrepare',...context});await tick();assert.equal(t.commands.at(-1)?.type,'gameAck');
   const packet=self===host?{kind:'input',epoch,frame:0,mask:0}:{kind:'frame',epoch,frame:0,p1:0,p2:0};
   t.channel.onmessage!.call(t.channel,new MessageEvent('message',{data:JSON.stringify(packet)}));
   assert.equal(clock,undefined,'early transport cannot execute a frame before Start');
   t.game.handle({type:'gameStart',...context});assert.ok(clock);assert.deepEqual((clock as Parameters<LocalPlayer['startGame']>[0]).next(0),{frame:0,p1:0,p2:0});
  }finally{t.game.dispose();}
 }
});

test('host Load validates the selected save and serializes native preparation, commit and final acceptance',async()=>{
 const t=setup(host),id='l'.repeat(22),target='t'.repeat(22),identity='a'.repeat(64),bytes=new ArrayBuffer(82),calls:string[]=[];let finish!:()=>void;
 Object.assign(t.player,{inspectSave:async()=>({identity,hash}),prepareSharedSave:async()=>{calls.push('prepare');await new Promise<void>(resolve=>finish=resolve);return {frame:20,hash};},commitSharedSave:async()=>{calls.push('commit');return {frame:20,hash};},finishSharedSave:async()=>{calls.push('finish');},rollbackSharedSave:async()=>({frame:0,hash})});
 try{
  await t.game.loadSaved({identity,slot:1,savedAt:1000,bytes,frame:20,hash},async()=>true);assert.equal(t.commands.at(-1)?.type,'gameLoadPropose');
  t.game.handle({type:'gameLoadHold',transactionId:id});t.game.enter({...room(host),game:{...room(host).game,load:{id,epoch,phase:'freezing',frame:20,hash,identity:'a'.repeat(64),savedAt:1000,required:[host,member],expiresAt:20000}}});await tick();assert.equal(t.commands.at(-1)?.type,'gameLoadBoundary');
  t.game.handle({type:'gameLoadStage',transactionId:id,epoch:target,frame:20,hash});await tick();
  t.game.handle({type:'gameLoadCommit',transactionId:id,epoch:target,frame:20,hash});await tick();assert.deepEqual(calls,['prepare']);assert.equal(t.commands.some(c=>c.type==='gameLoadCommitted'),false);
  finish();await tick();assert.deepEqual(calls,['prepare','commit']);assert.equal(t.commands.at(-1)?.type,'gameLoadCommitted');
  t.game.handle({type:'gameLoadFinish',transactionId:id});await tick();assert.deepEqual(calls,['prepare','commit','finish']);
 }finally{t.game.dispose();}
});

test('cleared or replaced save cannot stage or commit and late completion cannot authorize a new membership',async()=>{
 const t=setup(host),id='l'.repeat(22),identity='a'.repeat(64),bytes=new ArrayBuffer(82);let valid=true,prepared=0,resolve!:()=>void;
 Object.assign(t.player,{inspectSave:async()=>({identity,hash}),prepareSharedSave:async()=>{prepared++;await new Promise<void>(done=>resolve=done);return {frame:20,hash};},rollbackSharedSave:async()=>({frame:0,hash})});
 try{
  await t.game.loadSaved({identity,slot:1,savedAt:1000,bytes,frame:20,hash},async()=>valid);t.game.handle({type:'gameLoadHold',transactionId:id});t.game.enter({...room(host),game:{...room(host).game,load:{id,epoch,phase:'freezing',frame:20,hash,identity:'a'.repeat(64),savedAt:1000,required:[host,member],expiresAt:20000}}});await tick();valid=false;
  t.game.handle({type:'gameLoadStage',transactionId:id,epoch,frame:20,hash});await tick();assert.equal(prepared,0);assert.equal(t.commands.at(-1)?.type,'gameLoadFailed');
  valid=true;t.game.handle({type:'gameLoadStage',transactionId:id,epoch,frame:20,hash});await tick();assert.equal(prepared,1);
  t.game.enter(undefined);resolve();await tick();assert.equal(t.commands.some(c=>c.type==='gameLoadPrepared'),false);
 }finally{t.game.dispose();}
});

test('Load rollback acknowledges actual native prior state and rejects a mismatched restoration',async()=>{
 for(const matches of [true,false]){const t=setup(host),id='l'.repeat(22);Object.assign(t.player,{rollbackSharedSave:async()=>({frame:917,hash:matches?hash:'f'.repeat(64)})});try{
  t.game.handle({type:'gameLoadHold',transactionId:id});t.game.enter({...room(host),game:{...room(host).game,load:{id,epoch,phase:'freezing',frame:20,hash,identity:'a'.repeat(64),savedAt:1000,required:[host,member],expiresAt:20000}}});await tick();t.game.handle({type:'gameLoadRollback',transactionId:id,epoch,frame:917,hash,reason:'Declined'});await tick();
  assert.equal(t.commands.some(c=>c.type==='gameLoadRolledBack'),matches);assert.equal(t.commands.at(-1)?.type,matches?'gameLoadRolledBack':'gameLoadFailed');
 }finally{t.game.dispose();}}
});

test('Load announcement waits for the matching authoritative view and cannot migrate into a later lobby',async()=>{
 const t=setup(host),id='l'.repeat(22);t.defer();try{
  t.game.handle({type:'gameLoadHold',transactionId:id});await tick();assert.equal(t.holds.length,0);
  const next={...room(host),id:'n'.repeat(22)};t.game.enter(next);await tick();assert.equal(t.holds.length,0);
  t.game.enter({...next,game:{...next.game,load:{id,epoch,phase:'freezing',frame:20,hash,identity:'a'.repeat(64),savedAt:1000,required:[host,member],expiresAt:20000}}});await tick();assert.equal(t.holds.length,0,'stale event was rebound to a new lobby');
 }finally{t.game.dispose();}
});

test('a reconnected controller can acknowledge a resent rollback after local transport cleanup',async()=>{
 const t=setup(),id='l'.repeat(22),view={...room(),game:{...room().game,load:{id,epoch,phase:'rolling_back' as const,frame:20,hash,identity:'a'.repeat(64),savedAt:1000,required:[host,member],expiresAt:20000}}};
 Object.assign(t.player,{rollbackSharedSave:async()=>({frame:917,hash})});try{
  t.game.enter(view);t.game.closed(host);t.game.handle({type:'gameLoadRollback',transactionId:id,epoch,frame:917,hash,reason:'Connection changed'});await tick();assert.equal(t.commands.at(-1)?.type,'gameLoadRolledBack');
  t.game.enter(undefined);const count=t.commands.length;t.game.handle({type:'gameLoadRollback',transactionId:id,epoch,frame:917,hash,reason:'Connection changed'});await tick();assert.equal(t.commands.length,count);
 }finally{t.game.dispose();}
});

test('Load owns async validation exclusively and a cancelled older attempt cannot release a newer request',async()=>{
 const t=setup(host),identity='a'.repeat(64),record={identity,slot:1,savedAt:1000,bytes:new ArrayBuffer(82)},inspections:Array<(value:{identity:string;hash:string})=>void>=[];
 Object.assign(t.player,{inspectSave:()=>new Promise(resolve=>inspections.push(resolve))});try{
  const older=t.game.loadSaved(record,async()=>true);const olderFailure=assert.rejects(older,/Saved progress changed/);
  await assert.rejects(t.game.loadSaved(record,async()=>true),/Another game change/);assert.equal(inspections.length,1);
  t.game.enter(undefined);t.game.enter(room(host));const newer=t.game.loadSaved(record,async()=>true);assert.equal(inspections.length,2);
  inspections[0]({identity,hash});await olderFailure;await assert.rejects(t.game.loadSaved(record,async()=>true),/Another game change/);
  inspections[1]({identity,hash});await newer;assert.equal(t.commands.filter(c=>c.type==='gameLoadPropose').length,1);
 }finally{t.game.dispose();}
});

test('room change during async save-record validation cannot propose the old room after the read resolves',async()=>{
 const t=setup(host),identity='a'.repeat(64);let resolve!:()=>void;
 Object.assign(t.player,{inspectSave:async()=>({identity,hash})});try{
  const request=t.game.loadSaved({identity,slot:1,savedAt:1000,bytes:new ArrayBuffer(82)},async()=>{await new Promise<void>(done=>resolve=done);return true;});const failure=assert.rejects(request,/Saved progress changed/);await tick();t.game.enter(undefined);resolve();await failure;assert.equal(t.commands.some(c=>c.type==='gameLoadPropose'),false);
 }finally{t.game.dispose();}
});

test('unused lobby roster revision retains the same transaction native rollback owner',async()=>{
 const t=setup(host),id='l'.repeat(22);let finish!:(value:{frame:number;hash:string})=>void;
 Object.assign(t.player,{rollbackSharedSave:()=>new Promise(resolve=>finish=resolve),finishSharedSave:async()=>{}});
 const view={...room(host),game:{...room(host).game,load:{id,epoch,phase:'freezing' as const,frame:20,hash,identity:'a'.repeat(64),savedAt:1000,required:[host,member],expiresAt:20000}}};
 try{
  t.game.enter(view);t.game.handle({type:'gameLoadHold',transactionId:id});await tick();
  t.game.handle({type:'gameLoadRollback',transactionId:id,epoch,frame:917,hash,reason:'Roster changed'});await tick();
  t.game.enter({...view,revision:view.revision+1,game:{...view.game,load:{...view.game.load,phase:'rolling_back'}}});
  finish({frame:917,hash});await tick();
  assert.equal(t.commands.at(-1)?.type,'gameLoadRolledBack');
  t.game.handle({type:'gameLoadFinish',transactionId:id});await tick();
  t.game.enter({...room(host),revision:2});t.game.playIntent();await tick();
  assert.equal(t.commands.at(-1)?.type,'gameReady');
 }finally{t.game.dispose();}
});

test('late native rollback cannot acknowledge for a departed membership',async()=>{
 const t=setup(host),id='l'.repeat(22);let finish!:(value:{frame:number;hash:string})=>void;
 Object.assign(t.player,{rollbackSharedSave:()=>new Promise(resolve=>finish=resolve)});
 try{
  t.game.enter({...room(host),game:{...room(host).game,load:{id,epoch,phase:'rolling_back',frame:20,hash,identity:'a'.repeat(64),savedAt:1000,required:[host,member],expiresAt:20000}}});
  t.game.handle({type:'gameLoadRollback',transactionId:id,epoch,frame:917,hash,reason:'Roster changed'});await tick();
  const previous=finish;t.game.enter(undefined);previous({frame:917,hash});await tick();
  assert.equal(t.commands.some(command=>command.type==='gameLoadRolledBack'),false);
 }finally{t.game.dispose();}
});

test('authorized controller checkpoint waits for its connecting transport and ignores stale open after leave',{timeout:5000},async()=>{
 for(const leave of [false,true]){
  const t=setup(host),transfer='t'.repeat(22),sent:unknown[]=[],channel=Object.assign(new EventTarget(),{readyState:'connecting',bufferedAmount:0,send:(value:unknown)=>sent.push(value)}) as unknown as RTCDataChannel;
  const captured=new Promise<void>(resolve=>t.send(async command=>{if(command.type==='gameCaptured')resolve();}));
  Object.assign(t.player,{exportPeerCheckpoint:async()=>({type:'peer-checkpoint-exported',requestId:1,epoch,frame:917,hash,identity:'a'.repeat(64),bytes:new ArrayBuffer(82)})});
  try{
   t.game.enter({...room(host),started:'shared',game:{...room(host).game,status:'paused',epoch}});
   t.game.checkpointChannel(member,channel,peerEpoch);
   t.game.handle({type:'gameCapture',epoch,transferId:transfer,recipient:member,purpose:'controller'});
   await captured;
   assert.ok(t.commands.some(command=>command.type==='gameCaptured'));
   t.game.handle({type:'gameCheckpoint',epoch,transferId:transfer,sender:host,recipient:member,purpose:'controller',frame:917,hash});
   t.game.handle({type:'gameCheckpointSend',epoch,transferId:transfer,recipient:member});await tick();
   assert.equal(t.commands.some(command=>command.type==='gameCheckpointFailed'),false);
   assert.equal(sent.length,0);
   if(leave)t.game.enter(undefined);
   Object.defineProperty(channel,'readyState',{value:'open'});channel.dispatchEvent(new Event('open'));await tick();
   assert.equal(sent.length>0,!leave);
  }finally{t.game.dispose();}
 }
});

test('cancelled, timed-out and closed checkpoint transports cannot send on a late open',{timeout:5000},async context=>{
 for(const reason of ['cancel','timeout','closed']){
  context.mock.timers.enable({apis:['setTimeout']});
  const t=setup(host),transfer='t'.repeat(22),sent:unknown[]=[],channel=Object.assign(new EventTarget(),{readyState:reason==='closed'?'closed':'connecting',bufferedAmount:0,send:(value:unknown)=>sent.push(value)}) as unknown as RTCDataChannel;
  const captured=new Promise<void>(resolve=>t.send(async command=>{if(command.type==='gameCaptured')resolve();}));
  Object.assign(t.player,{exportPeerCheckpoint:async()=>({type:'peer-checkpoint-exported',requestId:1,epoch,frame:917,hash,identity:'a'.repeat(64),bytes:new ArrayBuffer(82)})});
  try{
   t.game.enter({...room(host),started:'shared',game:{...room(host).game,status:'paused',epoch}});t.game.checkpointChannel(member,channel,peerEpoch);
   t.game.handle({type:'gameCapture',epoch,transferId:transfer,recipient:member,purpose:'controller'});
   await captured;
   t.game.handle({type:'gameCheckpoint',epoch,transferId:transfer,sender:host,recipient:member,purpose:'controller',frame:917,hash});
   t.game.handle({type:'gameCheckpointSend',epoch,transferId:transfer,recipient:member});
   if(reason==='cancel')t.game.handle({type:'gameSyncStop',epoch,transferId:transfer,reason:'Cancelled'});
   if(reason==='timeout')context.mock.timers.tick(CHECKPOINT_TIMEOUT_MS+1);
   Object.defineProperty(channel,'readyState',{value:'open'});channel.dispatchEvent(new Event('open'));await tick();
   assert.equal(sent.length,0,reason);
   assert.equal(t.commands.some(command=>command.type==='gameCheckpointFailed'),reason!=='cancel');
  }finally{t.game.dispose();context.mock.timers.reset();}
 }
});

test('leaving settles a pending cartridge replacement and fences its captured native continuation',async()=>{
 const t=setup(host),intent='x'.repeat(22);let current=true;
 Object.assign(t.player,{captureCartridge:async()=>({type:'state-captured',frame:0,hash,identity:'a'.repeat(64),bytes:new ArrayBuffer(82)})});
 const pending=t.game.replaceCartridge(intent,()=>current);await tick();assert.equal(t.commands.at(-1)?.type,'gameLoadPropose');
 current=false;t.game.enter(undefined);await assert.rejects(pending,/Lobby membership changed/);t.game.dispose();
});

test('a cartridge captured after its selection was canceled never proposes a shared swap',async()=>{
 const t=setup(host);let current=true,finish!:(value:unknown)=>void;
 Object.assign(t.player,{captureCartridge:()=>new Promise(resolve=>finish=resolve)});
 const pending=t.game.replaceCartridge('x'.repeat(22),()=>current);current=false;
 finish({frame:0,hash,identity:'a'.repeat(64),bytes:new ArrayBuffer(82)});await assert.rejects(pending,/Game selection changed/);
 assert.equal(t.commands.some(command=>command.type==='gameLoadPropose'),false);t.game.dispose();
});
