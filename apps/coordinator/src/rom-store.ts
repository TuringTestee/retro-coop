import {createHash,randomBytes} from 'node:crypto';
import {existsSync,mkdirSync,mkdtempSync,readdirSync,rmSync,renameSync,openSync,closeSync,readFileSync,writeFileSync,statSync} from 'node:fs';
import {open} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import type {IncomingMessage} from 'node:http';
import {inspectCartridge} from '../../../packages/contracts/src/fingerprint.ts';
import {RoomError,Rooms} from './rooms.ts';

export const ROM_LIMITS={file:64*1024*1024,total:256*1024*1024,concurrent:4} as const;
export type RomLimits={file:number;total:number;concurrent:number};
type Entry={roomId:string;bytes:number;path:string;request?:IncomingMessage;committed:boolean};
/** Private files have server-generated names. The directory belongs to one coordinator process. */
export class RomStore {
 private entries=new Map<string,Entry>();
 private used=0;
 private limits:RomLimits;
 private lock:string;
 readonly directory:string;
 constructor(directory=mkdtempSync(join(tmpdir(),'retro-coop-rom-store-')),limits:RomLimits=ROM_LIMITS) {
  this.limits=limits;
  this.directory=resolve(directory);mkdirSync(this.directory,{recursive:true,mode:0o700});
  const info=statSync(this.directory);if((info.mode&0o077)!==0 || (process.getuid && info.uid!==process.getuid()))throw Error('ROM storage directory must be private to the coordinator');
  this.lock=join(this.directory,'owner.lock');
  if(existsSync(this.lock)){
   const prior=Number(readFileSync(this.lock,'utf8'));
   try {if(Number.isInteger(prior)&&prior>0)process.kill(prior,0);throw Error('ROM storage directory is already in use');}
   catch(error) {if((error as NodeJS.ErrnoException).code!=='ESRCH')throw error;rmSync(this.lock,{force:true});}
  }
  const fd=openSync(this.lock,'wx',0o600);writeFileSync(fd,String(process.pid));closeSync(fd);
  // Rooms are ephemeral across restart, so no prior ROM is valid after boot.
  for(const name of readdirSync(this.directory))if(/^(upload|blob)-[a-f0-9]{32}$/.test(name))rmSync(join(this.directory,name),{force:true});
 }
 private path(prefix:'upload'|'blob') {return join(this.directory,`${prefix}-${randomBytes(16).toString('hex')}`);}
 discard(roomId:string) {const entry=this.entries.get(roomId);if(!entry)return;this.entries.delete(roomId);this.used-=entry.bytes;entry.request?.destroy();rmSync(entry.path,{force:true});}
 stop() {for(const roomId of [...this.entries.keys()])this.discard(roomId);rmSync(this.lock,{force:true});}
 private reserve(roomId:string,bytes:number,request:IncomingMessage) {
  if(!Number.isSafeInteger(bytes)||bytes<16||bytes>this.limits.file)throw new RoomError('upload_size_limit');
  if(this.entries.has(roomId))throw new RoomError('upload_unavailable');
  if(this.used+bytes>this.limits.total || [...this.entries.values()].filter(entry=>!entry.committed).length>=this.limits.concurrent)throw new RoomError('upload_capacity');
  const entry:Entry={roomId,bytes,path:this.path('upload'),request,committed:false};this.entries.set(roomId,entry);this.used+=bytes;return entry;
 }
 async upload(rooms:Rooms,token:string,roomId:string,intent:string,bytes:number,request:IncomingMessage) {
  const begun=rooms.beginUpload(token,roomId,intent,bytes),lease=begun.id;
  let entry:Entry|undefined;
  try {
   entry=this.reserve(roomId,bytes,request);
   const handle=await open(entry.path,'wx',0o600),hash=createHash('sha256'),header=Buffer.alloc(16);let received=0;
   try {
    if(this.entries.get(roomId)!==entry)throw new RoomError('upload_cancelled');
    for await(const chunk of request) {
     rooms.uploadProgress(roomId,lease);if(!this.entries.has(roomId))throw new RoomError('upload_cancelled');
     const data=chunk as Buffer;if(received+data.length>bytes)throw new RoomError('length_mismatch');
     if(received<16)data.copy(header,received,0,Math.min(data.length,16-received));
     received+=data.length;hash.update(data);await handle.write(data);
    }
    await handle.sync();
   } finally {await handle.close();}
   if(received!==bytes)throw new RoomError('length_mismatch');
   if(hash.digest('hex')!==begun.fingerprint.romSha256)throw new RoomError('hash_mismatch');
   let cartridge;try {cartridge=inspectCartridge(header,bytes);}catch {throw new RoomError('invalid_cartridge');}
   const expected=begun.fingerprint.cartridge;
   if(cartridge.format!==expected.format || cartridge.mapper!==expected.mapper || cartridge.submapper!==expected.submapper || cartridge.region!==expected.region || cartridge.bytes!==expected.bytes)throw new RoomError('cartridge_mismatch');
   const path=this.path('blob');renameSync(entry.path,path);entry.path=path;entry.request=undefined;entry.committed=true;
   rooms.commitUpload(roomId,lease,path);
   return {bytes,sha256:begun.fingerprint.romSha256};
  } catch(error) {
   rooms.failUpload(roomId,lease);
   if(entry){entry.request=undefined;this.discard(roomId);rmSync(entry.path,{force:true});}
   throw error;
  }
 }
 pathForRoom(roomId:string) {const entry=this.entries.get(roomId);return entry?.committed?entry.path:undefined;}
}
