// ROM and PCM buffers cross only the browser's dedicated worker boundary.
export type WorkerRequest =
  | { type: 'load'; rom: ArrayBuffer }
  | { type: 'frame'; p1: number; p2: number }
  | { type: 'pause' };
export type WorkerResponse =
  | { type: 'ready'; fps: number }
  | { type: 'frame'; pixels: ArrayBuffer; audio: ArrayBuffer }
  | { type: 'paused' }
  | { type: 'error'; message: string };
export type HealthResponse = { status: 'ok'; service: 'retro-coop-coordinator'; protocol: 1 };
export const health: HealthResponse = { status: 'ok', service: 'retro-coop-coordinator', protocol: 1 };
export function isWorkerRequest(value: unknown): value is WorkerRequest {
  if (!value || typeof value !== 'object' || !('type' in value)) return false;
  if (value.type === 'load') return 'rom' in value && value.rom instanceof ArrayBuffer && value.rom.byteLength > 0;
  if (value.type === 'pause') return true;
  return value.type === 'frame' && 'p1' in value && 'p2' in value && [value.p1, value.p2].every(v => typeof v === 'number' && Number.isInteger(v) && v >= 0 && v <= 255);
}
