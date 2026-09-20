import {featuredGame,featuredAssetPath} from '../../../packages/contracts/src/catalog.ts';

/** Bounded exact-byte fetch. Cancellation also covers a completed response awaiting hashing. */
export async function downloadFeatured(signal:AbortSignal,progress:(bytes:number)=>void,fetcher:typeof fetch=fetch):Promise<File> {
 signal.throwIfAborted();
 const response=await fetcher(featuredAssetPath,{signal,credentials:'omit',redirect:'error',cache:'default'});
 if(!response.ok || !response.body)throw Error('The included game could not download. Retry, or choose a local game.');
 const length=response.headers.get('Content-Length');
 if(length!==null && Number(length)!==featuredGame.bytes){await response.body.cancel();throw Error('The included download has the wrong size. Retry the download.');}
 const reader=response.body.getReader(),bytes=new Uint8Array(featuredGame.bytes);let offset=0;
 try {
  while(true){signal.throwIfAborted();const {done,value}=await reader.read();signal.throwIfAborted();if(done)break;
   if(value.length>bytes.length-offset)throw Error('The included download is larger than expected. Retry the download.');
   bytes.set(value,offset);offset+=value.length;progress(offset);
  }
  if(offset!==bytes.length)throw Error('The included download ended early. Retry the download.');
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');
  signal.throwIfAborted();
  if(hash!==featuredGame.sha256)throw Error('The included download did not match the verified game. Retry the download.');
  return new File([bytes],'From Below.nes',{type:'application/octet-stream'});
 } finally {await reader.cancel().catch(()=>{});reader.releaseLock();}
}
