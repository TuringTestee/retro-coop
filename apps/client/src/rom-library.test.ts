import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import 'fake-indexeddb/auto';
import {clearLocalData,deleteRom,listRoms,putRom,readRom} from './saves.ts';
import {candidateStillStored,entry,gameLibrary,libraryEntries,previewDisplay,rememberImport,savedCandidate,validPreview,verifiedSavedFile} from './rom-library.ts';

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
test('stored preview and label are bounded for display',()=>{
 assert.equal(validPreview('data:image/webp;base64,AAAA'),true);
 assert.equal(validPreview('data:image/svg+xml;base64,AAAA'),false);
 assert.equal(validPreview('data:image/webp;base64,'+'A'.repeat(32_001)),false);
 const row=entry({sha256:hash,bytes:bytes.buffer,size:bytes.length,savedAt:12,label:'X'.repeat(100),preview:'data:image/svg+xml;base64,AAAA'});
 assert.equal(row.label.length,80);assert.equal(row.preview,undefined);
 assert.deepEqual(previewDisplay(row),{text:'No preview yet.'});
});
