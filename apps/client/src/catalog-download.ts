import {catalogAssetPath,type CatalogEntry} from '../../../packages/contracts/src/catalog.ts';

export async function downloadCatalogEntry(entry:CatalogEntry,signal:AbortSignal,progress:(bytes:number)=>void,fetcher:typeof fetch=fetch):Promise<File> {
 signal.throwIfAborted();const response=await fetcher(catalogAssetPath(entry),{signal,credentials:'omit',redirect:'error',cache:'default'});
 if(!response.ok||!response.body)throw Error(`${entry.title} could not download. Retry, or choose a local game.`);
 const length=response.headers.get('Content-Length');if(length!==null&&Number(length)!==entry.bytes){await response.body.cancel();throw Error(`${entry.title} has the wrong download size. Retry.`);}
 const reader=response.body.getReader(),bytes=new Uint8Array(entry.bytes);let offset=0;
 try {while(true){signal.throwIfAborted();const {done,value}=await reader.read();signal.throwIfAborted();if(done)break;if(value.length>bytes.length-offset)throw Error(`${entry.title} downloaded more data than expected. Retry.`);bytes.set(value,offset);offset+=value.length;progress(offset);}if(offset!==bytes.length)throw Error(`${entry.title} download ended early. Retry.`);const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');signal.throwIfAborted();if(hash!==entry.sha256)throw Error(`${entry.title} did not match the verified game. Retry.`);return new File([bytes],`${entry.title}.nes`,{type:'application/octet-stream'});}finally{await reader.cancel().catch(()=>{});reader.releaseLock();}
}
