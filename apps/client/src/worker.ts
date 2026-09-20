import { hex } from './cartridge.ts';
import { isLocalFileOperation, localFileKind, isWorkerRequest, type WorkerResponse } from '../../../packages/contracts/src/index.ts';
// This adapter uses only the local-player ABI. Peer checkpoint exports are not called.
type Core = WebAssembly.Exports & {
 memory: WebAssembly.Memory; local_alloc(size:number):number; local_initialize(ptr:number,size:number):number;
 local_has_battery():number; local_battery_info():number; local_battery_limit():number; local_battery_alloc(size:number):number; local_bind_core(ptr:number,size:number):number;
 local_state_hash():number; local_state_info():number; local_state_validate(ptr:number,size:number):number; local_state_limit():number; local_state_alloc(size:number):number; local_state_export():number; local_state_import(ptr:number,size:number):number;
 local_battery_export():number; local_battery_import(ptr:number,size:number):number;
 local_frame(p1:number,p2:number):number; local_fps():number; local_output(kind:number):number; local_output_len():number;
};
let core: Core | undefined;
const send = (message: WorkerResponse, transfer: Transferable[] = []) => postMessage(message, { transfer });
function copy(kind: number) { const ptr = core!.local_output(kind); return new Uint8Array(core!.memory.buffer, ptr, core!.local_output_len()).slice().buffer; }
function check(ok: number) { if (!ok) throw Error(new TextDecoder().decode(copy(0))); }
let loading = false, frame=0, fresh=true;
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
    const coreHash = await crypto.subtle.digest('SHA-256',bytes);
    const coreSha256 = hex(coreHash);
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
    const identityPtr = core.local_battery_alloc(coreHash.byteLength);
    if (!identityPtr) throw Error('Cannot allocate core identity');
    new Uint8Array(core.memory.buffer, identityPtr, coreHash.byteLength).set(new Uint8Array(coreHash));
    check(core.local_bind_core(identityPtr,coreHash.byteLength));
    frame=0;fresh=true;send({type:'ready',fps:core.local_fps(),coreSha256,battery:!!core.local_has_battery()});
   } finally { loading = false; }
  } else if (!core) throw Error('Load the emulator first');
  else if (isLocalFileOperation(data)) {
   const kind=localFileKind(data.type);
   const api=kind==='battery'
    ? {limit:core.local_battery_limit,alloc:core.local_battery_alloc,export:core.local_battery_export,import:core.local_battery_import}
    : {limit:core.local_state_limit,alloc:core.local_state_alloc,export:core.local_state_export,import:core.local_state_import};
   if(data.type==='state-hash') {check(core.local_state_hash());send({type:'state-hash',requestId:data.requestId,info:{hash:hex(copy(0)),frame,fresh}});}
   else if(data.type==='state-info' || data.type==='battery-info') {
    check(kind==='state' ? core.local_state_info() : core.local_battery_info());send({type:`${kind}-info`,requestId:data.requestId,info:JSON.parse(new TextDecoder().decode(copy(0)))});
   } else if (data.type === 'battery-export' || data.type === 'state-export') {
    check(api.export()); const bytes=copy(0);
    send({type:`${kind}-exported`,requestId:data.requestId,bytes},[bytes]);
   } else {
    if (data.bytes.byteLength > api.limit()) throw Error('Local file exceeds the import limit');
    const ptr=api.alloc(data.bytes.byteLength);
    if (!ptr) throw Error('Local file exceeds the import limit');
    new Uint8Array(core.memory.buffer,ptr,data.bytes.byteLength).set(new Uint8Array(data.bytes));
    if(data.type==='state-validate') {check(core.local_state_validate(ptr,data.bytes.byteLength));send({type:'state-validated',requestId:data.requestId});}
    else {check(api.import(ptr,data.bytes.byteLength));fresh=false;send({type:`${kind}-imported`,requestId:data.requestId});}
   }
  }
  else if (data.type === 'pause') send({type:'paused'});
  else {
   check(core.local_frame(data.p1,data.p2));frame++;fresh=false; const pixels = copy(5), audio = copy(2);
   send({type:'frame',pixels,audio,...(data.epoch!==undefined?{epoch:data.epoch,frame:data.frame}:{})},[pixels,audio]);
  }
 } catch (error) {
  const message=error instanceof Error ? error.message : 'Emulator failed';
  send(isLocalFileOperation(data) ? {type:`${localFileKind(data.type)}-error`,requestId:data.requestId,message} : {type:'error',message});
 }
};
