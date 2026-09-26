import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {stripTypeScriptTypes} from 'node:module';
import * as contracts from '../../../packages/contracts/src/index.ts';
import {checkpointDigest} from './checkpoint.ts';
const operationId='o'.repeat(22),epoch='e'.repeat(22),identity='a'.repeat(64);
const hex=(bytes:ArrayBuffer)=>Buffer.from(bytes).toString('hex');
async function harness(){
 const payload=new TextEncoder().encode('{"state":1}'),bytes=new Uint8Array(72+payload.length);bytes.set(new TextEncoder().encode('RCSTATE1'));bytes.set(Buffer.from(identity,'hex'),8);bytes.set(payload,72);
 const hash=await checkpointDigest(new Uint8Array([...bytes.slice(8,40),...payload]).buffer);
 const memory=new WebAssembly.Memory({initial:1});let output:Uint8Array=new Uint8Array(),imports=0,clears=0;
 const emit=(bytes:Uint8Array)=>{output=bytes;new Uint8Array(memory.buffer,4096,bytes.length).set(bytes);return 1;};
 const allocations=new Set<number>();
 const consume=(ptr:number)=>assert.equal(allocations.delete(ptr),true,'native state operations consume their allocation exactly once');
 const core={memory,local_state_limit:()=>2*1024*1024,local_state_alloc:()=>{assert.equal(allocations.has(1024),false);allocations.add(1024);return 1024;},local_state_validate:(ptr:number)=>{consume(ptr);return 1;},local_state_import:(ptr:number)=>{consume(ptr);imports++;return 1;},local_rewind_clear:()=>{clears++;},local_state_export:()=>emit(bytes),local_state_hash:()=>emit(Buffer.from(hash,'hex')),local_state_info:()=>emit(new TextEncoder().encode(JSON.stringify({identity}))),local_output:()=>4096,local_output_len:()=>output.length};
 const messages:contracts.WorkerResponse[]=[];
 const source=readFileSync(new URL('./worker.ts',import.meta.url),'utf8').replace(/^import .*;$/gm,'').replace('let core: Core | undefined;','let core: Core | undefined = injectedCore;');
 let now=0;
 const context={performance:{now:()=>now},setTimeout:(fn:()=>void,ms:number)=>setTimeout(fn,ms).unref(),clearTimeout,...contracts,injectedCore:core,hex,crypto,ArrayBuffer,Uint8Array,TextDecoder,TextEncoder,postMessage:(message:contracts.WorkerResponse)=>messages.push(structuredClone(message)),onmessage:undefined};
 runInNewContext(stripTypeScriptTypes(source),context);
 const rpc=context.onmessage as unknown as (event:{data:unknown})=>Promise<void>;
 return {bytes:bytes.buffer,hash,messages,rpc,advance:(ms:number)=>{now+=ms;},stats:()=>({imports,clears})};
}
test('dedicated peer RPC consumes each native allocation once and restores exact frame/epoch/hash',async()=>{
 const h=await harness();const request={type:'peer-checkpoint-prepare',operationId,requestId:1,epoch,frame:917,bytes:h.bytes,identity,hash:h.hash};
 await h.rpc({data:{...request,hash:'f'.repeat(64)}});assert.equal(h.messages.at(-1)?.type,'peer-checkpoint-error');assert.deepEqual(h.stats(),{imports:0,clears:0});
 await h.rpc({data:request});assert.deepEqual(h.messages.at(-1),{type:'peer-checkpoint-prepared',requestId:1,operationId,epoch,frame:917,hash:h.hash});assert.deepEqual(h.stats(),{imports:0,clears:0});
 await h.rpc({data:{type:'peer-checkpoint-commit',requestId:2,operationId}});assert.deepEqual(h.messages.at(-1),{type:'peer-checkpoint-imported',requestId:2,operationId,epoch,frame:917,hash:h.hash});assert.deepEqual(h.stats(),{imports:1,clears:1});
 await h.rpc({data:{type:'peer-checkpoint-export',requestId:2,epoch,frame:916}});assert.equal(h.messages.at(-1)?.type,'peer-checkpoint-error');
 await h.rpc({data:{type:'peer-checkpoint-export',requestId:3,epoch,frame:917}});const result=h.messages.at(-1);assert.equal(result?.type,'peer-checkpoint-exported');if(result?.type==='peer-checkpoint-exported'){assert.equal(result.frame,917);assert.equal(result.hash,h.hash);assert.equal(result.identity,identity);assert.deepEqual(result.bytes,h.bytes);}
});
test('invalid peer metadata and concurrent frame requests cannot mutate an importing worker',async()=>{
 const h=await harness();assert.equal(contracts.isWorkerRequest({type:'peer-checkpoint-prepare',operationId,requestId:1,epoch,frame:-1,bytes:h.bytes,identity,hash:h.hash}),false);
 const pending=h.rpc({data:{type:'peer-checkpoint-prepare',operationId,requestId:1,epoch,frame:50,bytes:h.bytes,identity,hash:h.hash}});
 await h.rpc({data:{type:'frame',epoch,frame:50,p1:0,p2:0}});assert.deepEqual(h.messages.at(-1),{type:'error',message:'Checkpoint preparation is pending'});await pending;assert.equal(h.messages.at(-1)?.type,'peer-checkpoint-prepared');assert.equal(h.stats().imports,0);
});

test('cancel during digest prevents preparation and stale commit without mutation',async()=>{
 const h=await harness();
 const pending=h.rpc({data:{type:'peer-checkpoint-prepare',requestId:1,operationId,epoch,frame:50,bytes:h.bytes,identity,hash:h.hash}});
 await h.rpc({data:{type:'peer-checkpoint-cancel',requestId:2,operationId}});await pending;
 assert.equal(h.messages.at(-1)?.type,'peer-checkpoint-error');
 await h.rpc({data:{type:'peer-checkpoint-commit',requestId:3,operationId}});assert.equal(h.messages.at(-1)?.type,'peer-checkpoint-error');assert.deepEqual(h.stats(),{imports:0,clears:0});
});
test('replacement and cancellation after preparation invalidate old commits',async()=>{
 const h=await harness(),next='n'.repeat(22);
 const prepare={type:'peer-checkpoint-prepare',requestId:1,operationId,epoch,frame:50,bytes:h.bytes,identity,hash:h.hash};
 await h.rpc({data:prepare});await h.rpc({data:{...prepare,operationId:next}});
 await h.rpc({data:{type:'peer-checkpoint-commit',requestId:3,operationId}});assert.equal(h.messages.at(-1)?.type,'peer-checkpoint-error');
 await h.rpc({data:{type:'peer-checkpoint-cancel',requestId:4,operationId:next}});
 await h.rpc({data:{type:'peer-checkpoint-commit',requestId:5,operationId:next}});assert.equal(h.messages.at(-1)?.type,'peer-checkpoint-error');assert.deepEqual(h.stats(),{imports:0,clears:0});
});

test('prepared deadline and overlapping replacement reject without importing',async()=>{
 const h=await harness(),next='n'.repeat(22),prepare={type:'peer-checkpoint-prepare',requestId:1,operationId,epoch,frame:50,bytes:h.bytes,identity,hash:h.hash};
 await h.rpc({data:prepare});h.advance(15000);
 await h.rpc({data:{type:'peer-checkpoint-commit',requestId:2,operationId}});assert.equal(h.messages.at(-1)?.type,'peer-checkpoint-error');
 const pending=h.rpc({data:prepare});await h.rpc({data:{...prepare,operationId:next}});await pending;
 await h.rpc({data:{type:'peer-checkpoint-commit',requestId:3,operationId}});assert.equal(h.messages.at(-1)?.type,'peer-checkpoint-error');assert.deepEqual(h.stats(),{imports:0,clears:0});
});
