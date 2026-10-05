import {isZipFile} from '../../../packages/contracts/src/game-file.ts';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createServer,type IncomingMessage,type ServerResponse} from 'node:http';
import {once} from 'node:events';
import {createHash} from 'node:crypto';
import {extractZipFile} from './zip-upload.ts';
import {ROM_FILE_LIMIT,ZIP_ARCHIVE_LIMIT} from '../../../packages/contracts/src/game-file.ts';

const bytes=Buffer.alloc(16+16384,1),sha=createHash('sha256').update(bytes).digest('hex');
const file=()=>new File(['original zip bytes'],'picked.zip',{type:'application/zip'});
const headers={'Content-Type':'application/octet-stream','Content-Length':String(bytes.length),'X-NES-Name':encodeURIComponent('Selected game.nes'),'X-NES-SHA256':sha};
async function service(handler:(request:IncomingMessage,response:ServerResponse)=>void) {
 const server=createServer(handler);server.listen(0,'127.0.0.1');await once(server,'listening');
 return {url:`http://127.0.0.1:${(server.address() as {port:number}).port}/coordinator?ignored=yes#ignored`,close:async()=>{server.closeAllConnections();await new Promise<void>(resolve=>server.close(()=>resolve()));}};
}
test('client uploads ZIP bytes and returns the selected, verified NES File',async()=>{
 const t=await service((request,response)=>{
  assert.equal(request.url,'/coordinator/rom-extractions');assert.equal(request.method,'POST');assert.equal(request.headers.authorization,'Bearer token');assert.equal(request.headers['content-type'],'application/zip');
  let uploaded='';request.on('data',chunk=>uploaded+=chunk);request.on('end',()=>{assert.equal(uploaded,'original zip bytes');response.writeHead(200,headers).end(bytes);});
 });try{const result=await extractZipFile(t.url,'token',file(),new AbortController().signal);assert.equal(result.name,'Selected game.nes');assert.deepEqual(Buffer.from(await result.arrayBuffer()),bytes);}finally{await t.close();}
});
test('client rejects compressed boundary locally without issuing an upload',async()=>{
 let requested=false;const t=await service((_request,response)=>{requested=true;response.end();});
 try{await assert.rejects(extractZipFile(t.url,'token',new File([new Uint8Array(ZIP_ARCHIVE_LIMIT)],'large.zip'),new AbortController().signal),/under 2 MB/);assert.equal(requested,false);}finally{await t.close();}
});
test('client verifies the extracted NES hash instead of trusting receipt metadata',async()=>{
 const t=await service((_request,response)=>response.writeHead(200,{...headers,'X-NES-SHA256':'f'.repeat(64)}).end(bytes));
 try{await assert.rejects(extractZipFile(t.url,'token',file(),new AbortController().signal),/did not match/);}finally{await t.close();}
});
for(const [label,changed] of [
 ['oversized NES',{'Content-Length':String(ROM_FILE_LIMIT+1)}],
 ['missing identity',{'X-NES-SHA256':''}],
 ['unsafe filename',{'X-NES-Name':'..%2Fgame.nes'}],
 ['bad Unicode encoding',{'X-NES-Name':'%FF.nes'}],
 ['unbounded title',{'X-NES-Name':'x'.repeat(81)+'.nes'}],
 ['wrong content type',{'Content-Type':'application/zip'}],
] as Array<[string,Record<string,string>]>)test(`client rejects ${label} and closes the response stream`,async()=>{
 let closed!:()=>void;const observed=new Promise<void>(resolve=>closed=resolve);
 const t=await service((_request,response)=>{response.once('close',closed);response.writeHead(200,{...headers,...changed});response.write(bytes.subarray(0,8));});
 try{await assert.rejects(extractZipFile(t.url,'token',file(),new AbortController().signal),/invalid ZIP response/);await observed;}finally{await t.close();}
});
test('client cancellation aborts the server transfer and allows a fresh retry',async()=>{
 let started!:()=>void,closed!:()=>void,count=0;const reached=new Promise<void>(resolve=>started=resolve),disconnected=new Promise<void>(resolve=>closed=resolve);
 const t=await service((_request,response)=>{if(++count===1){response.once('close',closed);response.writeHead(200,headers);response.write(bytes.subarray(0,8));started();}else response.writeHead(200,headers).end(bytes);});
 try{const controller=new AbortController(),pending=extractZipFile(t.url,'token',file(),controller.signal);await reached;controller.abort();await assert.rejects(pending,/abort/i);await disconnected;const retry=await extractZipFile(t.url,'token',file(),new AbortController().signal);assert.equal(retry.name,'Selected game.nes');assert.deepEqual(Buffer.from(await retry.arrayBuffer()),bytes);}finally{await t.close();}
});
test('client communicates archive failure and supports a successful retry',async()=>{
 let count=0;const t=await service((_request,response)=>{if(++count===1)response.writeHead(400,{'Content-Type':'application/json'}).end(JSON.stringify({error:'archive_no_game'}));else response.writeHead(200,headers).end(bytes);});
 try{await assert.rejects(extractZipFile(t.url,'token',file(),new AbortController().signal),/contains no NES game/);const retry=await extractZipFile(t.url,'token',file(),new AbortController().signal);assert.equal(retry.size,bytes.length);}finally{await t.close();}
});


test('shared filename detection routes ZIP case variants without changing NES admission',()=>{
 for(const name of ['game.zip','game.ZIP','game.Zip'])assert.equal(isZipFile(name),true);
 for(const name of ['game.nes','game.NES','game.zip.nes','game.zip.exe'])assert.equal(isZipFile(name),false);
});
