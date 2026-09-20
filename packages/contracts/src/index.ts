// ROM, local save files and PCM buffers cross only the browser's dedicated worker boundary.
const localFileKinds = ['battery','state'] as const;
export type LocalFileKind = typeof localFileKinds[number];
export type StateHash = {hash:string;frame:number;fresh:boolean};
export type StateInfo = {identity:string;limit:number};
export type LocalFileRequest =
  | {type:'state-info';requestId:number}
  | {type:'state-hash';requestId:number}
  | {type:'state-validate';requestId:number;bytes:ArrayBuffer}
  | {[Kind in LocalFileKind]:
  | { type: `${Kind}-export`; requestId: number }
  | { type: `${Kind}-import`; requestId: number; bytes: ArrayBuffer }
}[LocalFileKind];
export type WorkerRequest =
  | { type: 'load'; rom: ArrayBuffer }
  | { type: 'frame'; p1: number; p2: number; epoch?:string; frame?:number }
  | { type: 'pause' }
  | LocalFileRequest;
export type WorkerResponse =
  | { type: 'ready'; fps: number; coreSha256: string }
  | { type: 'frame'; pixels: ArrayBuffer; audio: ArrayBuffer; epoch?:string; frame?:number }
  | { type: 'paused' }
  | {type:'state-info';requestId:number;info:StateInfo}
  | {type:'state-hash';requestId:number;info:StateHash}
  | {type:'state-validated';requestId:number}
  | { type: `${LocalFileKind}-exported`; requestId: number; bytes: ArrayBuffer }
  | { type: `${LocalFileKind}-imported`; requestId: number }
  | { type: `${LocalFileKind}-error`; requestId: number; message: string }
  | { type: 'error'; message: string };
export type HealthResponse = { status: 'ok'; service: 'retro-coop-coordinator'; protocol: 1 };
export const health: HealthResponse = { status: 'ok', service: 'retro-coop-coordinator', protocol: 1 };
export function isLocalFileOperation(value: unknown): value is {type:LocalFileRequest['type'];requestId:number} {
  return !!value && typeof value === 'object' && 'type' in value && (value.type==='state-info' || value.type==='state-hash' || value.type==='state-validate' || localFileKinds.some(kind=>value.type===`${kind}-export` || value.type===`${kind}-import`)) && 'requestId' in value && typeof value.requestId === 'number' && Number.isSafeInteger(value.requestId) && value.requestId >= 0;
}
export function localFileKind(type: LocalFileRequest['type']):LocalFileKind { return type.split('-')[0] as LocalFileKind; }
export function isWorkerRequest(value: unknown): value is WorkerRequest {
  if (!value || typeof value !== 'object' || !('type' in value)) return false;
  if (value.type === 'load') return 'rom' in value && value.rom instanceof ArrayBuffer && value.rom.byteLength > 0;
  if (isLocalFileOperation(value)) {
    return (value.type==='state-info' || value.type==='state-hash' || value.type.endsWith('-export')) || ('bytes' in value && value.bytes instanceof ArrayBuffer && value.bytes.byteLength > 0);
  }
  if (value.type === 'pause') return true;
  const tagged=!('epoch' in value) && !('frame' in value) || 'epoch' in value && typeof value.epoch==='string' && value.epoch.length>=16 && value.epoch.length<=128 && 'frame' in value && typeof value.frame==='number' && Number.isSafeInteger(value.frame) && value.frame>=0;
  return tagged && value.type === 'frame' && 'p1' in value && 'p2' in value && [value.p1, value.p2].every(v => typeof v === 'number' && Number.isInteger(v) && v >= 0 && v <= 255);
}
