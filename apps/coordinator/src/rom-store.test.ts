import {test} from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {createHash,randomUUID} from 'node:crypto';
import {readFileSync,existsSync,mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {WebSocket} from 'ws';
import {createCoordinator,shutdown} from './server.ts';
import {RomStore} from './rom-store.ts';
import type {Fingerprint,RoomEvent,RoomCommand} from '../../../packages/contracts/src/rooms.ts';
const origin='http://127.0.0.1:5173';
const rom=()=>{const bytes=Buffer.alloc(16+16384);bytes.set([0x4e,0x45,0x53,0x1a,1,0]);return bytes;};
const fingerprint=(bytes:Buffer):Fingerprint=>({romSha256:createHash('sha256').update(bytes).digest('hex'),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:0,submapper:0,region:'NTSC',bytes:bytes.length}});
type Command=RoomCommand extends infer T ? T extends RoomCommand ? Omit<T,'requestId'> : never : never;
async function setup(romLimits?:{file:number;total:number;concurrent:number}) {
 let now=1000;const server=createCoordinator({origins:[origin],requireCustomUpload:true,now:()=>now,romLimits});server.listen(0,'127.0.0.1');await once(server,'listening');
 const url=`http://127.0.0.1:${(server.address() as {port:number}).port}`,socket=new WebSocket(url.replace('http','ws')+'/ws',{origin});await once(socket,'open');
 const command=async(value:Command)=>{const requestId=randomUUID();const result=new Promise<Extract<RoomEvent,{type:'result'}>>(resolve=>{const listener=(raw:Buffer)=>{const event=JSON.parse(raw.toString()) as RoomEvent;if(event.type==='result'&&event.requestId===requestId){socket.off('message',listener);resolve(event);}};socket.on('message',listener);});socket.send(JSON.stringify({...value,requestId}));return result;};
 const hello=await command({type:'hello'});assert.equal(hello.ok,true);const token=hello.ok?hello.data.session!.token:'';
 const create=async(bytes=rom())=>{const intent=randomUUID(),result=await command({type:'create',intent,visibility:'public',fingerprint:fingerprint(bytes)});assert.equal(result.ok,true);return {intent,roomId:result.ok?result.data.room!.id:'',bytes};};
 const upload=(roomId:string,intent:string,bytes:Buffer,auth=token,headers:Record<string,string>={})=>fetch(`${url}/rooms/${roomId}/rom`,{method:'PUT',headers:{Origin:origin,Authorization:`Bearer ${auth}`,'X-Room-Intent':intent,'Content-Type':'application/octet-stream',...headers},body:new Uint8Array(bytes)});
 return {server,socket,url,command,create,upload,token,advance:(ms:number)=>{now+=ms;server.rooms.sweep();},close:async()=>{socket.terminate();await shutdown(server);}};
}
test('private upload commits exact bytes before a custom room is publishable',async()=>{
 const t=await setup();try {
  const {intent,roomId,bytes}=await t.create();
  assert.equal((await t.command({type:'confirmCreate',intent})).ok,false);
  assert.equal((await t.upload(roomId,intent,bytes,'x'.repeat(43))).status,403);
  assert.equal((await t.upload(roomId,randomUUID(),bytes)).status,400);
  const success=await t.upload(roomId,intent,bytes);assert.equal(success.status,201);assert.deepEqual(await success.json(),{bytes:bytes.length,sha256:fingerprint(bytes).romSha256});
  const path=t.server.romStore.pathForRoom(roomId)!;assert.deepEqual(readFileSync(path),bytes);
  assert.equal((await t.command({type:'confirmCreate',intent})).ok,true);
  await t.command({type:'close',roomId});assert.equal(existsSync(path),false);
 }finally{await t.close();}
});
test('only the current guest membership can download private bytes',async()=>{
 const t=await setup();try{
  const {intent,roomId,bytes}=await t.create();assert.equal((await t.upload(roomId,intent,bytes)).status,201);
  const confirmed=await t.command({type:'confirmCreate',intent});assert.equal(confirmed.ok,true);
  const invite=confirmed.ok?confirmed.data.room!.invite:'';
  const guest=t.server.rooms.attach(undefined,()=>{},()=>{}),other=t.server.rooms.attach(undefined,()=>{},()=>{});
  const joined=t.server.rooms.handle(guest.token,{type:'join',requestId:randomUUID(),invite,intent:randomUUID()}).room!;
  const get=(auth:string,membership:string,id=roomId,headers:Record<string,string>={})=>fetch(`${t.url}/rooms/${id}/rom`,{headers:{Authorization:`Bearer ${auth}`,'X-Room-Membership':membership,...headers}});
  const noOrigin=await get(guest.token,joined.chatMembership);
  assert.equal(noOrigin.status,200);assert.equal(noOrigin.headers.get('Access-Control-Allow-Origin'),null);assert.deepEqual(Buffer.from(await noOrigin.arrayBuffer()),bytes);
  const missingToken=await fetch(`${t.url}/rooms/${roomId}/rom`,{headers:{'X-Room-Membership':joined.chatMembership}});
  assert.equal(missingToken.status,403);assert.deepEqual(await missingToken.json(),{error:'session_expired'});
  assert.equal((await get(other.token,joined.chatMembership)).status,403);
  assert.equal((await get(t.token,joined.chatMembership)).status,403);
  assert.equal((await get(guest.token,'x'.repeat(43))).status,403);
  assert.equal((await get(guest.token,joined.chatMembership,'x'.repeat(43))).status,403);
  const denied=await get(guest.token,joined.chatMembership,roomId,{Origin:'https://evil.example'});
  assert.equal(denied.status,403);assert.deepEqual(await denied.json(),{error:'origin_denied'});assert.equal(denied.headers.get('Access-Control-Allow-Origin'),null);
  const downloaded=await get(guest.token,joined.chatMembership,roomId,{Origin:origin});assert.equal(downloaded.status,200);assert.equal(downloaded.headers.get('Access-Control-Allow-Origin'),origin);assert.equal(downloaded.headers.get('Cache-Control'),'no-store');assert.equal(downloaded.headers.get('Content-Disposition'),null);assert.equal(Number(downloaded.headers.get('Content-Length')),bytes.length);assert.deepEqual(Buffer.from(await downloaded.arrayBuffer()),bytes);
  for(const method of ['PUT','OPTIONS']){
   const noOriginResponse=await fetch(`${t.url}/rooms/${roomId}/rom`,{method});assert.equal(noOriginResponse.status,403);assert.deepEqual(await noOriginResponse.json(),{error:'origin_denied'});
   const disallowed=await fetch(`${t.url}/rooms/${roomId}/rom`,{method,headers:{Origin:'https://evil.example'}});assert.equal(disallowed.status,403);assert.equal(disallowed.headers.get('Access-Control-Allow-Origin'),null);
  }
  const preflight=await fetch(`${t.url}/rooms/${roomId}/rom`,{method:'OPTIONS',headers:{Origin:origin}});assert.equal(preflight.status,204);assert.equal(preflight.headers.get('Access-Control-Allow-Origin'),origin);
  t.server.rooms.handle(guest.token,{type:'leave',requestId:randomUUID(),intent:joined.reservationIntent!});
  const replacement=t.server.rooms.attach(undefined,()=>{},()=>{});
  const next=t.server.rooms.handle(replacement.token,{type:'join',requestId:randomUUID(),invite,intent:randomUUID()}).room!;
  assert.equal((await get(guest.token,joined.chatMembership)).status,403);
  assert.equal((await get(replacement.token,joined.chatMembership)).status,403);
  const replacementDownload=await get(replacement.token,next.chatMembership);assert.equal(replacementDownload.status,200);assert.deepEqual(Buffer.from(await replacementDownload.arrayBuffer()),bytes);
  await t.command({type:'close',roomId});assert.equal((await get(replacement.token,next.chatMembership)).status,403);
 }finally{await t.close();}
});
test('download progress extends only its guest reservation within five minutes',async()=>{
 const t=await setup();try{
  const {intent,roomId,bytes}=await t.create();assert.equal((await t.upload(roomId,intent,bytes)).status,201);
  const confirmed=await t.command({type:'confirmCreate',intent});const invite=confirmed.ok?confirmed.data.room!.invite:'';
  const guest=t.server.rooms.attach(undefined,()=>{},()=>{}),joined=t.server.rooms.handle(guest.token,{type:'join',requestId:randomUUID(),invite,intent:randomUUID()}).room!;
  const lease=t.server.rooms.beginDownload(guest.token,roomId,joined.chatMembership);
  for(let i=0;i<4;i++){t.advance(25_000);t.server.rooms.handle(t.token,{type:'heartbeat',requestId:randomUUID()});t.server.rooms.downloadProgress(roomId,lease.id);}
  assert.throws(()=>t.server.rooms.beginDownload(guest.token,roomId,joined.chatMembership),/download_busy/);
  t.advance(31_000);assert.throws(()=>t.server.rooms.downloadProgress(roomId,lease.id),/download_expired/);
  const retry=t.server.rooms.beginDownload(guest.token,roomId,joined.chatMembership);
  for(let i=0;i<6;i++){t.advance(25_000);t.server.rooms.handle(t.token,{type:'heartbeat',requestId:randomUUID()});t.server.rooms.downloadProgress(roomId,retry.id);}
  t.advance(20_000);assert.throws(()=>t.server.rooms.downloadProgress(roomId,retry.id),/download_expired|room_changed/);
 }finally{await t.close();}
});
test('bad bytes and cancellation release private capacity without publishing',async()=>{
 const t=await setup();try {
  const a=await t.create(),corrupt=Buffer.from(a.bytes);corrupt[32]=1;
  assert.equal((await t.upload(a.roomId,a.intent,corrupt)).status,400);
  assert.equal(t.server.romStore.pathForRoom(a.roomId),undefined);
  assert.equal((await t.command({type:'confirmCreate',intent:a.intent})).ok,false);
  await t.command({type:'cancelCreate',intent:a.intent});
  assert.equal((await t.upload(a.roomId,a.intent,a.bytes)).status,400);
  const b=await t.create();assert.equal((await t.upload(b.roomId,b.intent,b.bytes.subarray(0,-1))).status,400);
  t.advance(5000);assert.equal((await t.command({type:'confirmCreate',intent:b.intent})).ok,false);
 }finally{await t.close();}
});
test('startup removes orphaned ROM files from a private prior process directory',()=>{
 const directory=mkdtempSync(join(tmpdir(),'retro-coop-rt1-restart-'));
 try {
  const orphan=join(directory,'upload-'+'a'.repeat(32)),blob=join(directory,'blob-'+'b'.repeat(32));
  writeFileSync(orphan,'partial');writeFileSync(blob,'old room');writeFileSync(join(directory,'owner.lock'),'99999999');
  const store=new RomStore(directory);assert.equal(existsSync(orphan),false);assert.equal(existsSync(blob),false);store.stop();
 }finally{rmSync(directory,{recursive:true,force:true});}
});
test('a matching hash still cannot commit an invalid or mismatched NES structure',async()=>{
 const t=await setup();try {
  const invalid=Buffer.alloc(rom().length),first=await t.create(invalid);
  const rejected=await t.upload(first.roomId,first.intent,invalid);assert.deepEqual(await rejected.json(),{error:'invalid_cartridge'});
  await t.command({type:'cancelCreate',intent:first.intent});
  const bytes=rom(),intent=randomUUID(),declared=fingerprint(bytes);declared.cartridge.mapper=1;
  const created=await t.command({type:'create',intent,visibility:'public',fingerprint:declared});assert.equal(created.ok,true);
  const roomId=created.ok?created.data.room!.id:'';
  const mismatch=await t.upload(roomId,intent,bytes);assert.deepEqual(await mismatch.json(),{error:'cartridge_mismatch'});
  assert.equal((await t.command({type:'confirmCreate',intent})).ok,false);
 }finally{await t.close();}
});
test('capacity and origin denial leave the room hidden and preserve the first private blob',async()=>{
 const bytes=rom(),t=await setup({file:bytes.length,total:bytes.length,concurrent:1});try {
  const first=await t.create(bytes);assert.equal((await t.upload(first.roomId,first.intent,bytes)).status,201);
  const secondHost=t.server.rooms.attach(undefined,()=>{},()=>{}),intent=randomUUID();
  const second=t.server.rooms.handle(secondHost.token,{type:'create',requestId:randomUUID(),intent,visibility:'public',fingerprint:fingerprint(bytes)}).room!;
  const denied=await t.upload(second.id,intent,bytes,secondHost.token);assert.equal(denied.status,429);assert.deepEqual(await denied.json(),{error:'upload_capacity'});
  assert.throws(()=>t.server.rooms.handle(secondHost.token,{type:'confirmCreate',requestId:randomUUID(),intent}),/upload_required/);
  const wrongOrigin=await t.upload(second.id,intent,bytes,secondHost.token,{Origin:'https://evil.example'});assert.equal(wrongOrigin.status,403);
  assert.deepEqual(readFileSync(t.server.romStore.pathForRoom(first.roomId)!),bytes);
 }finally{await t.close();}
});
test('progressing lease crosses five-second sweep but idle and total bounds close the intent',async()=>{
 const t=await setup();try {
  const a=await t.create();const lease=t.server.rooms.beginUpload(t.token,a.roomId,a.intent,a.bytes.length);
  t.advance(6000);t.server.rooms.uploadProgress(a.roomId,lease.id);
  assert.equal((await t.command({type:'confirmCreate',intent:a.intent})).ok,false);
  t.advance(30_000);assert.throws(()=>t.server.rooms.uploadProgress(a.roomId,lease.id),/upload_expired|not_in_room/);
  const b=await t.create(),second=t.server.rooms.beginUpload(t.token,b.roomId,b.intent,b.bytes.length);
  for(let i=0;i<10;i++){t.advance(29_000);t.server.rooms.uploadProgress(b.roomId,second.id);}
  t.advance(10_000);assert.throws(()=>t.server.rooms.uploadProgress(b.roomId,second.id),/upload_expired/);
 }finally{await t.close();}
});
