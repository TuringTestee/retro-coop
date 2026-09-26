import {test} from 'node:test';
import assert from 'node:assert/strict';
import {CheckpointReceiver,CheckpointSender,checkpointDigest} from './checkpoint.ts';
import {parseCheckpointMetadata,isCheckpointMetadata,encodeCheckpointChunk,decodeCheckpointChunk,CHECKPOINT_MAX_BYTES,CHECKPOINT_BUFFER_BYTES,CHECKPOINT_PAYLOAD_BYTES} from '../../../packages/contracts/src/checkpoint.ts';
const token=(s:string)=>s.repeat(22);
async function fixture(size=100){const bytes=new Uint8Array(size).fill(42).buffer;return {bytes,metadata:{transferId:token('t'),sender:token('s'),recipient:token('r'),epoch:token('e'),frame:51,identity:'a'.repeat(64),hash:'b'.repeat(64),digest:await checkpointDigest(bytes),byteLength:size}};}
const authorized=()=>true;
test('strict metadata and binary framing reject unbounded and ambiguous values',async()=>{
 const {metadata}=await fixture();assert.equal(isCheckpointMetadata(metadata),true);assert.deepEqual(parseCheckpointMetadata(JSON.stringify(metadata)),metadata);assert.equal(parseCheckpointMetadata(" ".repeat(1025)),undefined);
 for(const bad of [{...metadata,extra:1},{...metadata,frame:-1},{...metadata,byteLength:CHECKPOINT_MAX_BYTES+1},{...metadata,recipient:metadata.sender}])assert.equal(isCheckpointMetadata(bad),false);
 const chunk=encodeCheckpointChunk(token('t'),4,new Uint8Array([1,2]));assert.deepEqual([...decodeCheckpointChunk(chunk).payload],[1,2]);
 new Uint8Array(chunk)[50]=1;assert.throws(()=>decodeCheckpointChunk(chunk));
 assert.throws(()=>encodeCheckpointChunk(token('t'),0,new Uint8Array(12*1024)));
});
test('bounded sender resumes on drain and receiver verifies complete digest',async()=>{
 const {metadata,bytes}=await fixture(CHECKPOINT_MAX_BYTES);const receiver=new CheckpointReceiver(),sender=new CheckpointSender();receiver.begin(metadata,authorized);
 const chunks:ArrayBuffer[]=[];const channel={readyState:'open',bufferedAmount:0,send(bytes:ArrayBuffer){chunks.push(bytes);this.bufferedAmount+=bytes.byteLength;}};
 sender.begin(metadata,bytes,channel);let result;
 do {result=sender.pump(metadata.recipient,authorized);assert.ok(channel.bufferedAmount<=CHECKPOINT_BUFFER_BYTES);for(const chunk of chunks.splice(0)){const received=await receiver.accept(chunk,authorized);if(received)assert.deepEqual(received.bytes,bytes);}channel.bufferedAmount=0;}while(result==='pending');
 assert.equal(sender.retainedBytes,0);assert.equal(receiver.retainedBytes,0);
});
test('reject duplicate, gap, stale, unsolicited, corrupted and changed authorization without retaining bytes',async()=>{
 const {metadata,bytes}=await fixture(200);
 for(const variant of ['duplicate','gap','stale','corrupt','unauthorized']){
  const r=new CheckpointReceiver();r.begin(metadata,authorized);
  if(variant==='duplicate')await r.accept(encodeCheckpointChunk(metadata.transferId,0,new Uint8Array(bytes,0,100)),authorized);
  const data=new Uint8Array(bytes.slice(0,100));if(variant==='corrupt')data.fill(0);
  const chunk=encodeCheckpointChunk(variant==='stale'?token('x'):metadata.transferId,variant==='gap'?100:0,variant==='corrupt'?new Uint8Array(200):data);
  await assert.rejects(r.accept(chunk,()=>variant!=='unauthorized'));assert.equal(r.retainedBytes,0);
 }
 await assert.rejects(new CheckpointReceiver().accept(encodeCheckpointChunk(metadata.transferId,0,new Uint8Array(bytes)),authorized));
});
test('sender enforces four recipients, deadlines and receiver cancellation during digest',async()=>{
 const {metadata,bytes}=await fixture();let now=0;const s=new CheckpointSender(()=>now);const channel={readyState:'open',bufferedAmount:CHECKPOINT_BUFFER_BYTES,send(){throw Error('should not send');}};
 for(const x of ['a','b','c','d'])s.begin({...metadata,recipient:token(x)},bytes,channel);
 assert.throws(()=>s.begin(metadata,bytes,channel));assert.equal(s.pump(token('a'),authorized),'pending');now=15000;s.expire();assert.equal(s.retainedBytes,0);
 const r=new CheckpointReceiver(()=>now);r.begin(metadata,authorized);now+=15000;assert.equal(r.expire(),true);assert.equal(r.retainedBytes,0);
 r.begin(metadata,authorized);const pending=r.accept(encodeCheckpointChunk(metadata.transferId,0,new Uint8Array(bytes)),authorized);r.cancel();await assert.rejects(pending);
});
