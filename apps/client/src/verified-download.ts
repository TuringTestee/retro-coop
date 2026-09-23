/** Read one source into bounded memory and verify its published exact bytes. */
export async function verifiedDownload(response:Response,expected:{bytes:number;sha256:string},signal:AbortSignal,progress:(bytes:number)=>void):Promise<Uint8Array> {
 signal.throwIfAborted();
 if(!response.ok || !response.body)throw Error('The game could not download. Retry.');
 const length=response.headers.get('Content-Length');
 if(length!==null && Number(length)!==expected.bytes){await response.body.cancel();throw Error('The game has the wrong download size. Retry.');}
 const reader=response.body.getReader(),bytes=new Uint8Array(expected.bytes);let offset=0;
 try {
  while(true){signal.throwIfAborted();const {done,value}=await reader.read();signal.throwIfAborted();if(done)break;if(value.length>bytes.length-offset)throw Error('The game downloaded more data than expected. Retry.');bytes.set(value,offset);offset+=value.length;progress(offset);}
  if(offset!==bytes.length)throw Error('The game download ended early. Retry.');
  if(await sha256(bytes)!==expected.sha256)throw Error('The game did not match the verified game. Retry.');
  signal.throwIfAborted();return bytes;
 }finally{await reader.cancel().catch(()=>{});reader.releaseLock();}
}
export async function sha256(bytes:Uint8Array):Promise<string> {return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes as Uint8Array<ArrayBuffer>)),x=>x.toString(16).padStart(2,'0')).join('');}
