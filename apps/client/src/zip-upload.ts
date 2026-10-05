import {ZIP_ARCHIVE_LIMIT,ROM_FILE_LIMIT,gameFileTitle} from '../../../packages/contracts/src/game-file.ts';

const extractionErrors:Record<string,string>={
 archive_size_limit:'This ZIP must be under 2 MB. Choose a smaller archive.',
 archive_no_game:'This ZIP contains no NES game. Choose another file.',
 invalid_archive:'This ZIP is damaged or unsupported. Choose another archive.',
 unsafe_archive:'This ZIP contains unsupported file paths or file types. Choose another archive.',
 encrypted_archive:'This ZIP is encrypted. Choose an archive without a password.',
 unsupported_archive:'This ZIP uses unsupported compression. Choose a stored or deflated ZIP.',
 invalid_cartridge:'The selected game in this ZIP is not a complete NES file. Choose another archive.',
 upload_size_limit:'The NES game in this ZIP exceeds the game file limit.',
 upload_capacity:'The game server is full. Retry later.',
 rate_limited:'Too many uploads. Wait, then retry.',
 session_expired:'Your game service connection expired. Reconnect and retry.',
 upload_expired:'ZIP preparation timed out. Retry when ready.',
 length_mismatch:'The ZIP upload was incomplete. Retry.',
};
const invalidResponse=()=>Error('The game server sent an invalid ZIP response. Retry.');

/** The server extracts; the browser verifies the resulting File before ordinary NES preparation. */
export async function extractZipFile(endpoint:string,token:string,file:File,signal:AbortSignal):Promise<File> {
 signal.throwIfAborted();
 if(file.size>=ZIP_ARCHIVE_LIMIT)throw Error(extractionErrors.archive_size_limit);
 const url=new URL(endpoint,globalThis.location?.href);url.pathname=url.pathname.replace(/\/$/,'')+'/rom-extractions';url.search='';url.hash='';
 const requestSignal=AbortSignal.any([signal,AbortSignal.timeout(300_000)]);
 let response:Response;
 try{response=await fetch(url,{method:'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/zip'},body:file,signal:requestSignal});}
 catch(error){if(signal.aborted)throw error;if(requestSignal.aborted)throw Error(extractionErrors.upload_expired);throw Error('ZIP upload connection failed. Retry.');}
 if(response.status!==200){
  let code:string|undefined;try{const body=await response.json();if(body&&typeof body==='object'&&typeof body.error==='string')code=body.error;}catch{}
  signal.throwIfAborted();throw Error(extractionErrors[code??'']??'ZIP preparation failed. Retry or choose another file.');
 }
 let name:string;try{name=decodeURIComponent(response.headers.get('X-NES-Name')??'');}catch{await response.body?.cancel();throw invalidResponse();}
 const length=response.headers.get('Content-Length')??'',bytes=Number(length),sha=response.headers.get('X-NES-SHA256');
 if(!/^[0-9]+$/.test(length)||!Number.isSafeInteger(bytes)||bytes<16||bytes>ROM_FILE_LIMIT||!sha||!/^[a-f0-9]{64}$/.test(sha)||name!==gameFileTitle(name)+'.nes'||name.length>84||/[\/\\\p{C}]/u.test(name)||response.headers.get('Content-Type')!=='application/octet-stream'||!response.body){await response.body?.cancel();throw invalidResponse();}
 const reader=response.body.getReader(),data=new Uint8Array(bytes);let received=0;
 try{
  for(;;){signal.throwIfAborted();const {done,value}=await reader.read();if(done)break;if(received+value.byteLength>bytes)throw invalidResponse();data.set(value,received);received+=value.byteLength;}
 }catch(error){await reader.cancel().catch(()=>{});if(signal.aborted)throw error;if(requestSignal.aborted)throw Error(extractionErrors.upload_expired);throw invalidResponse();}
 finally{reader.releaseLock();}
 if(received!==bytes)throw invalidResponse();signal.throwIfAborted();
 const actual=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data)),byte=>byte.toString(16).padStart(2,'0')).join('');
 signal.throwIfAborted();if(actual!==sha)throw Error('The extracted game did not match the server receipt. Retry.');
 return new File([data],name,{type:'application/octet-stream'});
}
