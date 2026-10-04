import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import 'fake-indexeddb/auto';
import {clearLocalData,deleteRom,listRoms,putRom,readRom} from './saves.ts';
import {candidateStillStored,entry,gameLibrary,libraryEntries,rememberImport,rememberUse,savedCandidate,verifiedSavedFile} from './rom-library.ts';

const bytes=Uint8Array.from({length:16+16384},(_,i)=>i<4?[0x4e,0x45,0x53,0x1a][i]:i===4?1:0);
const hash=createHash('sha256').update(bytes).digest('hex');
async function reset(){const {generation}=await listRoms();await clearLocalData(generation);}

test('legacy downloaded row remains readable and an identical import enriches one row',async()=>{
 await reset();const before=await readRom(hash);
 await putRom({sha256:hash,bytes:bytes.slice().buffer,size:bytes.length,savedAt:10},before.generation,before.romGeneration);
 assert.deepEqual(new Uint8Array(await (await verifiedSavedFile(hash)).arrayBuffer()),bytes);
 assert.equal(entry((await readRom(hash)).record!).source,'download');
 await rememberImport(new File([bytes.slice()],'My game.nes'),hash);
 const rows=await libraryEntries();assert.equal(rows.length,1);assert.equal(rows[0].label,'My game.nes');assert.equal(rows[0].source,'import');
 assert.deepEqual(new Uint8Array((await readRom(hash)).record!.bytes),bytes);
});
test('included games derive once from the manifest even when their bytes are saved',async()=>{
 await reset();const rows=await gameLibrary();assert.equal(rows.filter(row=>row.kind==='included').length,2);
 const included=rows[0];const before=await readRom(included.sha256);
 await putRom({sha256:included.sha256,bytes:bytes.slice().buffer,size:bytes.length,savedAt:10},before.generation,before.romGeneration);
 const after=await gameLibrary();assert.equal(after.filter(row=>row.sha256===included.sha256).length,1);
});
test('saved selection rejects corrupt, evicted and deleted copies',async()=>{
 await reset();await assert.rejects(verifiedSavedFile(hash),/missing or damaged/);
 const before=await readRom(hash);const damaged=bytes.slice();damaged[20]^=1;
 await putRom({sha256:hash,bytes:damaged.buffer,size:damaged.length,savedAt:10},before.generation,before.romGeneration);
 await assert.rejects(verifiedSavedFile(hash),/missing or damaged/);
 await deleteRom(hash,before.generation);await assert.rejects(verifiedSavedFile(hash),/missing or damaged/);
});
test('saved candidate binds exact bytes and deletion generation through local load',async()=>{
 await reset();await rememberImport(new File([bytes.slice()],'test.nes'),hash);
 const candidate=await savedCandidate(hash);
 const loaded={romSha256:hash,cartridge:{bytes:bytes.length}} as Parameters<typeof candidateStillStored>[1];
 assert.equal(await candidateStillStored(candidate,loaded),true);
 assert.equal(await candidateStillStored(candidate,{...loaded,romSha256:'0'.repeat(64)}),false);
 assert.equal(await candidateStillStored(candidate,{...loaded,cartridge:{...loaded.cartridge,bytes:bytes.length-1}}),false);
 const current=await readRom(hash);await deleteRom(hash,current.generation);
 assert.equal(await candidateStillStored(candidate,loaded),false);
});
test('cross-tab clear and deletion prevent an old import write',async()=>{
 await reset();const before=await readRom(hash);await clearLocalData(before.generation);
 await assert.rejects(putRom({sha256:hash,bytes:bytes.slice().buffer,size:bytes.length,savedAt:10},before.generation,before.romGeneration),/deleted or local data was cleared/);
 const next=await readRom(hash);await deleteRom(hash,next.generation);
 await assert.rejects(putRom({sha256:hash,bytes:bytes.slice().buffer,size:bytes.length,savedAt:10},next.generation,next.romGeneration),/deleted or local data was cleared/);
 assert.equal((await readRom(hash)).record,undefined);
});
test('reselecting a saved game updates recency without changing its bytes',async()=>{
 await reset();const initial=await readRom(hash);
 await putRom({sha256:hash,bytes:bytes.slice().buffer,size:bytes.length,savedAt:10,lastUsedAt:10,label:'Recent.nes',source:'import'},initial.generation,initial.romGeneration);
 const before=(await readRom(hash)).record!;
 await rememberUse(hash);
 const after=(await readRom(hash)).record!;
 assert.equal(after.label,'Recent.nes');
 assert.deepEqual(new Uint8Array(after.bytes),bytes);
 assert.ok(after.lastUsedAt!>before.lastUsedAt!);
});

test('automatic recovery retains two current-game captures and rejects clear/write and ABA races',async()=>{
 const {readRecovery,changeRecovery}=await import('./saves.ts');
 await reset();const first=await readRecovery();
 const fingerprint={romSha256:hash,coreSha256:'a'.repeat(64),localSchema:1 as const,settings:'auto-region;zero-ram;48000hz;standard-p1-p2' as const,cartridge:{format:'iNES' as const,mapper:0,submapper:0,region:'NTSC',bytes:bytes.length}};
 const row={fingerprint,title:'Original game',identity:'a'.repeat(64),hash:'b'.repeat(64),frame:10,savedAt:100,bytes:new ArrayBuffer(72)};
 await changeRecovery(first.record,first.generation,row);const old=await readRecovery();
 await changeRecovery(old.record,old.generation,{...row,frame:20});const next=await readRecovery();
 await changeRecovery(next.record,next.generation,{...row,frame:30});assert.deepEqual((await readRecovery()).record!.captures.map(row=>row.frame),[30,20]);
 await assert.rejects(changeRecovery(old.record,old.generation,row),/changed or was cleared/);
 const latest=await readRecovery();await changeRecovery(latest.record,latest.generation,undefined);
 const empty=await readRecovery();await changeRecovery(empty.record,empty.generation,row);
 assert.ok((await readRecovery()).record!.revision>latest.record!.revision);
 await assert.rejects(changeRecovery(latest.record,latest.generation,row),/changed or was cleared/);
 const beforeClear=await readRecovery();await clearLocalData(beforeClear.generation);
 await assert.rejects(changeRecovery(beforeClear.record,beforeClear.generation,row),/changed or was cleared/);
 assert.equal((await readRecovery()).record,undefined);
 await assert.rejects(changeRecovery(undefined,(await readRecovery()).generation,row,()=>false),/changed or was cleared/);
});

test('failed recovery storage preserves the prior capture and unavailable storage rejects clearly',async()=>{
 const {readRecovery,changeRecovery}=await import('./saves.ts');await reset();
 const fingerprint={romSha256:hash,coreSha256:'a'.repeat(64),localSchema:1 as const,settings:'auto-region;zero-ram;48000hz;standard-p1-p2' as const,cartridge:{format:'iNES' as const,mapper:0,submapper:0,region:'NTSC',bytes:bytes.length}};
 const row={fingerprint,title:'Game',identity:'a'.repeat(64),hash:'b'.repeat(64),frame:10,savedAt:100,bytes:new ArrayBuffer(72)};
 const initial=await readRecovery();await changeRecovery(initial.record,initial.generation,row);const prior=await readRecovery();
 const put=IDBObjectStore.prototype.put;
 IDBObjectStore.prototype.put=function(...args){if(this.name==='recovery')throw new DOMException('Disk full','QuotaExceededError');return put.apply(this,args);};
 try{await assert.rejects(changeRecovery(prior.record,prior.generation,{...row,frame:20}),/Disk full/);}finally{IDBObjectStore.prototype.put=put;}
 assert.deepEqual(await readRecovery(),prior);
 const remove=IDBObjectStore.prototype.delete;
 IDBObjectStore.prototype.delete=function(...args){if(this.name==='recovery')throw new DOMException('Disk unavailable','UnknownError');return remove.apply(this,args);};
 try{await assert.rejects(changeRecovery(prior.record,prior.generation,undefined),/Disk unavailable/);}finally{IDBObjectStore.prototype.delete=remove;}
 assert.deepEqual(await readRecovery(),prior);
 const db=globalThis.indexedDB;Object.defineProperty(globalThis,'indexedDB',{value:{open(){throw Error('Storage disabled');}},configurable:true});
 try{await assert.rejects(readRecovery(),/Storage disabled/);}finally{Object.defineProperty(globalThis,'indexedDB',{value:db,configurable:true});}
});

test('completed pause queues its newer capture behind an in-flight timer sample',async()=>{
 const {HostRecoveryCapture}=await import('./host-recovery.ts');const {readRecovery}=await import('./saves.ts');await reset();
 const fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1 as const,settings:'auto-region;zero-ram;48000hz;standard-p1-p2' as const,cartridge:{format:'iNES' as const,mapper:0,submapper:0,region:'NTSC' as const,bytes:24592}};
 let frame=1800,release!:(value:{frame:number;hash:string;identity:string;bytes:ArrayBuffer})=>void;const exports:number[]=[];
 const player={captureRecovery(){const result={frame,hash:'c'.repeat(64),identity:'d'.repeat(64),bytes:new ArrayBuffer(80)};exports.push(frame);return exports.length===1?new Promise(resolve=>{release=resolve;}):Promise.resolve(result);}} as unknown as import('./player.ts').LocalPlayer;
 const owner=new HostRecoveryCapture(player,fingerprint,'Game',()=>true,()=>{});
 try{const timer=owner.capture();while(!release)await new Promise(resolve=>setImmediate(resolve));frame=1810;const paused=owner.capture();release({frame:1800,hash:'c'.repeat(64),identity:'d'.repeat(64),bytes:new ArrayBuffer(80)});await Promise.all([timer,paused]);assert.deepEqual(exports,[1800,1810]);assert.deepEqual((await readRecovery()).record?.captures.map(c=>c.frame),[1810,1800]);}finally{owner.stop();}
});


test('queued automatic capture stops at revoked owner and unchanged progress is deduplicated',async()=>{
 const {HostRecoveryCapture}=await import('./host-recovery.ts');const {readRecovery}=await import('./saves.ts');
 for(const revoke of ['stop','membership','unchanged']){
  await reset();let current=true,exports=0,release!:()=>void;
  const fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1 as const,settings:'auto-region;zero-ram;48000hz;standard-p1-p2' as const,cartridge:{format:'iNES' as const,mapper:0,submapper:0,region:'NTSC' as const,bytes:24592}};
  const captured={frame:10,hash:'c'.repeat(64),identity:'d'.repeat(64),bytes:new ArrayBuffer(80)};
  const player={captureRecovery(){++exports;return exports===1?new Promise(resolve=>{release=()=>resolve(captured);}):Promise.resolve(captured);}} as unknown as import('./player.ts').LocalPlayer;
  const owner=new HostRecoveryCapture(player,fingerprint,'Game',()=>current,()=>{});
  try{const first=owner.capture();while(!release)await new Promise(resolve=>setImmediate(resolve));const queued=owner.capture();if(revoke==='stop')owner.stop();if(revoke==='membership')current=false;release();await Promise.all([first,queued]);const record=(await readRecovery()).record;assert.equal(exports,revoke==='unchanged'?2:1);assert.equal(record?.captures.length,revoke==='unchanged'?1:undefined);}finally{owner.stop();}
 }
});
