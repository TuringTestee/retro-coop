import {token,integer} from './protocol-validation.ts';
// ROM, local save files and PCM buffers cross only the browser's dedicated worker boundary.
const localFileKinds = ['battery','state'] as const;
export type LocalFileKind = typeof localFileKinds[number];
export type StateHash = {hash:string;frame:number;fresh:boolean};
export type LocalFileInfo = {identity:string;limit:number};
export type RewindInfo = {availableSeconds:number;spanSeconds:number;maxSeconds:number;retainedBytes:number;peakBytes:number;budgetBytes:number;frame:number;cycles:number;clockRate:number;checkpoints:number;inputs:number;issue?:string};
export type LocalFileRequest =
  | {type:'state-hash';requestId:number}
  | {type:'state-history';requestId:number}
  | {type:'state-rewind';requestId:number;seconds:number}
  | {type:'state-validate';requestId:number;bytes:ArrayBuffer}
  | {[Kind in LocalFileKind]:
  | {type:`${Kind}-info`;requestId:number}
  | { type: `${Kind}-export`; requestId: number }
  | { type: `${Kind}-import`; requestId: number; bytes: ArrayBuffer }
}[LocalFileKind];
export type WorkerRequest =
  | { type: 'load'; rom: ArrayBuffer }
  | { type: 'frame'; p1: number; p2: number; epoch?:string; frame?:number; rewind?:RewindInfo }
  | { type: 'pause' }
  | LocalFileRequest;
export type WorkerResponse =
  | { type: 'ready'; fps: number; coreSha256: string; battery:boolean }
  | { type: 'frame'; pixels: ArrayBuffer; audio: ArrayBuffer; epoch?:string; frame?:number; rewind?:RewindInfo }
  | { type: 'paused' }
  | {type:`${LocalFileKind}-info`;requestId:number;info:LocalFileInfo}
  | {type:'state-hash';requestId:number;info:StateHash}
  | {type:'state-history';requestId:number;info:RewindInfo}
  | {type:'state-rewound';requestId:number;pixels:ArrayBuffer;info:RewindInfo}
  | {type:'state-validated';requestId:number}
  | { type: `${LocalFileKind}-exported`; requestId: number; bytes: ArrayBuffer }
  | { type: `${LocalFileKind}-imported`; requestId: number }
  | { type: `${LocalFileKind}-error`; requestId: number; message: string }
  | { type: 'error'; message: string };
export type HealthResponse = { status: 'ok'; service: 'retro-coop-coordinator'; protocol: 1 };
export const health: HealthResponse = { status: 'ok', service: 'retro-coop-coordinator', protocol: 1 };
export function isLocalFileOperation(value: unknown): value is {type:LocalFileRequest['type'];requestId:number} {
  return !!value && typeof value === 'object' && 'type' in value && ((value.type==='state-hash' || value.type==='state-info' || value.type==='battery-info') || value.type==='state-validate' || value.type==='state-history' || value.type==='state-rewind' || localFileKinds.some(kind=>value.type===`${kind}-export` || value.type===`${kind}-import`)) && 'requestId' in value && typeof value.requestId === 'number' && Number.isSafeInteger(value.requestId) && value.requestId >= 0;
}
export function localFileKind(type: LocalFileRequest['type']):LocalFileKind { return type.split('-')[0] as LocalFileKind; }
export function isWorkerRequest(value: unknown): value is WorkerRequest {
  if (!value || typeof value !== 'object' || !('type' in value)) return false;
  if (value.type === 'load') return 'rom' in value && value.rom instanceof ArrayBuffer && value.rom.byteLength > 0;
  if (isLocalFileOperation(value)) {
    if(value.type==='state-rewind')return 'seconds' in value && typeof value.seconds==='number' && Number.isFinite(value.seconds) && value.seconds>0;
    if(value.type==='state-history')return true;
    return ((value.type==='state-hash' || value.type==='state-info' || value.type==='battery-info') || value.type.endsWith('-export')) || ('bytes' in value && value.bytes instanceof ArrayBuffer && value.bytes.byteLength > 0);
  }
  if (value.type === 'pause') return true;
  const tagged=!('epoch' in value) && !('frame' in value) || 'epoch' in value && token(value.epoch) && 'frame' in value && integer(value.frame,0,Number.MAX_SAFE_INTEGER);
  return tagged && value.type === 'frame' && 'p1' in value && 'p2' in value && [value.p1, value.p2].every(v => typeof v === 'number' && Number.isInteger(v) && v >= 0 && v <= 255);
}
