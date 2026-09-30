import {listRoms,putRom,readRom,type RomRecord} from './saves.ts';
import {sha256} from './verified-download.ts';
import {catalog,type CatalogId} from '../../../packages/contracts/src/catalog.ts';
import type {Fingerprint} from '../../../packages/contracts/src/fingerprint.ts';

const maxLabel=80;
export type LibraryEntry={sha256:string;size:number;label:string;source:'import'|'download';lastUsedAt:number};
export type GameLibraryEntry=LibraryEntry&({kind:'saved'}|{kind:'included';catalogId:CatalogId});
export type SavedCandidate={file:File;sha256:string;size:number;generation:number;romGeneration:number};
export const safeLabel=(name:string)=>name.replace(/[\p{C}]/gu,'').trim().slice(0,maxLabel)||'NES game';
export function entry(record:RomRecord):LibraryEntry {
 return {sha256:record.sha256,size:record.size,label:safeLabel(record.label??'NES game'),source:record.source==='import'?'import':'download',lastUsedAt:Number.isFinite(record.lastUsedAt)?record.lastUsedAt!:record.savedAt};
}
export async function libraryEntries():Promise<LibraryEntry[]> {
 const {records}=await listRoms();return records.map(entry).sort((a,b)=>b.lastUsedAt-a.lastUsedAt);
}
export async function gameLibrary():Promise<GameLibraryEntry[]> {
 const stored=await libraryEntries();const included=new Set<string>(catalog.map(item=>item.sha256));
 return [
  ...catalog.map(item=>({sha256:item.sha256,size:item.bytes,label:item.title,source:'download' as const,lastUsedAt:stored.find(row=>row.sha256===item.sha256)?.lastUsedAt??0,kind:'included' as const,catalogId:item.id})),
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
export async function rememberImport(file:File,hash:string):Promise<boolean> {
 const bytes=new Uint8Array(await file.arrayBuffer());if(await sha256(bytes)!==hash)throw Error('The selected file changed while loading. Add it again.');
 const {generation,romGeneration}=await readRom(hash);
 await putRom({sha256:hash,size:bytes.length,bytes:bytes.slice().buffer,savedAt:Date.now(),lastUsedAt:Date.now(),source:'import',label:safeLabel(file.name)},generation,romGeneration);
 return true;
}
export async function rememberUse(sha256:string):Promise<void> {
 const {generation,romGeneration,record}=await readRom(sha256);if(!record)return;
 await putRom({...record,lastUsedAt:Date.now()},generation,romGeneration);
}
