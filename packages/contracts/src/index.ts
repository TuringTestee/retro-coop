import {token,integer,sha256} from './protocol-validation.ts';
import {CHECKPOINT_MAX_BYTES} from './checkpoint.ts';
// ROM, local save files and PCM buffers cross only the browser's dedicated worker boundary.
const localFileKinds = ['battery','state'] as const;
export type LocalFileKind = typeof localFileKinds[number];
export type StateHash = {hash:string;frame:number;fresh:boolean};
export type LocalFileInfo = {identity:string;limit:number};
export type RewindInfo = {availableSeconds:number;spanSeconds:number;maxSeconds:number;retainedBytes:number;peakBytes:number;budgetBytes:number;frame:number;cycles:number;clockRate:number;checkpoints:number;inputs:number;issue?:string};
export type LocalFileRequest =
  | {type:'state-hash';requestId:number}
  | {type:'state-preview';requestId:number}
  | {type:'state-capture';requestId:number}
  | {type:'state-history';requestId:number}
  | {type:'state-rewind';requestId:number;seconds:number}
  | {type:'state-validate'|'state-inspect';requestId:number;bytes:ArrayBuffer}
  | {[Kind in LocalFileKind]:
  | {type:`${Kind}-info`;requestId:number}
  | { type: `${Kind}-export`; requestId: number }
  | { type: `${Kind}-import`; requestId: number; bytes: ArrayBuffer }
}[LocalFileKind];
export type PeerCheckpointRequest =
 | {type:'peer-checkpoint-bind';requestId:number;epoch:string;frame:number;hash:string}
 | {type:'peer-checkpoint-export';requestId:number;epoch:string;frame?:number}
 | {type:'peer-checkpoint-prepare';requestId:number;operationId:string;epoch:string;frame:number;bytes:ArrayBuffer;identity:string;hash:string;transactionId?:string}
 | {type:'peer-checkpoint-rollback'|'peer-checkpoint-finish';requestId:number;operationId:string}
 | {type:'peer-checkpoint-commit'|'peer-checkpoint-cancel';requestId:number;operationId:string};
export function isPeerCheckpointOperation(value:unknown):value is PeerCheckpointRequest {
 return !!value && typeof value==='object' && 'type' in value && ['peer-checkpoint-bind','peer-checkpoint-export','peer-checkpoint-prepare','peer-checkpoint-commit','peer-checkpoint-cancel','peer-checkpoint-rollback','peer-checkpoint-finish'].includes(String(value.type)) && 'requestId' in value && integer(value.requestId,0,Number.MAX_SAFE_INTEGER);
}
export type WorkerRequest =
  | { type: 'load'; rom: ArrayBuffer }
  | { type: 'frame'; p1: number; p2: number; epoch?:string; frame?:number }
  | { type: 'pause' }
  | LocalFileRequest
  | PeerCheckpointRequest;
export type WorkerResponse =
 | {type:'peer-checkpoint-bound';requestId:number;epoch:string;frame:number;hash:string}
  | {type:'peer-checkpoint-exported';requestId:number;epoch:string;frame:number;bytes:ArrayBuffer;identity:string;hash:string}
  | {type:'peer-checkpoint-imported'|'peer-checkpoint-prepared';requestId:number;operationId:string;epoch:string;frame:number;hash:string}
  | {type:'peer-checkpoint-cancelled'|'peer-checkpoint-finished';requestId:number;operationId:string}
  | {type:'peer-checkpoint-rolled-back';requestId:number;operationId:string;epoch?:string;frame:number;hash:string}
  | {type:'peer-checkpoint-error';requestId:number;message:string}
  | { type: 'ready'; fps: number; coreSha256: string; battery:boolean }
  | { type: 'frame'; pixels: ArrayBuffer; audio: ArrayBuffer; epoch?:string; frame?:number; rewind?:RewindInfo }
  | { type: 'paused' }
  | {type:`${LocalFileKind}-info`;requestId:number;info:LocalFileInfo}
  | {type:'state-hash';requestId:number;info:StateHash}
  | {type:'state-captured';requestId:number;frame:number;hash:string;identity:string;bytes:ArrayBuffer}
  | {type:'state-preview';requestId:number;pixels:ArrayBuffer}
  | {type:'state-history';requestId:number;info:RewindInfo}
  | {type:'state-rewound';requestId:number;pixels:ArrayBuffer;info:RewindInfo}
  | {type:'state-validated';requestId:number}
  | {type:'state-inspected';requestId:number;identity:string;hash:string}
  | { type: `${LocalFileKind}-exported`; requestId: number; bytes: ArrayBuffer }
  | { type: `${LocalFileKind}-imported`; requestId: number }
  | { type: `${LocalFileKind}-error`; requestId: number; message: string; code?:'invalid_state' }
  | { type: 'error'; message: string };
export type HealthResponse = { status: 'ok'; service: 'retro-coop-coordinator'; protocol: 1 };
export const health: HealthResponse = { status: 'ok', service: 'retro-coop-coordinator', protocol: 1 };
export function isLocalFileOperation(value: unknown): value is {type:LocalFileRequest['type'];requestId:number} {
  return !!value && typeof value === 'object' && 'type' in value && ((value.type==='state-hash' || value.type==='state-capture' || value.type==='state-preview' || value.type==='state-info' || value.type==='battery-info') || value.type==='state-validate' || value.type==='state-inspect' || value.type==='state-history' || value.type==='state-rewind' || localFileKinds.some(kind=>value.type===`${kind}-export` || value.type===`${kind}-import`)) && 'requestId' in value && typeof value.requestId === 'number' && Number.isSafeInteger(value.requestId) && value.requestId >= 0;
}
export function localFileKind(type: LocalFileRequest['type']):LocalFileKind { return type.split('-')[0] as LocalFileKind; }
export function isWorkerRequest(value: unknown): value is WorkerRequest {
  if (!value || typeof value !== 'object' || !('type' in value)) return false;
  if (isPeerCheckpointOperation(value)) {
   if(value.type==='peer-checkpoint-commit'||value.type==='peer-checkpoint-cancel'||value.type==='peer-checkpoint-rollback'||value.type==='peer-checkpoint-finish')return token(value.operationId);
   if(value.type==='peer-checkpoint-bind')return token(value.epoch)&&integer(value.frame,0,Number.MAX_SAFE_INTEGER)&&sha256(value.hash);
   if(value.type==='peer-checkpoint-export')return token(value.epoch)&&(value.frame===undefined||integer(value.frame,0,Number.MAX_SAFE_INTEGER));
   return value.type==='peer-checkpoint-prepare' && token(value.operationId) && token(value.epoch) && integer(value.frame,0,Number.MAX_SAFE_INTEGER) && value.bytes instanceof ArrayBuffer && value.bytes.byteLength>=72 && value.bytes.byteLength<=CHECKPOINT_MAX_BYTES && sha256(value.identity) && sha256(value.hash) && (value.transactionId===undefined||token(value.transactionId));
  }
  if (value.type === 'load') return 'rom' in value && value.rom instanceof ArrayBuffer && value.rom.byteLength > 0;
  if (isLocalFileOperation(value)) {
    if(value.type==='state-rewind')return 'seconds' in value && typeof value.seconds==='number' && Number.isFinite(value.seconds) && value.seconds>0;
    if(value.type==='state-history')return true;
    return ((value.type==='state-hash' || value.type==='state-capture' || value.type==='state-preview' || value.type==='state-info' || value.type==='battery-info') || value.type.endsWith('-export')) || ('bytes' in value && value.bytes instanceof ArrayBuffer && value.bytes.byteLength > 0);
  }
  if (value.type === 'pause') return true;
  const tagged=!('epoch' in value) && !('frame' in value) || 'epoch' in value && token(value.epoch) && 'frame' in value && integer(value.frame,0,Number.MAX_SAFE_INTEGER);
  return tagged && value.type === 'frame' && 'p1' in value && 'p2' in value && [value.p1, value.p2].every(v => typeof v === 'number' && Number.isInteger(v) && v >= 0 && v <= 255);
}
