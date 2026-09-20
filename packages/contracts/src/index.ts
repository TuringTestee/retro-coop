// ROM, local battery files and PCM buffers cross only the browser's dedicated worker boundary.
export type WorkerRequest =
  | { type: 'load'; rom: ArrayBuffer }
  | { type: 'frame'; p1: number; p2: number }
  | { type: 'pause' }
  | { type: 'battery-export'; requestId: number }
  | { type: 'battery-import'; requestId: number; bytes: ArrayBuffer };
export type WorkerResponse =
  | { type: 'ready'; fps: number; coreSha256: string }
  | { type: 'frame'; pixels: ArrayBuffer; audio: ArrayBuffer }
  | { type: 'paused' }
  | { type: 'battery-exported'; requestId: number; bytes: ArrayBuffer }
  | { type: 'battery-imported'; requestId: number }
  | { type: 'battery-error'; requestId: number; message: string }
  | { type: 'error'; message: string };
export type HealthResponse = { status: 'ok'; service: 'retro-coop-coordinator'; protocol: 1 };
export const health: HealthResponse = { status: 'ok', service: 'retro-coop-coordinator', protocol: 1 };
export const batteryFileLimit = 2 * 1024 * 1024;
export function isBatteryOperation(value: unknown): value is { type: 'battery-export' | 'battery-import'; requestId: number } {
  return !!value && typeof value === 'object' && 'type' in value && (value.type === 'battery-export' || value.type === 'battery-import') && 'requestId' in value && typeof value.requestId === 'number' && Number.isSafeInteger(value.requestId) && value.requestId >= 0;
}
export function isWorkerRequest(value: unknown): value is WorkerRequest {
  if (!value || typeof value !== 'object' || !('type' in value)) return false;
  if (value.type === 'load') return 'rom' in value && value.rom instanceof ArrayBuffer && value.rom.byteLength > 0;
  if (value.type === 'battery-export' || value.type === 'battery-import') {
    if (!isBatteryOperation(value)) return false;
    return value.type === 'battery-export' || ('bytes' in value && value.bytes instanceof ArrayBuffer && value.bytes.byteLength > 0 && value.bytes.byteLength <= batteryFileLimit);
  }
  if (value.type === 'pause') return true;
  return value.type === 'frame' && 'p1' in value && 'p2' in value && [value.p1, value.p2].every(v => typeof v === 'number' && Number.isInteger(v) && v >= 0 && v <= 255);
}
