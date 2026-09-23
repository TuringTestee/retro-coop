import {listRoms,putRom,readRom,type RomRecord} from './saves.ts';
import {sha256} from './verified-download.ts';
import {catalog,type CatalogId} from '../../../packages/contracts/src/catalog.ts';
import type {Fingerprint} from '../../../packages/contracts/src/fingerprint.ts';

const maxLabel=80,maxPreview=32_000;
export type LibraryEntry={sha256:string;size:number;label:string;source:'import'|'download';lastUsedAt:number;preview?:string};
export type GameLibraryEntry=LibraryEntry&({kind:'saved'}|{kind:'included';catalogId:CatalogId});
export type SavedCandidate={file:File;sha256:string;size:number;generation:number;romGeneration:number};
export const safeLabel=(name:string)=>name.replace(/[\p{C}]/gu,'').trim().slice(0,maxLabel)||'NES game';
export function validPreview(value:unknown):value is string {
 if(typeof value!=='string'||value.length>maxPreview||!/^data:image\/webp;base64,[A-Za-z0-9+/]+={0,2}$/.test(value))return false;
 try{
  const raw=atob(value.slice('data:image/webp;base64,'.length));
  if(raw.length<30||raw.slice(0,4)!=='RIFF'||raw.slice(8,12)!=='WEBP')return false;
  const u8=(i:number)=>raw.charCodeAt(i),u16=(i:number)=>u8(i)|(u8(i+1)<<8),u24=(i:number)=>u8(i)|(u8(i+1)<<8)|(u8(i+2)<<16);
  const size=(u8(4)|(u8(5)<<8)|(u8(6)<<16)|(u8(7)<<24))>>>0;
  if(size!==raw.length-8)return false;
  const chunk=raw.slice(12,16);let width=0,height=0;
  if(chunk==='VP8 '&&raw.slice(23,26)==='\x9d\x01\x2a'){width=u16(26)&0x3fff;height=u16(28)&0x3fff;}
  else if(chunk==='VP8L'&&u8(20)===0x2f){width=1+(u8(21)|((u8(22)&0x3f)<<8));height=1+((u8(22)>>6)|(u8(23)<<2)|((u8(24)&0xf)<<10));}
  else if(chunk==='VP8X'){width=1+u24(24);height=1+u24(27);}
  return width>0&&width<=128&&height>0&&height<=120;
 }catch{return false;}
}
export function entry(record:RomRecord):LibraryEntry {
 return {sha256:record.sha256,size:record.size,label:safeLabel(record.label??'NES game'),source:record.source==='import'?'import':'download',lastUsedAt:Number.isFinite(record.lastUsedAt)?record.lastUsedAt!:record.savedAt,...(validPreview(record.preview)?{preview:record.preview}:{})};
}
export async function libraryEntries():Promise<LibraryEntry[]> {
 const {records}=await listRoms();return records.map(entry).sort((a,b)=>b.lastUsedAt-a.lastUsedAt);
}
export async function gameLibrary():Promise<GameLibraryEntry[]> {
 const stored=await libraryEntries();const included=new Set<string>(catalog.map(item=>item.sha256));
 return [
  ...catalog.map(item=>({sha256:item.sha256,size:item.bytes,label:item.title,source:'download' as const,lastUsedAt:stored.find(row=>row.sha256===item.sha256)?.lastUsedAt??0,preview:stored.find(row=>row.sha256===item.sha256)?.preview,kind:'included' as const,catalogId:item.id})),
  ...stored.filter(row=>!included.has(row.sha256)).map(row=>({...row,kind:'saved' as const})),
 ];
}
export async function verifiedSavedFile(hash:string):Promise<File> {
 const {record}=await readRom(hash);
 if(!record||record.sha256!==hash||!Number.isSafeInteger(record.size)||record.size<=0||!(record.bytes instanceof ArrayBuffer)||record.bytes.byteLength!==record.size||await sha256(new Uint8Array(record.bytes))!==hash)throw Error('This saved game is missing or damaged. Add the NES file again.');
 return new File([record.bytes],safeLabel(record.label??'saved-game.nes'),{type:'application/octet-stream'});
}
export async function savedCandidate(hash:string):Promise<SavedCandidate> {
 const initial=await readRom(hash),file=await verifiedSavedFile(hash),latest=await readRom(hash);
 if(initial.generation!==latest.generation||initial.romGeneration!==latest.romGeneration||!latest.record)throw Error('This saved game changed in another tab. Add the NES file again.');
 return {file,sha256:hash,size:file.size,generation:latest.generation,romGeneration:latest.romGeneration};
}
export async function candidateStillStored(candidate:SavedCandidate,loaded:Pick<Fingerprint,'romSha256'|'cartridge'>):Promise<boolean> {
 if(loaded.romSha256!==candidate.sha256||loaded.cartridge.bytes!==candidate.size)return false;
 const {generation,romGeneration,record}=await readRom(candidate.sha256);
 return generation===candidate.generation&&romGeneration===candidate.romGeneration&&record?.size===candidate.size&&record.bytes instanceof ArrayBuffer&&record.bytes.byteLength===candidate.size&&await sha256(new Uint8Array(record.bytes))===candidate.sha256;
}
export function previewDisplay(recent:LibraryEntry|undefined):{image:string;alt:string}|{text:'No preview yet.'} {
 return recent?.preview&&validPreview(recent.preview)?{image:recent.preview,alt:`Recent game preview: ${recent.label}`}:{text:'No preview yet.'};
}
export async function rememberImport(file:File,hash:string):Promise<boolean> {
 const bytes=new Uint8Array(await file.arrayBuffer());if(await sha256(bytes)!==hash)throw Error('The selected file changed while loading. Add it again.');
 const {generation,romGeneration}=await readRom(hash);
 await putRom({sha256:hash,size:bytes.length,bytes:bytes.slice().buffer,savedAt:Date.now(),lastUsedAt:Date.now(),source:'import',label:safeLabel(file.name)},generation,romGeneration);
 return true;
}
export async function rememberPreview(sha256:string,preview:string):Promise<boolean> {
 if(!validPreview(preview))return false;
 const {generation,romGeneration,record}=await readRom(sha256);if(!record)return false;
 await putRom({...record,preview,lastUsedAt:Date.now()},generation,romGeneration);
 return true;
}
export function capturePreview(canvas:HTMLCanvasElement):string|undefined {
 const context=canvas.getContext('2d',{willReadFrequently:true});if(!context)return;
 const {data}=context.getImageData(0,0,canvas.width,canvas.height);
 let min=255,max=0,opaque=0;for(let i=0;i<data.length;i+=4){const value=(data[i]+data[i+1]+data[i+2])/3;min=Math.min(min,value);max=Math.max(max,value);if(data[i+3]>0)opaque++;}
 if(opaque<data.length/16||max-min<12)return;
 const small=document.createElement('canvas');small.width=128;small.height=120;small.getContext('2d')?.drawImage(canvas,0,0,128,120);
 const value=small.toDataURL('image/webp',0.5);return validPreview(value)?value:undefined;
}
