import {test} from 'node:test';
import assert from 'node:assert/strict';
import 'fake-indexeddb/auto';
import {recoverLiveHost} from './host-recovery.ts';
import {clearLocalData,readRecovery,changeRecovery,type RecoveryCapture} from './saves.ts';
import type {LocalPlayer} from './player.ts';
const fingerprint:RecoveryCapture['fingerprint']={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:0,submapper:0,region:'NTSC',bytes:16400}};
const identity='c'.repeat(64),hash='d'.repeat(64);
const capture=(frame:number):RecoveryCapture=>({fingerprint,identity,hash,title:'Game',frame,savedAt:1000+frame,bytes:new ArrayBuffer(80)});
async function records(...captures:RecoveryCapture[]){const stored=await readRecovery();await clearLocalData(stored.generation);for(const row of captures){const prior=await readRecovery();await changeRecovery(prior.record,prior.generation,row);}}
function machine(inspect:(bytes:ArrayBuffer)=>Promise<{identity:string;hash:string}>){const imported:number[]=[];return {imported,player:{saveInfo:async()=>({identity,limit:2000}),inspectSave:inspect,importPeerCheckpoint:async(_epoch:string,frame:number)=>{imported.push(frame);}} as unknown as LocalPlayer};}
test('completed invalid newest state permits the validated older capture and reports its time',async()=>{
 await records(capture(10),capture(20));let inspected=0;
 const t=machine(async()=>{if(++inspected===1)throw Object.assign(Error('Invalid codec state'),{code:'invalid_state'});return {identity,hash};});
 const result=await recoverLiveHost(t.player,fingerprint,()=>true,()=>{});
 assert.deepEqual(result,{frame:10,hash,savedAt:1010,older:true});assert.deepEqual(t.imported,[10]);assert.equal((await readRecovery()).record!.captures.length,2);
});
test('a storage or worker delay leaves recovery unknown and does not initialize a fresh timeline',async()=>{
 await records(capture(10));const t=machine(async()=>{throw Error('The save operation timed out. Try again.');});
 await assert.rejects(recoverLiveHost(t.player,fingerprint,()=>true,()=>{}),/timed out/);assert.deepEqual(t.imported,[]);assert.equal((await readRecovery()).record!.captures[0].frame,10);
 const retry=machine(async()=>({identity,hash}));assert.equal((await recoverLiveHost(retry.player,fingerprint,()=>true,()=>{}))?.frame,10);
});
test('confirmed absent or incompatible captures permit fallback without deleting saved copies',async()=>{
 await records();const t=machine(async()=>{throw Error('Unexpected validation');});assert.equal(await recoverLiveHost(t.player,fingerprint,()=>true,()=>{}),undefined);
 await records({...capture(10),identity:'e'.repeat(64)});assert.equal(await recoverLiveHost(t.player,fingerprint,()=>true,()=>{}),undefined);assert.equal((await readRecovery()).record!.captures.length,1);assert.deepEqual(t.imported,[]);
});
test('clearing captures during completed validation revokes the pending import',async()=>{
 await records(capture(10));const t=machine(async()=>{const stored=await readRecovery();await clearLocalData(stored.generation);return {identity,hash};});
 await assert.rejects(recoverLiveHost(t.player,fingerprint,()=>true,()=>{}),/changed or was cleared/);assert.deepEqual(t.imported,[]);
});
