import {createHash} from 'node:crypto';
import {createReadStream,createWriteStream} from 'node:fs';
import {open} from 'node:fs/promises';
import type {IncomingMessage,ServerResponse} from 'node:http';
import {Readable,Transform} from 'node:stream';
import {pipeline} from 'node:stream/promises';
import {crc32} from 'node:zlib';
import {openPromise,type Entry,type ZipFile} from 'yauzl';
import {ZIP_ARCHIVE_LIMIT,gameFileTitle} from '../../../packages/contracts/src/game-file.ts';
import {inspectCartridge} from '../../../packages/contracts/src/fingerprint.ts';
import {RoomError,type Rooms} from './rooms.ts';
import type {RomStore} from './rom-store.ts';

const compare = (a:string,b:string) => a<b?-1:a>b?1:0;
const normalized = (name:string) => name.normalize('NFC');
const pathKey = (name:string) => normalized(name).toLowerCase();
function validateEntry(entry:Entry) {
 const name=normalized(entry.fileName),segments=name.replace(/\/$/,'').split('/');
 if(!name || /[\p{C}\\]/u.test(name) || /^[a-z]:/i.test(name) || segments.some(part=>!part||part==='.'||part==='..'))throw new RoomError('unsafe_archive');
 const mode=(entry.externalFileAttributes>>>16)&0xf000;
 const directory=name.endsWith('/');
 if(mode!==0 && mode!==(directory?0x4000:0x8000) || !directory&&(entry.externalFileAttributes&0x10)!==0)throw new RoomError('unsafe_archive');
 if(entry.isEncrypted() || (entry.generalPurposeBitFlag&0x40)!==0)throw new RoomError('encrypted_archive');
 if(entry.compressionMethod!==0&&entry.compressionMethod!==8)throw new RoomError('unsupported_archive');
 return {name,directory};
}

async function selectedEntry(zip:ZipFile,progress:()=>void):Promise<Entry> {
 // Every central header occupies at least 46 bytes of the bounded archive.
 if(zip.entryCount>Math.floor(zip.fileSize/46))throw new RoomError('invalid_archive');
 const names=new Set<string>();let selected:Entry|undefined;
 for await(const entry of zip.eachEntry()) {
  progress();const {name,directory}=validateEntry(entry),key=pathKey(name);
  if(names.has(name))throw new RoomError('unsafe_archive');names.add(name);
  const local=await zip.readLocalFileHeaderPromise(entry);
  if(!local.fileName.equals(entry.fileNameRaw) || local.generalPurposeBitFlag!==entry.generalPurposeBitFlag || local.compressionMethod!==entry.compressionMethod)throw new RoomError('invalid_archive');
  // Bit 3 permits sizes/CRC to follow the data instead of being known in the local header.
  if(!(entry.generalPurposeBitFlag&8) && (local.crc32!==entry.crc32 || local.compressedSize!==entry.compressedSize || local.uncompressedSize!==entry.uncompressedSize))throw new RoomError('invalid_archive');
  if((entry.generalPurposeBitFlag&8) && (local.crc32!==0&&local.crc32!==entry.crc32 || local.compressedSize!==0&&local.compressedSize!==entry.compressedSize || local.uncompressedSize!==0&&local.uncompressedSize!==entry.uncompressedSize))throw new RoomError('invalid_archive');
  if(directory||!/\.nes$/i.test(name))continue;
  if(!selected || compare(key,pathKey(selected.fileName))<0 || key===pathKey(selected.fileName)&&compare(name,normalized(selected.fileName))<0)selected=entry;
 }
 if(!selected)throw new RoomError('archive_no_game');return selected;
}

/** ZIP bytes have no room authority. Only the extracted NES later enters normal admission. */
export async function extractZip(request:IncomingMessage,response:ServerResponse,rooms:Rooms,store:RomStore,token:string,length:number|undefined,now:()=>number) {
 const current=rooms.beginExtraction(token),controller=new AbortController();
 let lastProgress=now();const started=lastProgress;
 const progress=()=>{
  current();controller.signal.throwIfAborted();const time=now();
  if(time-started>=300_000 || time-lastProgress>=30_000)throw new RoomError('upload_expired');
  lastProgress=time;
 };
 const abort=()=>controller.abort(new RoomError('upload_cancelled'));
 controller.signal.addEventListener('abort',()=>request.destroy(),{once:true});
 const timer=setInterval(()=>{try{current();if(now()-started>=300_000||now()-lastProgress>=30_000)controller.abort(new RoomError('upload_expired'));}catch(error){controller.abort(error);}},1000);timer.unref();
 response.once('close',abort);
 let scratch:ReturnType<RomStore['beginExtraction']>|undefined,zip:ZipFile|undefined;
 try {
  if(length!==undefined&&(!Number.isSafeInteger(length)||length<=0||length>=ZIP_ARCHIVE_LIMIT))throw new RoomError('archive_size_limit');
  scratch=store.beginExtraction(length??0,abort);const owned=scratch;
  let received=0;
  await pipeline(Readable.from(request.iterator({destroyOnReturn:false})),new Transform({transform(chunk:Buffer,_encoding,callback){
   try{progress();received+=chunk.length;if(received>=ZIP_ARCHIVE_LIMIT)throw new RoomError('archive_size_limit');if(length!==undefined&&received>length)throw new RoomError('length_mismatch');owned.reserveArchive(received);callback(null,chunk);}catch(error){callback(error as Error);}
  }}),createWriteStream(scratch.archivePath,{flags:'wx',mode:0o600}),{signal:controller.signal});
  if(!received || length!==undefined&&received!==length)throw new RoomError('length_mismatch');
  progress();zip=await openPromise(scratch.archivePath,{lazyEntries:true,autoClose:false,validateEntrySizes:true,strictFileNames:true});
  const selected=await selectedEntry(zip,progress);progress();
  scratch.reserveOutput(selected.uncompressedSize);
  const stream=await zip.openReadStreamPromise(selected),hash=createHash('sha256');let bytes=0,crc=0;
  await pipeline(stream,new Transform({transform(chunk:Buffer,_encoding,callback){
   try{progress();bytes+=chunk.length;owned.reserveOutput(bytes);crc=crc32(chunk,crc);hash.update(chunk);callback(null,chunk);}catch(error){callback(error as Error);}
  }}),createWriteStream(scratch.outputPath,{flags:'wx',mode:0o600}),{signal:controller.signal});
  if(bytes!==selected.uncompressedSize||crc!==selected.crc32)throw new RoomError('invalid_archive');
  const file=await open(scratch.outputPath,'r');let header:Buffer;
  try{header=Buffer.alloc(16);const read=await file.read(header,0,16,0);if(read.bytesRead!==16)throw new RoomError('invalid_cartridge');}finally{await file.close();}
  try{inspectCartridge(header,bytes);}catch{throw new RoomError('invalid_cartridge');}
  progress();const name=gameFileTitle(normalized(selected.fileName).split('/').at(-1)!)+'.nes';
  response.writeHead(200,{'Content-Type':'application/octet-stream','Content-Length':bytes,'X-NES-Name':encodeURIComponent(name),'X-NES-SHA256':hash.digest('hex'),'X-Content-Type-Options':'nosniff'});
  await pipeline(createReadStream(scratch.outputPath),new Transform({transform(chunk,_encoding,callback){try{progress();callback(null,chunk);}catch(error){callback(error as Error);}}}),response,{signal:controller.signal});
 } catch(error) {
  request.resume();
  const reason=controller.signal.aborted?controller.signal.reason:error;
  if(reason instanceof RoomError)throw reason;
  if((reason as NodeJS.ErrnoException)?.code==='ENOSPC')throw new RoomError('upload_capacity');
  throw new RoomError('invalid_archive');
 } finally {
  clearInterval(timer);response.off('close',abort);zip?.close();scratch?.release();
 }
}
