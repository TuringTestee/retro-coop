export type UploadReceipt = {bytes:number;sha256:string};

const uploadErrors:Record<string,string> = {
 upload_capacity:'The room server is full. Retry upload later.',upload_size_limit:'This NES file exceeds the room server limit.',
 rate_limited:'Too many uploads. Wait, then retry upload.',upload_expired:'Upload timed out. Retry upload to create a fresh room.',
 room_changed:'The pending room expired. Retry upload to create a fresh room.',session_expired:'Your room session expired. Retry upload to reconnect.',
 host_disconnected:'The room connection was lost. Retry upload after reconnecting.',
 length_mismatch:'The upload was incomplete. Retry upload.',hash_mismatch:'The uploaded file did not match the selected game. Retry upload.',
 invalid_cartridge:'The server rejected this NES file. Choose another file.',cartridge_mismatch:'The uploaded NES header did not match. Retry upload.',
 upload_unavailable:'The upload service is unavailable. Retry upload.',
};

export function uploadRoomFile(endpoint:string,roomId:string,intent:string,token:string,file:File,onProgress:(sent:number,total:number)=>void,signal:AbortSignal):Promise<UploadReceipt> {
 return new Promise((resolve,reject)=>{
  const xhr=new XMLHttpRequest();
  const fail=(message:string)=>reject(Error(message));
  if(signal.aborted){fail('Upload cancelled.');return;}
  const abort=()=>xhr.abort();signal.addEventListener('abort',abort,{once:true});
  const finish=()=>signal.removeEventListener('abort',abort);
  xhr.open('PUT',new URL(`rooms/${encodeURIComponent(roomId)}/rom`,endpoint.endsWith('/')?endpoint:`${endpoint}/`).href);
  xhr.setRequestHeader('Authorization',`Bearer ${token}`);
  xhr.setRequestHeader('X-Room-Intent',intent);
  xhr.setRequestHeader('Content-Type','application/octet-stream');
  xhr.timeout=300_000;
  xhr.upload.onprogress=event=>onProgress(event.loaded,file.size);
  xhr.onabort=()=>{finish();fail('Upload cancelled. Retry upload when ready.');};
  xhr.onerror=()=>{finish();fail('Upload connection failed. Retry upload.');};
  xhr.ontimeout=()=>{finish();fail('Upload timed out. Retry upload to create a fresh room.');};
  xhr.onload=()=>{
   finish();let body:unknown;
   try{body=JSON.parse(xhr.responseText);}catch{fail('The room server sent an invalid upload response. Retry upload.');return;}
   if(xhr.status!==201){const code=typeof body==='object'&&body!==null&&'error' in body?String(body.error):'';fail(uploadErrors[code]??'Upload failed. Retry upload.');return;}
   if(typeof body!=='object'||body===null||!('bytes' in body)||!('sha256' in body)||body.bytes!==file.size||typeof body.sha256!=='string'||! /^[a-f0-9]{64}$/.test(body.sha256)){
    fail('The room server sent an invalid upload receipt. Retry upload.');return;
   }
   resolve(body as UploadReceipt);
  };
  xhr.send(file);
 });
}
