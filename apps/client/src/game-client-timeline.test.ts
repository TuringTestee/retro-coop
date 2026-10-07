import {test} from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate,setTimeout as delay} from 'node:timers/promises';
import {GameClient,type GameplayState} from './game-client.ts';
import type {GameDriver,LocalPlayer} from './player.ts';
import type {RoomView,Fingerprint} from '../../../packages/contracts/src/rooms.ts';
import type {GameCommand,GameEvent} from '../../../packages/contracts/src/gameplay.ts';
import {checkpointDigest} from './checkpoint.ts';
import {encodeCheckpointChunk,type CheckpointMetadata} from '../../../packages/contracts/src/checkpoint.ts';
const epoch='e'.repeat(32),peerEpoch='p'.repeat(32),host='h'.repeat(22),member='m'.repeat(22),observer='o'.repeat(22),transferId='t'.repeat(22),hash='c'.repeat(64),identity='d'.repeat(64);
const fingerprint:Fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:0,submapper:0,region:'NTSC',bytes:24592}};
type Command=GameCommand extends infer T?T extends GameCommand?Omit<T,'requestId'>:never:never;
function channel(){const sent:(string|ArrayBuffer)[]=[];const rtc=Object.assign(new EventTarget(),{readyState:'open',bufferedAmount:0,onmessage:undefined,send:(data:string|ArrayBuffer)=>sent.push(data)}) as unknown as RTCDataChannel;return {rtc,sent,receive:(data:unknown)=>rtc.onmessage!.call(rtc,new MessageEvent('message',{data}))};}
async function setup(role:'host'|'member'|'observer',start=917){
 const self=role==='host'?host:role==='member'?member:observer,remote=role==='host'?member:host;
 const commands:Command[]=[],updates:GameplayState[]=[],data=channel(),checkpoint=channel();let frame=start,driver!:GameDriver,drains=0,cancels=0,exports=0,imports=0,stops=0,wakes=0;
 let importHook:((current:()=>boolean)=>Promise<{frame:number;hash:string}>)|undefined,sendHook:((command:Command)=>Promise<void>)|undefined,hashHook:(()=>Promise<{frame:number;hash:string;fresh:boolean}>)|undefined;
 const bytes=new Uint8Array(100).fill(7).buffer;
 const mock={isLoaded:()=>true,frameRate:()=>60,holdForGame:async()=>({hash,frame,fresh:false}),stateHash:()=>hashHook?hashHook():Promise.resolve({hash,frame,fresh:false}),startGame:(value:GameDriver)=>{driver=value;},wakeGame(){wakes++;},setGameInputOwner:(value:boolean)=>{if(driver)driver.ownsInput=value;},sampleGameInput:()=>0,drainGame(){drains++;},stopGame(){stops++;},allowLocalPlay(){},async bindGameEpoch(){},resumeGamePresentation(){},releaseControllers(){},cancelPeerCheckpoint(){cancels++;},exportPeerCheckpoint:async()=>{exports++;return {bytes,hash,identity,epoch,frame};},importPeerCheckpoint:async(_epoch:string,f:number,_bytes:ArrayBuffer,_identity:string,_hash:string,current:()=>boolean)=>{imports++;return importHook?importHook(current):{frame:f,hash};}};
 const game=new GameClient(()=>mock as unknown as LocalPlayer,async command=>{commands.push(command);await sendHook?.(command);},state=>updates.push(state));
 const room:RoomView={id:'r'.repeat(22),label:'Room',visibility:'public',status:'waiting',host:'Host',occupancy:3,openSlots:2,hostReady:true,established:true,started:'shared',chatMembership:self,hostMembership:host,invite:'i'.repeat(22),role:role==='host'?'host':'member',slot:role==='host'?'slot-1':role==='member'?'slot-2':'slot-3',revision:1,accessRevision:0,controllerRoles:['player1','player2'],connectionPolicy:'standard',peers:role==='observer'?[{pairId:'q'.repeat(22),member:host,gameplay:true,status:'connected',policy:'standard',epoch:peerEpoch}]:[],reservationIntent:'j'.repeat(22),fingerprint,matches:true,game:{status:role==='observer'?'playing':'paused',epoch,protocol:2 as const,controllers:{owners:[host,member],revision:1},ready:[],startRequested:false},slots:[{id:'slot-1',role:'player1',open:true,revision:0,member:{id:host,nickname:'Host',connected:true,matches:true,acquisition:'loaded'}},{id:'slot-2',role:'player2',open:true,revision:0,member:{id:member,nickname:'Member',connected:true,matches:true,acquisition:'loaded'}},{id:'slot-3',role:'observer',open:true,revision:0,member:{id:observer,nickname:'Observer',connected:true,matches:true,acquisition:'loaded'}},...(['slot-4','slot-5'] as const).map(id=>({id,role:'observer' as const,open:true,revision:0}))]};
 game.enter(room);game.selected(fingerprint);game.ready(remote,data.rtc,peerEpoch);game.checkpointChannel(remote,checkpoint.rtc,peerEpoch);
 const context={epoch,authority:host,hash,frame:start,protocol:2 as const,controllers:room.game.controllers};
 if(role!=='observer'){game.playIntent();game.handle({type:'gamePrepare',...context});await setImmediate();game.handle({type:'gameStart',...context});assert.ok(driver);}
 const spec:Extract<GameEvent,{type:'gameCheckpoint'}>={type:'gameCheckpoint',epoch,transferId,sender:host,recipient:role==='host'?member:self,purpose:role==='observer'?'live':'controller',frame:start,hash};
 return {game,room,commands,updates,data,checkpoint,bytes,spec,get driver(){return driver;},stats:()=>({drains,cancels,exports,imports,stops,wakes}),complete:(f:number)=>{frame=f+1;driver.committed(f);},setImport:(hook:typeof importHook)=>{importHook=hook;},setSend:(hook:typeof sendHook)=>{sendHook=hook;},setHash:(hook:typeof hashHook)=>{hashHook=hook;}};
}
const flush=async()=>{for(let i=0;i<4;i++)await setImmediate();};
test('native guest failure remains a manual retry across ordinary room publications',async()=>{
 const h=await setup('observer');try{h.game.handle(h.spec);await deliver(h);h.data.receive(JSON.stringify({kind:'live',epoch,transferId,frame:917,hash}));await flush();
  h.game.handle({type:'gameLive',epoch,transferId,recipient:observer,frame:917,hash});h.driver.pause('network');await flush();
  const before=h.commands.filter(command=>command.type==='gameObserve').length;
  h.game.enter({...h.room,revision:2});h.game.enter({...h.room,revision:3});await flush();assert.equal(h.commands.filter(command=>command.type==='gameObserve').length,before);
  h.game.retry();await flush();assert.equal(h.commands.filter(command=>command.type==='gameObserve').length,before+1);
 }finally{h.game.dispose();}
});
async function until(done:()=>boolean){const deadline=Date.now()+1000;while(!done()){if(Date.now()>=deadline)assert.fail('Asynchronous checkpoint did not settle');await delay(1);}}
async function deliver(h:Awaited<ReturnType<typeof setup>>,overrides:Partial<CheckpointMetadata>={},wait=true){
 const metadata:CheckpointMetadata={transferId,sender:host,recipient:h.spec.recipient,epoch,frame:917,identity,hash,digest:await checkpointDigest(h.bytes),byteLength:h.bytes.byteLength,...overrides};
 h.checkpoint.receive(JSON.stringify(metadata));h.checkpoint.receive(encodeCheckpointChunk(metadata.transferId,0,new Uint8Array(h.bytes)));
 if(wait)await until(()=>h.stats().imports>0||h.commands.some(x=>x.type==='gameCheckpointFailed'));await flush();
}
function remoteInput(h:Awaited<ReturnType<typeof setup>>,sequence:number,mask:number){h.driver.sample?.(0);const lease=h.data.sent.map(raw=>JSON.parse(raw as string)).findLast(packet=>packet.kind==='lease');assert.ok(lease);h.data.receive(JSON.stringify({kind:'input',epoch,revision:lease.revision,generation:lease.generation,lease:lease.lease,sequence,mask,release:false}));}
test('explicit host freeze retains the last completed frame while remote input is absent',async()=>{
 const h=await setup('host');try{assert.deepEqual(h.driver.next(0),{frame:917,p1:0,p2:0});h.game.handle({type:'gameFreeze',epoch,reason:'Owner left'});await flush();assert.deepEqual(h.commands.filter(x=>x.type==='gameFrozen'),[{type:'gameFrozen',epoch,frame:917,hash}]);assert.equal(h.driver.next(255),undefined);assert.equal(h.stats().drains,0);assert.equal(h.data.sent.filter(raw=>JSON.parse(raw as string).kind==='frame').length,0);}finally{h.game.dispose();}
});
test('replica drains only received committed vectors and cannot run ahead of authority fence',async()=>{
 const h=await setup('member');try{assert.equal(h.driver.next(255),undefined);h.game.handle({type:'gamePauseAt',epoch,frame:919,hash,reason:'Pause'});assert.equal(h.stats().drains,1);assert.equal(h.driver.next(255),undefined);
  for(let frame=917;frame<919;frame++){h.data.receive(JSON.stringify({kind:'frame',epoch,stream:epoch,revision:1,frame,p1:3,p2:5}));assert.deepEqual(h.driver.next(255),{frame,p1:3,p2:5});h.complete(frame);}await flush();assert.equal(h.driver.next(255),undefined);assert.deepEqual(h.commands.filter(x=>x.type==='gamePaused'),[{type:'gamePaused',epoch,frame:919,hash}]);assert.ok(h.data.sent.every(x=>typeof x==='string'&&JSON.parse(x).kind==='input'));
 }finally{h.game.dispose();}
});
test('authority captures exact state but waits for receiver readiness before sending checkpoint bytes',async()=>{
 const h=await setup('host');try{
  h.game.handle({type:'gameCapture',epoch,transferId,recipient:member,purpose:'controller'});await until(()=>h.commands.some(c=>c.type==='gameCaptured'));assert.equal(h.stats().exports,1);assert.equal(h.checkpoint.sent.length,0);
  h.game.handle(h.spec);h.game.handle({type:'gameCheckpointSend',epoch,transferId:'x'.repeat(22),recipient:member});await flush();assert.equal(h.checkpoint.sent.length,0);
  h.game.handle({type:'gameCheckpointSend',epoch,transferId,recipient:member});assert.equal(h.checkpoint.sent.length,2);const metadata=JSON.parse(h.checkpoint.sent[0] as string) as CheckpointMetadata;assert.equal(metadata.sender,host);assert.equal(metadata.recipient,member);assert.equal(metadata.frame,917);assert.equal(metadata.digest,await checkpointDigest(h.bytes));
 }finally{h.game.dispose();}
});
test('recipient acknowledges exact restored state; wrong member fails before worker import',async()=>{
 for(const wrong of [false,true]){const h=await setup('member');try{h.game.handle(h.spec);await flush();assert.deepEqual(h.commands.filter(c=>c.type==='gameCheckpointReady'),[{type:'gameCheckpointReady',epoch,transferId}]);await deliver(h,wrong?{recipient:'z'.repeat(22)}:{});assert.equal(h.stats().imports,wrong?0:1);assert.deepEqual(h.commands.filter(c=>c.type==='gameCheckpointAck'),wrong?[]:[{type:'gameCheckpointAck',epoch,transferId,frame:917,hash}]);if(wrong)assert.equal(h.commands.at(-1)?.type,'gameCheckpointFailed');}finally{h.game.dispose();}}
});
test('cancel or room departure invalidates held import authorization and suppresses stale acknowledgement',async()=>{
 for(const leave of [false,true]){const h=await setup('member');let finish!:(value:{frame:number;hash:string})=>void,current!:()=>boolean;try{h.setImport(check=>{current=check;return new Promise(resolve=>{finish=resolve;});});h.game.handle(h.spec);await deliver(h);assert.equal(current(),true);const before=h.stats().cancels;if(leave)h.game.enter(undefined);else h.game.cancelIntent();assert.equal(current(),false);assert.ok(h.stats().cancels>before);finish({frame:917,hash});await flush();assert.equal(h.commands.some(c=>c.type==='gameCheckpointAck'),false);}finally{h.game.dispose();}}
});
test('oversized and excessive queued checkpoint packets fail before allocation or import',async()=>{
 for(const flood of [false,true]){const h=await setup('observer');try{h.game.handle(h.spec);await flush();if(flood){const chunk=encodeCheckpointChunk(transferId,0,new Uint8Array([1]));for(let i=0;i<257;i++)h.checkpoint.receive(chunk);}else h.checkpoint.receive(new ArrayBuffer(12289));await flush();assert.equal(h.stats().imports,0);assert.equal(h.commands.at(-1)?.type,'gameCheckpointFailed');assert.equal(h.commands.some(c=>c.type==='gameAbort'||c.type==='gamePause'),false);}finally{h.game.dispose();}}
});
test('failed old import and stale transfer packets cannot cancel newer checkpoint authorization',async()=>{
 const h=await setup('member');let reject!:(error:Error)=>void;try{h.setImport(()=>new Promise((_resolve,no)=>{reject=no;}));h.game.handle(h.spec);await deliver(h);const next={...h.spec,transferId:'n'.repeat(22)};h.game.handle(next);reject(Error('Cancelled old import'));await flush();await deliver(h,{},false);assert.equal(h.commands.some(c=>c.type==='gameCheckpointFailed'),false);h.setImport(undefined);await deliver(h,{transferId:next.transferId});await until(()=>h.commands.some(c=>c.type==='gameCheckpointAck'&&c.transferId===next.transferId));}finally{h.game.dispose();}
});
test('late old readiness rejection preserves replacement transfer through its exact acknowledgement',async()=>{
 const h=await setup('member'),replacement='r'.repeat(22);let reject!:(error:Error)=>void;try{h.setSend(command=>command.type==='gameCheckpointReady'&&command.transferId===transferId?new Promise((_resolve,no)=>{reject=no;}):Promise.resolve());h.game.handle(h.spec);await flush();assert.equal(typeof reject,'function');h.game.handle({...h.spec,transferId:replacement});await flush();const cancels=h.stats().cancels,latest=h.updates.at(-1);reject(Error('Old readiness failed'));await flush();assert.equal(h.stats().cancels,cancels);assert.deepEqual(h.updates.at(-1),latest);assert.equal(h.commands.some(c=>c.type==='gameCheckpointFailed'),false);await deliver(h,{transferId:replacement});assert.deepEqual(h.commands.filter(c=>c.type==='gameCheckpointAck'),[{type:'gameCheckpointAck',epoch,transferId:replacement,frame:917,hash}]);}finally{h.game.dispose();}
});
test('passive observer imports then catches up silently on committed vectors without controller input',async()=>{
 const h=await setup('observer');try{assert.ok(h.commands.some(c=>c.type==='gameObserve'));h.game.handle(h.spec);await deliver(h);assert.equal(h.driver.ownsInput,false);assert.equal(h.driver.silent?.(),true);assert.equal(h.driver.next(255),undefined);
  for(let frame=917;frame<920;frame++)h.data.receive(JSON.stringify({kind:'frame',epoch,stream:transferId,revision:1,frame,p1:1,p2:2}));h.data.receive(JSON.stringify({kind:'live',epoch,transferId,frame:920,hash}));
  assert.equal(h.commands.some(c=>c.type==='gameObserved'),false);for(let frame=917;frame<920;frame++){assert.deepEqual(h.driver.next(255),{frame,p1:1,p2:2});h.complete(frame);}await flush();assert.equal(h.driver.silent?.(),false);assert.deepEqual(h.commands.filter(c=>c.type==='gameObserved'),[{type:'gameObserved',epoch,transferId,frame:920,hash}]);assert.equal(h.data.sent.length,0);assert.equal(h.updates.at(-1)?.synchronizing,true);h.game.handle({type:'gameLive',epoch,transferId,recipient:observer,frame:920,hash});assert.equal(h.updates.at(-1)?.status,'Observing the current game.');
 }finally{h.game.dispose();}
});
test('observer wrong-order frames fail only its synchronization and never request a room pause',async()=>{
 const h=await setup('observer');try{h.game.handle(h.spec);await deliver(h);h.data.receive(JSON.stringify({kind:'frame',epoch,stream:transferId,revision:1,frame:918,p1:0,p2:0}));await flush();assert.equal(h.commands.at(-1)?.type,'gameCheckpointFailed');assert.equal(h.commands.some(c=>c.type==='gamePause'||c.type==='gameAbort'),false);assert.equal(h.driver.next(0),undefined);}finally{h.game.dispose();}
});
test('current committed packets and completed state hashes wake existing frame owner without polling',async()=>{
 const h=await setup('member',119);let finish!:(value:{frame:number;hash:string;fresh:boolean})=>void;try{h.setHash(()=>new Promise(resolve=>{finish=resolve;}));h.data.receive(JSON.stringify({kind:'frame',epoch:'z'.repeat(22),stream:epoch,revision:1,frame:119,p1:0,p2:0}));assert.equal(h.stats().wakes,0);h.data.receive(JSON.stringify({kind:'frame',epoch,stream:epoch,revision:1,frame:119,p1:0,p2:0}));assert.equal(h.stats().wakes,1);assert.equal(h.driver.next(0)?.frame,119);h.complete(119);assert.equal(h.driver.next(0),undefined);finish({frame:120,hash,fresh:false});await flush();assert.equal(h.stats().wakes,2);}finally{h.game.dispose();}
});
test('removed observer channel callbacks cannot disturb ongoing host authority',async()=>{
 const h=await setup('host'),other=channel();try{h.game.ready(observer,other.rtc,peerEpoch);const stops=h.stats().stops;h.game.enter({...h.room,slots:h.room.slots.map(slot=>slot.member?.id===observer?{...slot,member:undefined}:slot)});other.receive('obsolete malformed packet');assert.equal(h.stats().stops,stops);assert.equal(h.commands.some(c=>c.type==='gamePause'||c.type==='gameAbort'),false);h.data.receive(JSON.stringify({kind:'input',epoch,frame:917,mask:0}));assert.deepEqual(h.driver.next(0),{frame:917,p1:0,p2:0});}finally{h.game.dispose();}
});
test('authority replays observer history then isolates a slow observer without blocking controller commits',async()=>{
 const h=await setup('host'),observerData=channel(),observerCheckpoint=channel();try{
  h.game.ready(observer,observerData.rtc,peerEpoch);h.game.checkpointChannel(observer,observerCheckpoint.rtc,peerEpoch);
  const request={type:'gameCapture' as const,epoch,transferId,recipient:observer,purpose:'live' as const};h.game.handle(request);await flush();assert.equal(h.stats().exports,0);
  remoteInput(h,1,2);assert.equal(h.driver.next(1)?.frame,917);h.complete(917);await until(()=>h.commands.some(c=>c.type==='gameCaptured'));
  h.game.handle({...h.spec,recipient:observer,purpose:'live'});h.game.handle({type:'gameCheckpointSend',epoch,transferId,recipient:observer});h.game.handle({type:'gameCatchup',epoch,transferId,recipient:observer,frame:917});await flush();
  assert.deepEqual(observerData.sent.map(raw=>JSON.parse(raw as string)),[{kind:'frame',epoch,stream:transferId,revision:1,frame:917,p1:1,p2:2},{kind:'live',epoch,transferId,frame:918,hash}]);
  Object.defineProperty(observerData.rtc,'bufferedAmount',{value:65537,configurable:true});remoteInput(h,2,4);assert.equal(h.driver.next(1)?.frame,918);h.complete(918);
  assert.equal(h.commands.some(c=>c.type==='gamePause'||c.type==='gameAbort'),false);assert.equal(h.updates.at(-1)?.frame,919);assert.equal(h.data.sent.map(raw=>JSON.parse(raw as string)).findLast(packet=>packet.kind==='frame').frame,918);assert.equal(observerData.sent.length,2);
 }finally{h.game.dispose();}
});
test('observer epoch change discards old timeline and requests a fresh passive checkpoint',async()=>{
 const h=await setup('observer');try{h.game.handle(h.spec);await deliver(h);h.data.receive(JSON.stringify({kind:'live',epoch,transferId,frame:917,hash}));await flush();const before=h.commands.filter(c=>c.type==='gameObserve').length;
  h.game.enter({...h.room,game:{...h.room.game,epoch:'n'.repeat(22),controllers:{...h.room.game.controllers,revision:2}}});await flush();assert.equal(h.commands.filter(c=>c.type==='gameObserve').length,before+1);assert.equal(h.driver.next(255),undefined);assert.equal(h.commands.some(c=>c.type==='gamePause'||c.type==='gameAbort'),false);
 }finally{h.game.dispose();}
});
test('passive replay queue stays bounded and overflow fails only that observer',async()=>{
 const h=await setup('observer');try{h.game.handle(h.spec);await deliver(h);for(let i=0;i<=2048;i++)h.data.receive(JSON.stringify({kind:'frame',epoch,stream:transferId,revision:1,frame:917+i,p1:0,p2:0}));await flush();assert.equal(h.commands.at(-1)?.type,'gameCheckpointFailed');assert.equal(h.commands.some(c=>c.type==='gamePause'||c.type==='gameAbort'),false);assert.equal(h.driver.next(0),undefined);}finally{h.game.dispose();}
});
test('observer replay waits for an in-flight interval hash without skipping that hash',async()=>{
 const h=await setup('host',119),other=channel();let finish!:(value:{frame:number;hash:string;fresh:boolean})=>void;
 try{h.game.ready(observer,other.rtc,peerEpoch);h.setHash(()=>new Promise(resolve=>{finish=resolve;}));
  h.game.handle({type:'gameCapture',epoch,transferId,recipient:observer,purpose:'live'});
  remoteInput(h,1,2);assert.equal(h.driver.next(0)?.frame,119);h.complete(119);
  await until(()=>h.commands.some(command=>command.type==='gameCaptured'));
  h.game.handle({type:'gameCatchup',epoch,transferId,recipient:observer,frame:119});assert.equal(other.sent.length,0);
  finish({frame:120,hash,fresh:false});await flush();
  assert.deepEqual(other.sent.map(value=>JSON.parse(value as string)),[{kind:'frame',epoch,stream:transferId,revision:1,frame:119,p1:0,p2:2},{kind:'hash',epoch,stream:transferId,frame:120,hash},{kind:'live',epoch,transferId,frame:120,hash}]);
 }finally{h.game.dispose();}
});
test('observer retries a new epoch even when prior synchronization stopped before a scheduler existed',async()=>{
 const h=await setup('observer');try{const before=h.commands.filter(c=>c.type==='gameObserve').length;
  h.game.handle({type:'gameSyncStop',epoch,transferId,reason:'Game epoch is changing.'});
  const next='n'.repeat(22);h.game.enter({...h.room,game:{...h.room.game,epoch:next}});await flush();
  assert.equal(h.commands.filter(c=>c.type==='gameObserve').length,before+1);assert.equal(h.updates.at(-1)?.synchronizing,true);
 }finally{h.game.dispose();}
});

test('pause arriving during observer import retains its fence and drains the same epoch to the exact boundary',async()=>{
 const h=await setup('observer');let finish!:(value:{frame:number;hash:string})=>void;
 try{
  h.setImport(()=>new Promise(resolve=>{finish=resolve;}));h.game.handle(h.spec);await deliver(h);
  h.game.handle({type:'gamePauseAt',epoch,frame:919,hash,reason:'User pause'});
  finish({frame:917,hash});await flush();
  for(let frame=917;frame<919;frame++)h.data.receive(JSON.stringify({kind:'frame',epoch,stream:transferId,revision:1,frame,p1:1,p2:2}));
  h.data.receive(JSON.stringify({kind:'live',epoch,transferId,frame:919,hash}));
  for(let frame=917;frame<919;frame++){assert.deepEqual(h.driver.next(255),{frame,p1:1,p2:2});h.complete(frame);}await flush();
  assert.equal(h.driver.next(255),undefined);assert.ok(h.commands.some(c=>c.type==='gamePaused'&&c.frame===919));assert.ok(h.commands.some(c=>c.type==='gameObserved'&&c.frame===919));assert.equal(h.commands.some(c=>c.type==='gameCheckpointFailed'),false);
 }finally{h.game.dispose();}
});

test('cancelled observer completion cannot abort a newer Load after its acknowledgment rejects',async()=>{
 for(const replacement of ['cancel','transfer','membership'] as const){const h=await setup('observer');let reject!:(error:Error)=>void;try{
  h.setSend(command=>command.type==='gameObserved'?new Promise((_resolve,no)=>{reject=no;}):Promise.resolve());
  h.game.handle(h.spec);await deliver(h);h.data.receive(JSON.stringify({kind:'live',epoch,transferId,frame:917,hash}));
  await until(()=>typeof reject==='function');
  if(replacement==='cancel')h.game.handle({type:'gameSyncStop',epoch,transferId,reason:'Waiting for the game to finish changing.'});
  else if(replacement==='transfer'){h.game.handle({...h.spec,transferId:'n'.repeat(22)});await flush();}
  else h.game.enter(undefined);
  const latest=h.updates.at(-1),stops=h.stats().stops;reject(Error('timeline_change_pending'));await flush();
  assert.equal(h.commands.some(command=>command.type==='gameAbort'),false);assert.equal(h.stats().stops,stops);assert.deepEqual(h.updates.at(-1),latest);
 }finally{h.game.dispose();}}
});

test('recovering P2 remains neutral until exact live acknowledgment then samples fresh assigned input',async()=>{
 const h=await setup('member');try{
  const spec={...h.spec,purpose:'live' as const};h.game.handle(spec);await deliver(h);assert.equal(h.driver.ownsInput,false);
  h.data.receive(JSON.stringify({kind:'live',epoch,transferId,frame:917,hash}));await flush();assert.ok(h.commands.some(command=>command.type==='gameObserved'&&command.hash===hash));assert.equal(h.driver.ownsInput,false);
  h.game.handle({type:'gameLive',epoch,transferId:'x'.repeat(22),recipient:member,frame:917,hash});assert.equal(h.driver.ownsInput,false);
  h.game.handle({type:'gameLive',epoch,transferId,recipient:member,frame:917,hash});assert.equal(h.driver.ownsInput,true);
  const lease={kind:'lease',epoch,revision:1,generation:peerEpoch,lease:'l'.repeat(32),expiresAt:3000};h.data.receive(JSON.stringify(lease));h.driver.sample?.(2);
  assert.ok(h.data.sent.map(raw=>JSON.parse(raw as string)).some(packet=>packet.kind==='input'&&packet.mask===2&&packet.lease===lease.lease));
 }finally{h.game.dispose();}
});

test('remote control sampling continues while replica has no confirmed frame to replay',async()=>{
 const h=await setup('member');try{
  const lease={kind:'lease',epoch,revision:1,generation:peerEpoch,lease:'l'.repeat(32),expiresAt:3000};h.data.receive(JSON.stringify(lease));h.driver.sample?.(1);h.driver.sample?.(0);assert.equal(h.driver.next(0),undefined);
  const input=h.data.sent.map(raw=>JSON.parse(raw as string)).filter(packet=>packet.kind==='input');assert.deepEqual(input.slice(-2).map(packet=>packet.mask),[1,0]);assert.ok(input.at(-1).sequence>input.at(-2).sequence);
 }finally{h.game.dispose();}
});

test('an old hash stream after successful live retry cannot disturb current host delivery',async()=>{
 const h=await setup('host',119);try{h.game.enter({...h.room,game:{...h.room.game,status:'playing'}});
  h.game.handle({type:'gameCapture',epoch,transferId,recipient:member,purpose:'live'});h.driver.next(0);h.complete(119);await flush();
  h.game.handle({type:'gameCatchup',epoch,transferId,recipient:member,frame:120});await flush();
  h.game.handle({type:'gameLive',epoch,transferId,recipient:member,frame:120,hash});const before=h.commands.filter(command=>command.type==='gameResynchronize').length;
  h.data.receive(JSON.stringify({kind:'hash',epoch,stream:epoch,frame:120,hash:'0'.repeat(64)}));await flush();assert.equal(h.commands.filter(command=>command.type==='gameResynchronize').length,before);assert.equal(h.driver.next(0)?.frame,120);
  h.data.receive(JSON.stringify({kind:'hash',epoch,stream:transferId,frame:120,hash:'0'.repeat(64)}));await flush();assert.equal(h.commands.filter(command=>command.type==='gameResynchronize').length,before+1);
 }finally{h.game.dispose();}
});
