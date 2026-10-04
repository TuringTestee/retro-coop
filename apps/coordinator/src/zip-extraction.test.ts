import {test} from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {createHash,randomUUID} from 'node:crypto';
import {request as httpRequest} from 'node:http';
import {mkdtempSync,readdirSync,writeFileSync,existsSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {crc32,deflateRawSync} from 'node:zlib';
import {WebSocket} from 'ws';
import {createCoordinator,shutdown} from './server.ts';
import {RomStore} from './rom-store.ts';
import {ZIP_ARCHIVE_LIMIT} from '../../../packages/contracts/src/game-file.ts';
import type {RomLimits} from './rom-store.ts';
import type {RoomEvent} from '../../../packages/contracts/src/rooms.ts';

const origin='https://client.example';
const rom=()=>{const bytes=Buffer.alloc(16+16384);bytes.set([0x4e,0x45,0x53,0x1a,1,0]);return bytes;};
type ZipEntry={name:string;data:Buffer;method?:number;flags?:number;mode?:number;crc?:number;advertised?:number};
/** Original, small fixtures; mutations exercise metadata rather than another ZIP implementation. */
function archive(entries:ZipEntry[]) {
 const local:Buffer[]=[],central:Buffer[]=[];let offset=0;
 for(const e of entries){
  const name=Buffer.from(e.name),method=e.method??0,data=method===8?deflateRawSync(e.data):e.data;
  const crc=e.crc??crc32(e.data),size=e.advertised??e.data.length,flags=e.flags??0x800;
  const header=Buffer.alloc(30);header.writeUInt32LE(0x04034b50);header.writeUInt16LE(20,4);header.writeUInt16LE(flags,6);header.writeUInt16LE(method,8);header.writeUInt32LE(crc,14);header.writeUInt32LE(data.length,18);header.writeUInt32LE(size,22);header.writeUInt16LE(name.length,26);
  local.push(header,name,data);
  const cd=Buffer.alloc(46);cd.writeUInt32LE(0x02014b50);cd.writeUInt16LE(0x314,4);cd.writeUInt16LE(20,6);cd.writeUInt16LE(flags,8);cd.writeUInt16LE(method,10);cd.writeUInt32LE(crc,16);cd.writeUInt32LE(data.length,20);cd.writeUInt32LE(size,24);cd.writeUInt16LE(name.length,28);cd.writeUInt32LE(((e.mode??0x8000)*65536)>>>0,38);cd.writeUInt32LE(offset,42);central.push(cd,name);offset+=header.length+name.length+data.length;
 }
 const directory=Buffer.concat(central),end=Buffer.alloc(22);end.writeUInt32LE(0x06054b50);end.writeUInt16LE(entries.length,8);end.writeUInt16LE(entries.length,10);end.writeUInt32LE(directory.length,12);end.writeUInt32LE(offset,16);
 return Buffer.concat([...local,directory,end]);
}
async function setup(romLimits?:RomLimits) {
 let now=1000;const server=createCoordinator({origins:[origin],romLimits,now:()=>now});server.listen(0,'127.0.0.1');await once(server,'listening');
 const url=`http://127.0.0.1:${(server.address() as {port:number}).port}`;
 const socket=new WebSocket(url.replace('http:','ws:')+'/ws',{origin});await once(socket,'open');
 const hello=new Promise<Extract<RoomEvent,{type:'result'}>>(resolve=>socket.once('message',raw=>resolve(JSON.parse(String(raw)))));
 socket.send(JSON.stringify({type:'hello',requestId:randomUUID()}));const result=await hello;assert.equal(result.ok,true);const token=result.ok?result.data.session!.token:'';
 const post=(bytes:Buffer,headers:Record<string,string>={})=>fetch(url+'/rom-extractions',{method:'POST',headers:{Origin:origin,Authorization:`Bearer ${token}`,'Content-Type':'application/zip',...headers},body:new Uint8Array(bytes)});
 const scratch=()=>readdirSync(server.romStore.directory).filter(name=>/^(archive|extracted)-/.test(name));
 const clear=async()=>{for(let i=0;i<100&&scratch().length;i++)await new Promise(resolve=>setTimeout(resolve,5));assert.deepEqual(scratch(),[]);};
 return {server,socket,url,token,post,scratch,clear,advance:(ms:number)=>{now+=ms;},close:async()=>{socket.terminate();await shutdown(server);}};
}

for(const method of [0,8])test(`HTTP extracts ${method===0?'stored':'deflated'} NES with exact identity and private cleanup`,async()=>{
 const t=await setup();try{
  const bytes=rom(),response=await t.post(archive([{name:'folder/',data:Buffer.alloc(0),mode:0x4000},{name:'folder/My Game.NES',data:bytes,method},{name:'notes.txt',data:Buffer.from('ignore')} ]));
  assert.equal(response.status,200);assert.deepEqual(Buffer.from(await response.arrayBuffer()),bytes);assert.equal(response.headers.get('X-NES-Name'),encodeURIComponent('My Game.nes'));assert.equal(response.headers.get('X-NES-SHA256'),createHash('sha256').update(bytes).digest('hex'));assert.equal(response.headers.get('Content-Length'),String(bytes.length));assert.equal(response.headers.get('Cache-Control'),'no-store');await t.clear();
 }finally{await t.close();}
});
test('HTTP automatically selects case-folded path with exact-path tie break',async()=>{
 const t=await setup();try{
  const bytes=rom(),other=Buffer.from(bytes);other[32]=2;
  const response=await t.post(archive([{name:'z.nes',data:other},{name:'a.nes',data:other},{name:'A.nes',data:bytes}]));assert.equal(response.status,200);assert.equal(response.headers.get('X-NES-Name'),'A.nes');assert.deepEqual(Buffer.from(await response.arrayBuffer()),bytes);await t.clear();
 }finally{await t.close();}
});
test('HTTP rejects an invalid selected game without choosing the next game',async()=>{
 const t=await setup();try{const response=await t.post(archive([{name:'b.nes',data:rom()},{name:'a.nes',data:Buffer.alloc(32)}]));assert.equal(response.status,400);assert.deepEqual(await response.json(),{error:'invalid_cartridge'});await t.clear();}finally{await t.close();}
});
const invalidCases:Array<[string,()=>Buffer,string]>=[
 ['empty',()=>archive([]),'archive_no_game'],
 ['no NES',()=>archive([{name:'notes.txt',data:Buffer.from('notes')}]),'archive_no_game'],
 ['corrupt',()=>Buffer.from('not a zip'),'invalid_archive'],
 ['bad CRC',()=>archive([{name:'game.nes',data:rom(),crc:1}]),'invalid_archive'],
 ['encrypted',()=>archive([{name:'game.nes',data:rom(),method:8,flags:0x801}]),'encrypted_archive'],
 ['unsupported compression',()=>archive([{name:'game.nes',data:rom(),method:12}]),'unsupported_archive'],
 ['traversal',()=>archive([{name:'../game.nes',data:rom()}]),'invalid_archive'],
 ['absolute path',()=>archive([{name:'/game.nes',data:rom()}]),'invalid_archive'],
 ['control characters',()=>archive([{name:'game\u0001.nes',data:rom()}]),'unsafe_archive'],
 ['symlink',()=>archive([{name:'game.nes',data:rom(),mode:0xa000}]),'unsafe_archive'],
 ['duplicate normalized name',()=>archive([{name:'e\u0301.nes',data:rom()},{name:'é.nes',data:rom()}]),'unsafe_archive'],
 ['inconsistent local filename',()=>{const b=archive([{name:'game.nes',data:rom()}]);b[30]=0x78;return b;},'invalid_archive'],
 ['inconsistent local method',()=>{const b=archive([{name:'game.nes',data:rom()}]);b.writeUInt16LE(8,8);return b;},'invalid_archive'],
 ['inflated bytes exceed declared size',()=>archive([{name:'game.nes',data:rom(),method:8,advertised:16}]),'invalid_archive'],
];
for(const [name,make,error] of invalidCases)test(`HTTP rejects ${name} and releases archive storage`,async()=>{
 const t=await setup();try{const response=await t.post(make());assert.equal(response.status,400);assert.deepEqual(await response.json(),{error});await t.clear();}finally{await t.close();}
});
test('HTTP bounds a long Unicode selected filename without changing NES bytes or identity',async()=>{
 const t=await setup();try{
  const bytes=rom(),name='X'+'😄'.repeat(5000)+'.NES';
  const response=await t.post(archive([{name,data:bytes,method:8}]));assert.equal(response.status,200);assert.deepEqual(Buffer.from(await response.arrayBuffer()),bytes);
  const selected=decodeURIComponent(response.headers.get('X-NES-Name')!);assert.ok(selected.endsWith('.nes'));assert.ok(selected.length<=84);assert.equal(selected.slice(0,1),'X');assert.equal(/\p{C}/u.test(selected),false);assert.equal(response.headers.get('X-NES-SHA256'),createHash('sha256').update(bytes).digest('hex'));await t.clear();
 }finally{await t.close();}
});
test('HTTP enforces strict decimal compressed limit and permits retry',async()=>{
 const t=await setup();try{
  for(const size of [ZIP_ARCHIVE_LIMIT,ZIP_ARCHIVE_LIMIT+1]){const response=await t.post(Buffer.alloc(size));assert.equal(response.status,413);assert.deepEqual(await response.json(),{error:'archive_size_limit'});}
  const entries=[{name:'game.nes',data:rom()},{name:'notes.txt',data:Buffer.alloc(0)}],overhead=archive(entries).length;
  entries[1].data=Buffer.alloc(ZIP_ARCHIVE_LIMIT-1-overhead);const bytes=archive(entries);assert.equal(bytes.length,ZIP_ARCHIVE_LIMIT-1);
  const response=await t.post(bytes);assert.equal(response.status,200);assert.deepEqual(Buffer.from(await response.arrayBuffer()),rom());await t.clear();
 }finally{await t.close();}
});
test('HTTP enforces actual compressed bytes for chunked bodies',async()=>{
 const t=await setup();try{
  const response=await new Promise<{status:number;body:string}>((resolve,reject)=>{
   const request=httpRequest(t.url+'/rom-extractions',{method:'POST',headers:{Origin:origin,Authorization:`Bearer ${t.token}`,'Content-Type':'application/zip'}},response=>{let body='';response.on('data',chunk=>body+=chunk);response.on('end',()=>resolve({status:response.statusCode!,body}));});request.on('error',reject);request.write(Buffer.alloc(ZIP_ARCHIVE_LIMIT-1));request.end(Buffer.from([0]));
  });assert.equal(response.status,413);assert.deepEqual(JSON.parse(response.body),{error:'archive_size_limit'});await t.clear();
 }finally{await t.close();}
});
test('HTTP rejects a chunked archive at the limit without waiting for its sender to finish',async()=>{
 const t=await setup();let request:ReturnType<typeof httpRequest>|undefined,deadline:ReturnType<typeof setTimeout>|undefined;
 try{
  const result=new Promise<{status:number;body:string}>((resolve,reject)=>{
   request=httpRequest(t.url+'/rom-extractions',{method:'POST',headers:{Origin:origin,Authorization:`Bearer ${t.token}`,'Content-Type':'application/zip'}},response=>{let body='';response.on('data',chunk=>body+=chunk);response.on('end',()=>resolve({status:response.statusCode!,body}));});request.on('error',()=>{});request.write(Buffer.alloc(ZIP_ARCHIVE_LIMIT));
   deadline=setTimeout(()=>reject(Error('The server waited for an over-limit sender to finish.')),2000);deadline.unref();
  });
  const response=await result;assert.equal(response.status,413);assert.deepEqual(JSON.parse(response.body),{error:'archive_size_limit'});await t.clear();
 }finally{clearTimeout(deadline);request?.destroy();await t.close();}
});
test('HTTP extraction requires allowed origin, authenticated session and valid content type',async()=>{
 const t=await setup();try{
  const bytes=archive([{name:'game.nes',data:rom()}]);
  for(const headers of [{Origin:'https://evil.example'},{Origin:''},{Authorization:'Bearer '+'x'.repeat(43)}] as Array<Record<string,string>>){const response=await t.post(bytes,headers);assert.equal(response.status,403);}
  const wrong=await t.post(bytes,{'Content-Type':'application/octet-stream'});assert.equal(wrong.status,400);await t.clear();
  const options=await fetch(t.url+'/rom-extractions',{method:'OPTIONS',headers:{Origin:origin}});assert.equal(options.status,204);assert.equal(options.headers.get('Access-Control-Allow-Origin'),origin);assert.match(options.headers.get('Access-Control-Expose-Headers')!,/X-NES-Name/);
 }finally{await t.close();}
});
test('HTTP extraction applies session rate limit without changing a room',async()=>{
 const t=await setup();try{
  for(let i=0;i<5;i++){const response=await t.post(archive([]));assert.equal(response.status,400);await response.json();}
  const denied=await t.post(archive([]));assert.equal(denied.status,429);assert.deepEqual(await denied.json(),{error:'rate_limited'});await t.clear();
 }finally{await t.close();}
});
test('HTTP extraction enforces existing inflated file and shared storage limits',async()=>{
 for(const limits of [{file:32,total:100_000,concurrent:4},{file:100_000,total:1000,concurrent:4}]){
  const t=await setup(limits);try{const response=await t.post(archive([{name:'game.nes',data:rom(),method:8}]));assert.equal(response.status,limits.file===32?413:429);assert.deepEqual(await response.json(),{error:limits.file===32?'upload_size_limit':'upload_capacity'});await t.clear();}finally{await t.close();}
 }
});
test('extraction and ordinary upload use the same concurrency/storage accounting; release is idempotent',()=>{
 const directory=mkdtempSync(join(tmpdir(),'retro-coop-zip-test-')),store=new RomStore(directory,{file:32,total:80,concurrent:1});
 try{const lease=store.beginExtraction(20,()=>{});lease.reserveOutput(32);assert.throws(()=>store.beginExtraction(1,()=>{}),/upload_capacity/);assert.throws(()=>lease.reserveOutput(33),/upload_size_limit/);lease.release();lease.release();const retry=store.beginExtraction(20,()=>{});retry.release();}finally{store.stop();}
});
test('startup removes orphaned ZIP scratch without touching unrelated files',()=>{
 const directory=mkdtempSync(join(tmpdir(),'retro-coop-zip-test-')),archivePath=join(directory,'archive-'+'a'.repeat(32)),output=join(directory,'extracted-'+'b'.repeat(32)),other=join(directory,'leave-me');writeFileSync(archivePath,'orphan');writeFileSync(output,'orphan');writeFileSync(other,'keep');
 const store=new RomStore(directory);try{assert.equal(existsSync(archivePath),false);assert.equal(existsSync(output),false);assert.equal(existsSync(other),true);}finally{store.stop();}
});
test('HTTP cancellation releases scratch and the shared concurrency slot for retry',async()=>{
 const t=await setup({file:100_000,total:200_000,concurrent:1});try{
  const bytes=archive([{name:'game.nes',data:rom()}]);
  const request=httpRequest(t.url+'/rom-extractions',{method:'POST',headers:{Origin:origin,Authorization:`Bearer ${t.token}`,'Content-Type':'application/zip','Content-Length':bytes.length}});request.on('error',()=>{});request.write(bytes.subarray(0,80));
  for(let i=0;i<100&&!t.scratch().length;i++)await new Promise(resolve=>setTimeout(resolve,5));assert.equal(t.scratch().length,1);
  const denied=await t.post(bytes);assert.equal(denied.status,429);assert.deepEqual(await denied.json(),{error:'upload_capacity'});
  request.destroy();await t.clear();
  const retry=await t.post(bytes);assert.equal(retry.status,200);await retry.arrayBuffer();await t.clear();
 }finally{await t.close();}
});
test('HTTP stalled preparation expires, cleans scratch and permits retry',async()=>{
 const t=await setup();try{
  const bytes=archive([{name:'game.nes',data:rom()}]);
  const request=httpRequest(t.url+'/rom-extractions',{method:'POST',headers:{Origin:origin,Authorization:`Bearer ${t.token}`,'Content-Type':'application/zip','Content-Length':bytes.length}});request.on('error',()=>{});request.write(bytes.subarray(0,80));
  for(let i=0;i<100&&!t.scratch().length;i++)await new Promise(resolve=>setTimeout(resolve,5));assert.equal(t.scratch().length,1);
  const closed=new Promise<void>(resolve=>request.once('close',()=>resolve()));t.advance(30_001);await closed;await t.clear();
  const retry=await t.post(bytes);assert.equal(retry.status,200);await retry.arrayBuffer();await t.clear();
 }finally{await t.close();}
});
test('HTTP extraction failure preserves a previously committed shared blob and lobby',async()=>{
 const t=await setup();try{
  const bytes=rom(),fingerprint={romSha256:createHash('sha256').update(bytes).digest('hex'),coreSha256:'b'.repeat(64),localSchema:1 as const,settings:'auto-region;zero-ram;48000hz;standard-p1-p2' as const,cartridge:{format:'iNES' as const,mapper:0,submapper:0,region:'NTSC',bytes:bytes.length}},intent=randomUUID();
  const room=t.server.rooms.handle(t.token,{type:'create',requestId:randomUUID(),intent,visibility:'public',fingerprint}).room!;
  const upload=await fetch(t.url+`/rooms/${room.id}/rom`,{method:'PUT',headers:{Origin:origin,Authorization:`Bearer ${t.token}`,'X-Room-Intent':intent,'Content-Type':'application/octet-stream'},body:bytes});assert.equal(upload.status,201);await upload.json();
  const confirmed=t.server.rooms.handle(t.token,{type:'confirmCreate',requestId:randomUUID(),intent}).room!,path=t.server.romStore.pathForRoom(room.id);
  const failure=await t.post(archive([{name:'bad.nes',data:bytes,crc:1}]));assert.equal(failure.status,400);await failure.json();assert.equal(t.server.romStore.pathForRoom(room.id),path);assert.equal(existsSync(path!),true);
  const retained=t.server.rooms.handle(t.token,{type:'confirmCreate',requestId:randomUUID(),intent}).room!;assert.equal(retained.id,confirmed.id);assert.deepEqual(retained.fingerprint,confirmed.fingerprint);assert.equal(retained.gameTitle,confirmed.gameTitle);await t.clear();
 }finally{await t.close();}
});
