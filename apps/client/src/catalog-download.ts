import {catalogAssetPath,type CatalogEntry} from '../../../packages/contracts/src/catalog.ts';
import {verifiedDownload} from './verified-download.ts';
import {acquireVerifiedRom} from './rom-acquisition.ts';

export async function acquireCatalogEntry(entry:CatalogEntry,signal:AbortSignal,progress:(bytes:number)=>void,fetcher:typeof fetch=fetch) {
 return acquireVerifiedRom(entry,`${entry.title}.nes`,signal,()=>true,async()=>{
  signal.throwIfAborted();let response:Response;try{response=await fetcher(catalogAssetPath(entry),{signal,credentials:'omit',redirect:'error',cache:'default'});}catch(error){signal.throwIfAborted();throw Error(`${entry.title} could not download. Retry, or choose a local game.`,{cause:error});}
  if(!response.ok||!response.body)throw Error(`${entry.title} could not download. Retry, or choose a local game.`);
  return verifiedDownload(response,entry,signal,progress);
 });
}
export async function downloadCatalogEntry(entry:CatalogEntry,signal:AbortSignal,progress:(bytes:number)=>void,fetcher:typeof fetch=fetch):Promise<File> {return (await acquireCatalogEntry(entry,signal,progress,fetcher)).file;}
