import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {downloadFeatured} from './featured-download.ts';
import {featuredGame,featuredAssetPath} from '../../../packages/contracts/src/catalog.ts';
const original=readFileSync(new URL('./assets/from-below-1.0.nes',import.meta.url));
const fetchBytes=(bytes:Uint8Array,headers:Record<string,string>={})=>(async()=>new Response(Uint8Array.from(bytes),{headers})) as typeof fetch;
test('included download verifies exact bytes and uses only the fixed catalog path',async()=>{
 const progress:number[]=[];
 const file=await downloadFeatured(new AbortController().signal,n=>progress.push(n),(async(url,init)=>{
  assert.equal(url,featuredAssetPath);assert.equal(init?.redirect,'error');assert.equal(init?.credentials,'omit');
  return new Response(original,{headers:{'Content-Length':String(featuredGame.bytes)}});
 }) as typeof fetch);
 assert.deepEqual(new Uint8Array(await file.arrayBuffer()),new Uint8Array(original));assert.equal(progress.at(-1),featuredGame.bytes);
});
test('truncated, oversized, wrong hash, wrong declared size and failed downloads cannot become a file',async()=>{
 const changed=Uint8Array.from(original);changed[20]^=1;
 for(const fetcher of [fetchBytes(original.subarray(1)),fetchBytes(new Uint8Array(featuredGame.bytes+1)),fetchBytes(changed),fetchBytes(original,{'Content-Length':'3'}),(async()=>new Response('',{status:503})) as typeof fetch]) {
  await assert.rejects(downloadFeatured(new AbortController().signal,()=>{},fetcher));
 }
});
test('cancellation rejects even when an already-completed response arrives late',async()=>{
 const controller=new AbortController();let release!:(response:Response)=>void;
 const pending=downloadFeatured(controller.signal,()=>{},(()=>new Promise<Response>(resolve=>{release=resolve;})) as typeof fetch);
 controller.abort();release(new Response(original));await assert.rejects(pending,{name:'AbortError'});
});
