import {putRom,readRom,type RomRecord} from './saves.ts';
import {sha256} from './verified-download.ts';

export type AcquiredRom={file:File;source:'cache'|'download';persisted:boolean;notice?:string};
const memoryNotice='Available in this tab; download again next time.';

/** Catalog and host-room sources use the same verified cache and cross-tab clear guard. */
export async function acquireVerifiedRom(expected:{bytes:number;sha256:string},fileName:string,signal:AbortSignal,current:()=>boolean,download:()=>Promise<Uint8Array>):Promise<AcquiredRom> {
 const check=()=>{signal.throwIfAborted();if(!current())throw Error('The room changed. Return to rooms and join again.');};
 const file=(bytes:BlobPart)=>new File([bytes],fileName,{type:'application/octet-stream'});
 check();let generation:number|undefined;
 try {
  const saved=await readRom(expected.sha256);check();generation=saved.generation;
  const record=saved.record;
  if(record?.sha256===expected.sha256 && record.size===expected.bytes && record.bytes instanceof ArrayBuffer && record.bytes.byteLength===record.size && await sha256(new Uint8Array(record.bytes))===record.sha256){
   check();return {file:file(record.bytes),source:'cache',persisted:true};
  }
 }catch(error){check();/* IndexedDB may be denied; verified network bytes can still play. */}
 const bytes=await download();check();
 // A source must not bypass validation merely because it shares this cache helper.
 if(bytes.length!==expected.bytes || await sha256(bytes)!==expected.sha256)throw Error('The game did not match the verified game. Retry.');
 check();const playable=file(bytes as Uint8Array<ArrayBuffer>);
 if(generation===undefined)return {file:playable,source:'download',persisted:false,notice:memoryNotice};
 try {
  const record:RomRecord={sha256:expected.sha256,size:bytes.length,bytes:bytes.slice().buffer,savedAt:Date.now()};
  await putRom(record,generation);check();
  const stored=await readRom(expected.sha256);check();
  if(stored.record?.bytes instanceof ArrayBuffer && stored.record.bytes.byteLength===bytes.length && await sha256(new Uint8Array(stored.record.bytes))===expected.sha256){check();return {file:playable,source:'download',persisted:true};}
 }catch(error){check();}
 return {file:playable,source:'download',persisted:false,notice:memoryNotice};
}
