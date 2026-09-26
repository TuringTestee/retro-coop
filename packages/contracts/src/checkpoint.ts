import {object,keys,token,integer,sha256} from './protocol-validation.ts';
export const CHECKPOINT_MAX_BYTES=2*1024*1024;
export const CHECKPOINT_CHUNK_BYTES=12*1024;
export const CHECKPOINT_BUFFER_BYTES=256*1024;
export const CHECKPOINT_TIMEOUT_MS=15_000;
export type CheckpointMetadata={transferId:string;sender:string;recipient:string;epoch:string;frame:number;identity:string;hash:string;digest:string;byteLength:number};
export function isCheckpointMetadata(value:unknown):value is CheckpointMetadata {
 return object(value) && keys(value,['transferId','sender','recipient','epoch','frame','identity','hash','digest','byteLength']) &&
  ['transferId','sender','recipient','epoch'].every(k=>token(value[k])) && value.sender!==value.recipient &&
  integer(value.frame,0,Number.MAX_SAFE_INTEGER) && ['identity','hash','digest'].every(k=>sha256(value[k])) && integer(value.byteLength,72,CHECKPOINT_MAX_BYTES);
}
// Fixed header: version, token length, 64-byte padded transfer token, uint32 offset.
const HEADER=70;
export function encodeCheckpointChunk(transferId:string,offset:number,payload:Uint8Array):ArrayBuffer {
 if(!token(transferId) || !integer(offset,0,CHECKPOINT_MAX_BYTES-1) || !payload.byteLength || payload.byteLength>CHECKPOINT_CHUNK_BYTES-HEADER || offset+payload.byteLength>CHECKPOINT_MAX_BYTES)throw Error('Invalid checkpoint chunk');
 const bytes=new Uint8Array(HEADER+payload.byteLength);bytes[0]=1;bytes[1]=transferId.length;bytes.set(new TextEncoder().encode(transferId),2);new DataView(bytes.buffer).setUint32(66,offset);bytes.set(payload,HEADER);return bytes.buffer;
}
export function decodeCheckpointChunk(buffer:ArrayBuffer):{transferId:string;offset:number;payload:Uint8Array} {
 if(buffer.byteLength<=HEADER || buffer.byteLength>CHECKPOINT_CHUNK_BYTES)throw Error('Invalid checkpoint chunk size');
 const bytes=new Uint8Array(buffer),length=bytes[1];
 if(bytes[0]!==1 || length<22 || length>64 || bytes.subarray(2+length,66).some(v=>v!==0))throw Error('Invalid checkpoint chunk header');
 const transferId=new TextDecoder('utf-8',{fatal:true}).decode(bytes.subarray(2,2+length));
 const offset=new DataView(buffer).getUint32(66);if(!token(transferId)||offset+buffer.byteLength-HEADER>CHECKPOINT_MAX_BYTES)throw Error('Invalid checkpoint chunk');
 return {transferId,offset,payload:bytes.subarray(HEADER)};
}
export const CHECKPOINT_PAYLOAD_BYTES=CHECKPOINT_CHUNK_BYTES-HEADER;
/** Parse bounded channel metadata before allocating any checkpoint payload. */
export function parseCheckpointMetadata(raw:unknown):CheckpointMetadata|undefined {
 if(typeof raw==='string'){
  if(raw.length>1024)return;
  try {raw=JSON.parse(raw);}catch{return;}
 }
 return isCheckpointMetadata(raw)?{...raw}:undefined;
}
