import {test} from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate,setTimeout as delay} from 'node:timers/promises';
import {GameClient,type GameplayState} from './game-client.ts';
import type {GameDriver,LocalPlayer} from './player.ts';
import type {RoomView} from '../../../packages/contracts/src/rooms.ts';
import type {GameCommand,GameEvent} from '../../../packages/contracts/src/gameplay.ts';
import {checkpointDigest} from './checkpoint.ts';
import {encodeCheckpointChunk,type CheckpointMetadata} from '../../../packages/contracts/src/checkpoint.ts';
const epoch='e'.repeat(32),peerEpoch='p'.repeat(32),host='h'.repeat(22),guest='g'.repeat(22),transferId='t'.repeat(22),hash='c'.repeat(64),identity='d'.repeat(64);
const fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:0,submapper:0,region:'NTSC',bytes:24592}} as const;
function channel(){const sent:(string|ArrayBuffer)[]=[];const rtc={readyState:'open',bufferedAmount:0,onmessage:undefined,send:(data:string|ArrayBuffer)=>sent.push(data)} as unknown as RTCDataChannel;return {rtc,sent,receive:(data:unknown)=>rtc.onmessage!.call(rtc,new MessageEvent('message',{data}))};}
async function setup(role:'host'|'guest',start=917){
 const commands:Omit<GameCommand,'requestId'>[]=[],updates:GameplayState[]=[],data=channel(),checkpoint=channel();let frame=start,driver!:GameDriver,drains=0,cancels=0,exports=0,imports=0;
 let importHook:((current:()=>boolean)=>Promise<{frame:number;hash:string}>)|undefined;
 const bytes=new Uint8Array(100).fill(7).buffer;
 const mock={frameRate:()=>60,holdForGame:async()=>({hash,frame,fresh:false}),stateHash:async()=>({hash,frame,fresh:false}),startGame:(value:GameDriver)=>{driver=value;},wakeGame(){},sampleGameInput:()=>0,drainGame(){drains++;},stopGame(){},allowLocalPlay(){},releaseControllers(){},cancelPeerCheckpoint(){cancels++;},exportPeerCheckpoint:async()=>{exports++;return {bytes,hash,identity,epoch,frame};},importPeerCheckpoint:async(_epoch:string,f:number,_bytes:ArrayBuffer,_identity:string,_hash:string,current:()=>boolean)=>{imports++;return importHook?importHook(current):{frame:f,hash};}};
 const game=new GameClient(()=>mock as unknown as LocalPlayer,async command=>{commands.push(command);},state=>updates.push(state));
 const room={id:'room',hostMembership:host,guestMembership:guest,role,matches:true,fingerprint,peer:{epoch:peerEpoch},established:true,game:{status:'paused',epoch}} as RoomView;
 game.enter(room);game.selected(fingerprint);game.playIntent();game.ready(data.rtc,peerEpoch);game.checkpointChannel(checkpoint.rtc,peerEpoch);
 game.handle({type:'gamePrepare',peerEpoch,epoch,hash,delay:6,frame:start});await setImmediate();game.handle({type:'gameStart',peerEpoch,epoch,delay:6,frame:start});assert.ok(driver,'start barrier installed the real frame driver');
 const spec:Extract<GameEvent,{type:'gameCheckpoint'}>={type:'gameCheckpoint',peerEpoch,epoch,transferId,frame:start,hash};
 return {game,commands,updates,data,checkpoint,driver,bytes,spec,stats:()=>({drains,cancels,exports,imports}),complete:(f:number)=>{frame=f+1;driver.committed(f);},setImport:(hook:typeof importHook)=>{importHook=hook;}};
}
const flush=async()=>{for(let i=0;i<4;i++)await setImmediate();};
async function until(done:()=>boolean){const deadline=Date.now()+1000;while(!done()){if(Date.now()>=deadline)assert.fail("Asynchronous checkpoint did not settle");await delay(1);}}

test('stalled host freezes at the last completed frame without another packet from missing owner',async()=>{
 const h=await setup('host');try{
  assert.equal(h.driver.next(0),undefined);
  h.game.handle({type:'gameFreeze',epoch,reason:'Owner disconnected'});await flush();
  assert.deepEqual(h.commands.filter(x=>x.type==='gameFrozen'),[{type:'gameFrozen',epoch,frame:917,hash}]);
  assert.equal(h.driver.next(255),undefined);assert.equal(h.stats().drains,0);assert.equal(h.data.sent.length,0,'freeze must not invent another committed frame');
 }finally{h.game.dispose();}
});

test('replica drains only received committed vectors to the authority fence and never runs ahead',async()=>{
 const h=await setup('guest');try{
  assert.equal(h.driver.next(255),undefined);h.game.handle({type:'gamePauseAt',epoch,frame:919,reason:'Pause'});assert.equal(h.stats().drains,1);
  assert.equal(h.driver.next(255),undefined);
  for(let frame=917;frame<919;frame++){
   h.data.receive(JSON.stringify({kind:'frame',epoch,frame,p1:3,p2:5}));assert.deepEqual(h.driver.next(255),{frame,p1:3,p2:5});h.complete(frame);
  }
  await flush();assert.equal(h.driver.next(255),undefined);assert.deepEqual(h.commands.filter(x=>x.type==='gamePaused'),[{type:'gamePaused',epoch,frame:919,hash}]);
  assert.ok(h.data.sent.every(x=>typeof x==='string'&&JSON.parse(x).kind==='input'),'replica never broadcasts authoritative frame vectors');
 }finally{h.game.dispose();}
});

test('checkpoint host waits for authorized receiver readiness before exporting or sending',async()=>{
 const h=await setup('host');try{
  h.game.handle(h.spec);await flush();assert.equal(h.stats().exports,0);assert.equal(h.checkpoint.sent.length,0);
  h.game.handle({type:'gameCheckpointSend',epoch,transferId:'x'.repeat(22)});await flush();assert.equal(h.stats().exports,0);
  h.game.handle({type:'gameCheckpointSend',epoch,transferId});await until(()=>h.checkpoint.sent.length===2);assert.equal(h.stats().exports,1);assert.equal(h.checkpoint.sent.length,2);
  const metadata=JSON.parse(h.checkpoint.sent[0] as string) as CheckpointMetadata;
  assert.equal(metadata.sender,host);assert.equal(metadata.recipient,guest);assert.equal(metadata.frame,917);assert.equal(metadata.digest,await checkpointDigest(h.bytes));assert.ok(h.checkpoint.sent[1] instanceof ArrayBuffer);
 }finally{h.game.dispose();}
});

async function deliver(h:Awaited<ReturnType<typeof setup>>,overrides:Partial<CheckpointMetadata>={}){
 const metadata:CheckpointMetadata={transferId,sender:host,recipient:guest,epoch,frame:917,identity,hash,digest:await checkpointDigest(h.bytes),byteLength:h.bytes.byteLength,...overrides};
 h.checkpoint.receive(JSON.stringify(metadata));h.checkpoint.receive(encodeCheckpointChunk(transferId,0,new Uint8Array(h.bytes)));await until(()=>h.stats().imports>0||h.commands.some(x=>x.type==='gameAbort'));await flush();
}
test('authorized guest acknowledges exact restored state; wrong member fails before import',async()=>{
 for(const wrongMember of [false,true]){
  const h=await setup('guest');try{
   h.game.handle(h.spec);await flush();assert.deepEqual(h.commands.filter(x=>x.type==='gameCheckpointReady'),[{type:'gameCheckpointReady',epoch,transferId}]);
   await deliver(h,wrongMember?{recipient:'z'.repeat(22)}:{});
   assert.equal(h.stats().imports,wrongMember?0:1);
   assert.deepEqual(h.commands.filter(x=>x.type==='gameCheckpointAck'),wrongMember?[]:[{type:'gameCheckpointAck',epoch,transferId,frame:917,hash}]);
   if(wrongMember)assert.equal(h.commands.at(-1)?.type,'gameAbort');
  }finally{h.game.dispose();}
 }
});

test('cancelled or departed checkpoint invalidates delayed import authorization and suppresses late acknowledgement',async()=>{
 for(const leave of [false,true]){
 const h=await setup('guest');let finish!:(value:{frame:number;hash:string})=>void,current!:()=>boolean;
 try{
  h.setImport(check=>{current=check;return new Promise(resolve=>{finish=resolve;});});h.game.handle(h.spec);await deliver(h);assert.equal(h.stats().imports,1);assert.equal(current(),true);
  const cancels=h.stats().cancels;if(leave)h.game.enter(undefined);else h.game.cancelIntent();assert.equal(current(),false);assert.ok(h.stats().cancels>cancels);
  finish({frame:917,hash});await flush();assert.deepEqual(h.commands.filter(x=>x.type==='gameCheckpointAck'),[]);if(!leave)assert.equal(h.commands.at(-1)?.type,'gameUnready');
 }finally{h.game.dispose();}
 }
});
