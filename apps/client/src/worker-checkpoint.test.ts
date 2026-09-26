import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {stripTypeScriptTypes} from 'node:module';
import * as contracts from '../../../packages/contracts/src/index.ts';
import {checkpointDigest} from './checkpoint.ts';
const epoch='e'.repeat(22),identity='a'.repeat(64);
const hex=(bytes:ArrayBuffer)=>Buffer.from(bytes).toString('hex');
async function harness(){
 const payload=new TextEncoder().encode('{"state":1}'),bytes=new Uint8Array(72+payload.length);bytes.set(new TextEncoder().encode('RCSTATE1'));bytes.set(Buffer.from(identity,'hex'),8);bytes.set(payload,72);
 const hash=await checkpointDigest(new Uint8Array([...bytes.slice(8,40),...payload]).buffer);
 const memory=new WebAssembly.Memory({initial:1});let output:Uint8Array=new Uint8Array(),imports=0,clears=0;
 const emit=(bytes:Uint8Array)=>{output=bytes;new Uint8Array(memory.buffer,4096,bytes.length).set(bytes);return 1;};
 const core={memory,local_state_limit:()=>2*1024*1024,local_state_alloc:()=>1024,local_state_validate:()=>1,local_state_import:()=>{imports++;return 1;},local_rewind_clear:()=>{clears++;},local_state_export:()=>emit(bytes),local_state_hash:()=>emit(Buffer.from(hash,'hex')),local_state_info:()=>emit(new TextEncoder().encode(JSON.stringify({identity}))),local_output:()=>4096,local_output_len:()=>output.length};
 const messages:contracts.WorkerResponse[]=[];
 const source=readFileSync(new URL('./worker.ts',import.meta.url),'utf8').replace(/^import .*;$/gm,'').replace('let core: Core | undefined;','let core: Core | undefined = injectedCore;');
 const context={...contracts,injectedCore:core,hex,crypto,ArrayBuffer,Uint8Array,TextDecoder,TextEncoder,postMessage:(message:contracts.WorkerResponse)=>messages.push(structuredClone(message)),onmessage:undefined};
 runInNewContext(stripTypeScriptTypes(source),context);
 const rpc=context.onmessage as unknown as (event:{data:unknown})=>Promise<void>;
 return {bytes:bytes.buffer,hash,messages,rpc,stats:()=>({imports,clears})};
}
test('dedicated peer RPC validates before mutation and restores exact frame/epoch/hash',async()=>{
 const h=await harness();const request={type:'peer-checkpoint-import',requestId:1,epoch,frame:917,bytes:h.bytes,identity,hash:h.hash};
 await h.rpc({data:{...request,hash:'f'.repeat(64)}});assert.equal(h.messages.at(-1)?.type,'peer-checkpoint-error');assert.deepEqual(h.stats(),{imports:0,clears:0});
 await h.rpc({data:request});assert.deepEqual(h.messages.at(-1),{type:'peer-checkpoint-imported',requestId:1,epoch,frame:917,hash:h.hash});assert.deepEqual(h.stats(),{imports:1,clears:1});
 await h.rpc({data:{type:'peer-checkpoint-export',requestId:2,epoch,frame:916}});assert.equal(h.messages.at(-1)?.type,'peer-checkpoint-error');
 await h.rpc({data:{type:'peer-checkpoint-export',requestId:3,epoch,frame:917}});const result=h.messages.at(-1);assert.equal(result?.type,'peer-checkpoint-exported');if(result?.type==='peer-checkpoint-exported'){assert.equal(result.frame,917);assert.equal(result.hash,h.hash);assert.equal(result.identity,identity);assert.deepEqual(result.bytes,h.bytes);}
});
test('invalid peer metadata and concurrent frame requests cannot mutate an importing worker',async()=>{
 const h=await harness();assert.equal(contracts.isWorkerRequest({type:'peer-checkpoint-import',requestId:1,epoch,frame:-1,bytes:h.bytes,identity,hash:h.hash}),false);
 const pending=h.rpc({data:{type:'peer-checkpoint-import',requestId:1,epoch,frame:50,bytes:h.bytes,identity,hash:h.hash}});
 await h.rpc({data:{type:'frame',epoch,frame:50,p1:0,p2:0}});assert.deepEqual(h.messages.at(-1),{type:'error',message:'Emulator is loading'});await pending;assert.equal(h.messages.at(-1)?.type,'peer-checkpoint-imported');
});
