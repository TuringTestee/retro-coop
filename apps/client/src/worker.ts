import { hex } from './cartridge.ts';
import { isWorkerRequest, type WorkerResponse } from '../../../packages/contracts/src/index.ts';
// This adapter uses only PR40's local-player ABI. Peer checkpoint exports are not called.
type Core = WebAssembly.Exports & {
 memory: WebAssembly.Memory; local_alloc(size:number):number; local_initialize(ptr:number,size:number):number;
 local_frame(p1:number,p2:number):number; local_fps():number; local_output(kind:number):number; local_output_len():number;
};
let core: Core | undefined;
const send = (message: WorkerResponse, transfer: Transferable[] = []) => postMessage(message, { transfer });
function copy(kind: number) { const ptr = core!.local_output(kind); return new Uint8Array(core!.memory.buffer, ptr, core!.local_output_len()).slice().buffer; }
function check(ok: number) { if (!ok) throw Error(new TextDecoder().decode(copy(0))); }
let loading = false;
onmessage = async ({data}: MessageEvent<unknown>) => {
 try {
  if (!isWorkerRequest(data)) throw Error('Invalid worker request');
  if (loading) throw Error('Emulator is loading');
  if (data.type === 'load') {
   loading = true;
   try {
    const response = await fetch('/generated/retro_coop_d02.wasm');
    if (!response.ok) throw Error('The emulator is unavailable. Reload the page to retry.');
    const bytes = await response.arrayBuffer();
    const coreSha256 = hex(await crypto.subtle.digest('SHA-256',bytes));
    const module = await WebAssembly.compile(bytes);
    const imports: WebAssembly.Imports = {};
    for (const item of WebAssembly.Module.imports(module)) {
     if (item.kind !== 'function') throw Error('Unsupported emulator import');
     (imports[item.module] ??= {})[item.name] = () => { throw Error('Unexpected emulator host access'); };
    }
    core = (await WebAssembly.instantiate(module, imports)).exports as Core;
    const ptr = core.local_alloc(data.rom.byteLength);
    new Uint8Array(core.memory.buffer, ptr, data.rom.byteLength).set(new Uint8Array(data.rom));
    check(core.local_initialize(ptr, data.rom.byteLength));
    send({type:'ready',fps:core.local_fps(),coreSha256});
   } finally { loading = false; }
  } else if (!core) throw Error('Load the emulator first');
  else if (data.type === 'pause') send({type:'paused'});
  else {
   check(core.local_frame(data.p1,data.p2)); const pixels = copy(5), audio = copy(2);
   send({type:'frame',pixels,audio},[pixels,audio]);
  }
 } catch (error) { send({type:'error',message:error instanceof Error ? error.message : 'Emulator failed'}); }
};
