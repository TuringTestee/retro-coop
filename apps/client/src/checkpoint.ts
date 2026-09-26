import {CHECKPOINT_MAX_BYTES,CHECKPOINT_PAYLOAD_BYTES,CHECKPOINT_BUFFER_BYTES,CHECKPOINT_TIMEOUT_MS,isCheckpointMetadata,encodeCheckpointChunk,decodeCheckpointChunk,type CheckpointMetadata} from '../../../packages/contracts/src/checkpoint.ts';
export async function checkpointDigest(bytes:ArrayBuffer):Promise<string> {return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');}
/** One authorized transfer per receiver. Owners cancel on membership/epoch changes. */
export class CheckpointReceiver {
 private current?:{metadata:CheckpointMetadata;bytes:Uint8Array<ArrayBuffer>;offset:number;deadline:number};
 private now:()=>number;
 constructor(now:()=>number=()=>performance.now()){this.now=now;}
 begin(metadata:CheckpointMetadata,authorized:(metadata:CheckpointMetadata)=>boolean) {
  if(this.current)throw Error('Checkpoint transfer already pending');
  if(!isCheckpointMetadata(metadata)||!authorized(metadata))throw Error('Unauthorized checkpoint transfer');
  this.current={metadata:{...metadata},bytes:new Uint8Array(metadata.byteLength),offset:0,deadline:this.now()+CHECKPOINT_TIMEOUT_MS};
 }
 cancel(){this.current=undefined;}
 get retainedBytes(){return this.current?.bytes.byteLength??0;}
 expire(){if(this.current && this.now()>=this.current.deadline){this.cancel();return true;}return false;}
 async accept(buffer:ArrayBuffer,authorized:(metadata:CheckpointMetadata)=>boolean):Promise<{metadata:CheckpointMetadata;bytes:ArrayBuffer}|undefined> {
  const current=this.current;
  try {
   if(!current || this.expire() || !authorized(current.metadata))throw Error('Unsolicited or expired checkpoint');
   const chunk=decodeCheckpointChunk(buffer);
   if(chunk.transferId!==current.metadata.transferId || chunk.offset!==current.offset || current.offset+chunk.payload.byteLength>current.bytes.byteLength)throw Error('Stale, duplicate or gapped checkpoint chunk');
   current.bytes.set(chunk.payload,current.offset);current.offset+=chunk.payload.byteLength;
   if(current.offset!==current.bytes.byteLength)return;
   const digest=await checkpointDigest(current.bytes.buffer);
   if(this.current!==current || this.expire() || !authorized(current.metadata) || digest!==current.metadata.digest)throw Error('Checkpoint digest or authorization changed');
   this.cancel();return {metadata:current.metadata,bytes:current.bytes.buffer};
  }catch(error){if(this.current===current)this.cancel();throw error;}
 }
}
export type CheckpointChannel={readyState:string;bufferedAmount:number;send(data:ArrayBuffer):void};
/** One owner pools the room's at-most-four outgoing transfers. pump is called on actual channel drain. */
export class CheckpointSender {
 private pending=new Map<string,{metadata:CheckpointMetadata;bytes:Uint8Array<ArrayBuffer>;offset:number;deadline:number;channel:CheckpointChannel}>();
 private now:()=>number;
 constructor(now:()=>number=()=>performance.now()){this.now=now;}
 begin(metadata:CheckpointMetadata,bytes:ArrayBuffer,channel:CheckpointChannel){
  if(!isCheckpointMetadata(metadata)||bytes.byteLength!==metadata.byteLength||bytes.byteLength>CHECKPOINT_MAX_BYTES)throw Error('Invalid checkpoint export');
  if(this.pending.has(metadata.recipient)||this.pending.size>=4)throw Error('Checkpoint sender capacity exceeded');
  this.pending.set(metadata.recipient,{metadata:{...metadata},bytes:new Uint8Array(bytes.slice(0)),offset:0,deadline:this.now()+CHECKPOINT_TIMEOUT_MS,channel});
 }
 cancel(recipient?:string){if(recipient)this.pending.delete(recipient);else this.pending.clear();}
 get retainedBytes(){return [...this.pending.values()].reduce((sum,p)=>sum+p.bytes.byteLength,0);}
 pump(recipient:string,authorized:(metadata:CheckpointMetadata)=>boolean):'pending'|'complete' {
  const p=this.pending.get(recipient);if(!p)throw Error('No checkpoint transfer');
  try {
   if(this.now()>=p.deadline||!authorized(p.metadata)||p.channel.readyState!=='open')throw Error('Checkpoint transfer expired or disconnected');
   while(p.offset<p.bytes.byteLength){
    const chunk=encodeCheckpointChunk(p.metadata.transferId,p.offset,p.bytes.subarray(p.offset,p.offset+CHECKPOINT_PAYLOAD_BYTES));
    if(p.channel.bufferedAmount+chunk.byteLength>CHECKPOINT_BUFFER_BYTES)return 'pending';
    p.channel.send(chunk);p.offset+=Math.min(CHECKPOINT_PAYLOAD_BYTES,p.bytes.byteLength-p.offset);
   }
   this.cancel(recipient);return 'complete';
  }catch(error){this.cancel(recipient);throw error;}
 }
 expire(){for(const [recipient,p] of this.pending)if(this.now()>=p.deadline)this.cancel(recipient);}
}
