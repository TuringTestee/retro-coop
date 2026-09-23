import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import 'fake-indexeddb/auto';
import type {RoomView} from '../../../packages/contracts/src/rooms.ts';
import {acquireGuestRom} from './guest-rom.ts';
import {clearLocalData,deleteRom,putRom,readRom} from './saves.ts';

const bytes=Uint8Array.from({length:16+16384},(_,i)=>i<4?[0x4e,0x45,0x53,0x1a][i]:i===4?1:0);
const hash=createHash('sha256').update(bytes).digest('hex');
const room={id:'r'.repeat(43),role:'guest',chatMembership:'m'.repeat(43),fingerprint:{romSha256:hash,cartridge:{bytes:bytes.length}}} as RoomView;
const response=()=>new Response(bytes.slice(),{headers:{'Content-Length':String(bytes.length)}});
const token='t'.repeat(43),signal=new AbortController().signal;
(globalThis as {location?:{href:string}}).location={href:'http://127.0.0.1:5173/'};

test('guest download checks exact bytes, persists, reads back and rehashes on reuse',async()=>{
 let calls=0;const fetcher=(async(url:URL,init:RequestInit)=>{calls++;assert.equal(url.pathname,`/coordinator/rooms/${room.id}/rom`);assert.equal((init.headers as Record<string,string>).Authorization,`Bearer ${token}`);assert.equal((init.headers as Record<string,string>)['X-Room-Membership'],room.chatMembership);assert.equal(init.cache,'no-store');return response();}) as typeof fetch;
 const progress:number[]=[];
 const first=await acquireGuestRom(room,token,signal,n=>progress.push(n),()=>true,fetcher);assert.equal(first.source,'download');assert.equal(first.persisted,true);assert.equal(progress.at(-1),bytes.length);assert.deepEqual(new Uint8Array(await first.file.arrayBuffer()),bytes);
 const second=await acquireGuestRom(room,token,signal,()=>{},()=>true,fetcher);assert.equal(second.source,'cache');assert.equal(calls,1);
 const stored=await readRom(hash);const damaged=bytes.slice();damaged[20]^=1;await putRom({sha256:hash,size:damaged.length,bytes:damaged.buffer,savedAt:Date.now()},stored.generation,stored.romGeneration);
 const repaired=await acquireGuestRom(room,token,signal,()=>{},()=>true,fetcher);assert.equal(repaired.source,'download');assert.equal(calls,2);
});
test('cross-tab clear during transfer prevents the late cache write but leaves playable bytes',async()=>{
 const current=await readRom(hash);await clearLocalData(current.generation);
 let release!:(response:Response)=>void;const fetcher=(()=>new Promise<Response>(resolve=>{release=resolve;})) as typeof fetch;
 const pending=acquireGuestRom(room,token,signal,()=>{},()=>true,fetcher);
 await new Promise(resolve=>setTimeout(resolve,0));
 const before=await readRom(hash);await clearLocalData(before.generation);release(response());
 const result=await pending;assert.equal(result.persisted,false);assert.match(result.notice!,/download again next time/);assert.deepEqual(new Uint8Array(await result.file.arrayBuffer()),bytes);assert.equal((await readRom(hash)).record,undefined);
});
test('individual game deletion prevents an in-flight download from recreating its saved copy',async()=>{
 const before=await readRom(hash);if(before.record)await deleteRom(hash,before.generation);
 let release!:(response:Response)=>void;const fetcher=(()=>new Promise<Response>(resolve=>{release=resolve;})) as typeof fetch;
 const pending=acquireGuestRom(room,token,signal,()=>{},()=>true,fetcher);
 await new Promise(resolve=>setTimeout(resolve,0));
 const generation=(await readRom(hash)).generation;
 await deleteRom(hash,generation);release(response());
 const result=await pending;assert.equal(result.persisted,false);assert.match(result.notice!,/download again next time/);
 assert.equal((await readRom(hash)).record,undefined);
});
test('partial, changed, and stale-operation downloads cannot load or persist',async()=>{
 const current=await readRom(hash);await clearLocalData(current.generation);
 for(const data of [bytes.subarray(0,-1),Uint8Array.from(bytes,x=>x^1)])await assert.rejects(acquireGuestRom(room,token,signal,()=>{},()=>true,(async()=>new Response(data.slice())) as typeof fetch));
 let active=true;await assert.rejects(acquireGuestRom(room,token,signal,()=>{},()=>active,(async()=>{active=false;return response();}) as typeof fetch),/room changed/i);
 assert.equal((await readRom(hash)).record,undefined);
});
test('storage denial keeps verified bytes available for this tab',async()=>{
 const original=globalThis.indexedDB;(globalThis as {indexedDB?:IDBFactory}).indexedDB=undefined;
 try{const result=await acquireGuestRom(room,token,signal,()=>{},()=>true,(async()=>response()) as typeof fetch);assert.equal(result.persisted,false);assert.match(result.notice!,/download again next time/);assert.deepEqual(new Uint8Array(await result.file.arrayBuffer()),bytes);}
 finally{globalThis.indexedDB=original;}
});
