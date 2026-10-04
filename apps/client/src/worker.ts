import coreUrl from './generated/retro_coop_d02.wasm?url';
import { hex } from './cartridge.ts';
import { isPeerCheckpointOperation, isLocalFileOperation, localFileKind, isWorkerRequest, type WorkerResponse, type RewindInfo } from '../../../packages/contracts/src/index.ts';
// Peer checkpoints reuse the validated canonical local-state codec through dedicated RPCs.
type Core = WebAssembly.Exports & {
 memory: WebAssembly.Memory; local_alloc(size:number):number; local_initialize(ptr:number,size:number):number;
 local_has_battery():number; local_battery_info():number; local_battery_limit():number; local_battery_alloc(size:number):number; local_bind_core(ptr:number,size:number):number;
 local_state_hash():number; local_state_info():number; local_state_validate(ptr:number,size:number):number; local_state_limit():number; local_state_alloc(size:number):number; local_state_export():number; local_state_import(ptr:number,size:number):number;
 local_rewind_record(p1:number,p2:number):number; local_rewind_info():number; local_rewind(seconds:number):number; local_rewind_clear():void;
 local_battery_export():number; local_battery_import(ptr:number,size:number):number;
 local_frame(p1:number,p2:number):number; local_fps():number; local_output(kind:number):number; local_output_len():number;
};
let core: Core | undefined;
const send = (message: WorkerResponse, transfer: Transferable[] = []) => postMessage(message, { transfer });
function copy(kind: number) { const ptr = core!.local_output(kind); return new Uint8Array(core!.memory.buffer, ptr, core!.local_output_len()).slice().buffer; }
function check(ok: number) { if (!ok) throw Error(new TextDecoder().decode(copy(0))); }
// Fresh means no gameplay timeline has begun. A cartridge battery restore can
// change the starting state while the timeline is still fresh.
let loading = false, frame=0, fresh=true;
let rewindIssue:string|undefined,sharedEpoch:string|undefined;
let checkpointGeneration=0, preparing=false;
let candidate: {operationId:string;generation:number;epoch:string;frame:number;bytes:ArrayBuffer;identity:string;hash:string;deadline:number}|undefined;
let candidateTimer:ReturnType<typeof setTimeout>|undefined;
function clearCandidate(){checkpointGeneration++;candidate=undefined;clearTimeout(candidateTimer);candidateTimer=undefined;}
function historyInfo():RewindInfo {check(core!.local_rewind_info());return {...JSON.parse(new TextDecoder().decode(copy(0))),issue:rewindIssue};}
onmessage = async ({data}: MessageEvent<unknown>) => {
 try {
  if (!isWorkerRequest(data)) throw Error('Invalid worker request');
  if(data.type==='peer-checkpoint-cancel') {
   if(candidate?.operationId===data.operationId)clearCandidate();
   send({type:'peer-checkpoint-cancelled',requestId:data.requestId,operationId:data.operationId});return;
  }
  if(preparing){if(data.type==='peer-checkpoint-prepare'||data.type==='load')clearCandidate();throw Error('Checkpoint preparation is pending');}
  if (loading) throw Error('Emulator is loading');
  if(data.type==='load'||data.type==='frame'||data.type==='state-rewind'||data.type==='state-import'||data.type==='battery-import')clearCandidate();
  if (data.type === 'load') {
   loading = true;
   try {
    const response = await fetch(coreUrl);
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
    // Mapper and board diagnostics belong in local probes, not the player-facing status.
    if (core.local_initialize(ptr, data.rom.byteLength) !== 1) {
     throw Error('This NES game cannot run here.');
    }
    const identityPtr = core.local_battery_alloc(coreHash.byteLength);
    if (!identityPtr) throw Error('Cannot allocate core identity');
    new Uint8Array(core.memory.buffer, identityPtr, coreHash.byteLength).set(new Uint8Array(coreHash));
    check(core.local_bind_core(identityPtr,coreHash.byteLength));
    frame=0;fresh=true;sharedEpoch=undefined;rewindIssue=undefined;send({type:'ready',fps:core.local_fps(),coreSha256,battery:!!core.local_has_battery()});
   } finally { loading = false; }
  } else if (!core) throw Error('Load the emulator first');
  else if (isPeerCheckpointOperation(data)) {
   if(data.type==='peer-checkpoint-bind'){
    if(frame!==data.frame)throw Error('Prepared frame changed');check(core.local_state_hash());const hash=hex(copy(0));if(hash!==data.hash)throw Error('Prepared state changed');
    clearCandidate();core.local_rewind_clear();sharedEpoch=data.epoch;rewindIssue=undefined;
    send({type:'peer-checkpoint-bound',requestId:data.requestId,epoch:data.epoch,frame,hash});
   } else if(data.type==='peer-checkpoint-export') {
    if(data.frame!==undefined&&frame!==data.frame || sharedEpoch!==data.epoch)throw Error('Checkpoint boundary is stale');
    check(core.local_state_export());const bytes=copy(0);
    check(core.local_state_hash());const hash=hex(copy(0));
    check(core.local_state_info());const {identity}=JSON.parse(new TextDecoder().decode(copy(0)));
    send({type:'peer-checkpoint-exported',requestId:data.requestId,epoch:data.epoch,frame,bytes,identity,hash},[bytes]);
   } else if(data.type==='peer-checkpoint-prepare') {
    clearCandidate();
    const generation=checkpointGeneration;
    candidate={operationId:data.operationId,generation,epoch:data.epoch,frame:data.frame,bytes:data.bytes,identity:data.identity,hash:data.hash,deadline:performance.now()+15_000};
    candidateTimer=setTimeout(()=>{if(candidate?.generation===generation)clearCandidate();},15_000);
    preparing=true;
    try {
     if(data.bytes.byteLength>core.local_state_limit())throw Error('Checkpoint exceeds codec limit');
     const ptr=core.local_state_alloc(data.bytes.byteLength);
     if(!ptr)throw Error('Checkpoint allocation failed');
     new Uint8Array(core.memory.buffer,ptr,data.bytes.byteLength).set(new Uint8Array(data.bytes));
     check(core.local_state_validate(ptr,data.bytes.byteLength));
     const bytes=new Uint8Array(data.bytes);
     if(hex(bytes.slice(8,40).buffer)!==data.identity)throw Error('Checkpoint identity mismatch');
     const canonical=new Uint8Array(32+bytes.byteLength-72);canonical.set(bytes.subarray(8,40));canonical.set(bytes.subarray(72),32);
     const hash=hex(await crypto.subtle.digest('SHA-256',canonical));
     if(hash!==data.hash)throw Error('Checkpoint state hash mismatch');
     if(candidate?.generation!==generation||performance.now()>=candidate.deadline)throw Error('Checkpoint preparation cancelled or expired');
     send({type:'peer-checkpoint-prepared',requestId:data.requestId,operationId:data.operationId,epoch:data.epoch,frame:data.frame,hash});
    } catch(error){if(candidate?.generation===generation)clearCandidate();throw error;}
    finally {preparing=false;}
   } else if(data.type==='peer-checkpoint-commit') {
    const prepared=candidate;
    if(!prepared||prepared.operationId!==data.operationId)throw Error('Checkpoint commit is stale');
    clearCandidate();
    if(performance.now()>=prepared.deadline)throw Error('Checkpoint preparation expired');
    // No asynchronous gap exists after the owner's final authorization check.
    const ptr=core.local_state_alloc(prepared.bytes.byteLength);
    if(!ptr)throw Error('Checkpoint allocation failed');
    new Uint8Array(core.memory.buffer,ptr,prepared.bytes.byteLength).set(new Uint8Array(prepared.bytes));
    // Import validates transactionally and consumes this allocation. A separate
    // validate call here would free the same bytes before import reads them.
    check(core.local_state_import(ptr,prepared.bytes.byteLength));
    core.local_rewind_clear();rewindIssue=undefined;frame=prepared.frame;sharedEpoch=prepared.epoch;fresh=false;
    send({type:'peer-checkpoint-imported',requestId:data.requestId,operationId:data.operationId,epoch:prepared.epoch,frame,hash:prepared.hash});
   }
  }
  else if (isLocalFileOperation(data)) {
   const kind=localFileKind(data.type);
   const api=kind==='battery'
    ? {limit:core.local_battery_limit,alloc:core.local_battery_alloc,export:core.local_battery_export,import:core.local_battery_import}
    : {limit:core.local_state_limit,alloc:core.local_state_alloc,export:core.local_state_export,import:core.local_state_import};
   if(data.type==='state-hash') {check(core.local_state_hash());send({type:'state-hash',requestId:data.requestId,info:{hash:hex(copy(0)),frame,fresh}});}
   else if(data.type==='state-capture') {
    // Worker messages run between completed frames; bytes and metadata share this boundary.
    check(core.local_state_export());const bytes=copy(0);check(core.local_state_hash());const hash=hex(copy(0));
    check(core.local_state_info());const {identity}=JSON.parse(new TextDecoder().decode(copy(0)));
    send({type:'state-captured',requestId:data.requestId,frame,hash,identity,bytes},[bytes]);
   }
   else if(data.type==='state-preview') {
    if(frame!==0||!fresh||sharedEpoch)throw Error('A preview is only available before play starts');
    check(core.local_state_hash());const originalHash=hex(copy(0));
    check(core.local_state_export());const saved=copy(0);
    let pixels:ArrayBuffer|undefined;
    try {
     for(let index=0;index<60;index++)check(core.local_frame(0,0));
     pixels=copy(5);
    } finally {
     const ptr=core.local_state_alloc(saved.byteLength);
     if(!ptr)throw Error('Cannot restore the game after preview');
     new Uint8Array(core.memory.buffer,ptr,saved.byteLength).set(new Uint8Array(saved));
     check(core.local_state_import(ptr,saved.byteLength));
    }
    check(core.local_state_hash());if(hex(copy(0))!==originalHash)throw Error("The preview changed the game's starting state");
    if(!pixels||pixels.byteLength!==256*240*4)throw Error('The game preview has an invalid image');
    send({type:'state-preview',requestId:data.requestId,pixels},[pixels]);
   }
   else if(data.type==='state-history')send({type:'state-history',requestId:data.requestId,info:historyInfo()});
   else if(data.type==='state-rewind') {check(core.local_rewind(data.seconds));fresh=false;const pixels=copy(0);send({type:'state-rewound',requestId:data.requestId,pixels,info:historyInfo()},[pixels]);}
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
    else {check(api.import(ptr,data.bytes.byteLength));if(kind==='state')fresh=false;rewindIssue=undefined;send({type:`${kind}-imported`,requestId:data.requestId});}
   }
  }
  else if (data.type === 'pause') send({type:'paused'});
  else {
   check(core.local_frame(data.p1,data.p2));frame=data.frame===undefined?frame+1:data.frame+1;fresh=false;
   if(data.epoch!==undefined){if(sharedEpoch!==data.epoch)core.local_rewind_clear();sharedEpoch=data.epoch;rewindIssue=undefined;}
   else {sharedEpoch=undefined;if(!rewindIssue) {try{check(core.local_rewind_record(data.p1,data.p2));}catch(error){rewindIssue=error instanceof Error ? error.message : 'Rewind unavailable';core.local_rewind_clear();}}}
   const pixels = copy(5), audio = copy(2);
   send({type:'frame',pixels,audio,rewind:data.epoch===undefined?historyInfo():undefined,...(data.epoch!==undefined?{epoch:data.epoch,frame:data.frame}:{})},[pixels,audio]);
  }
 } catch (error) {
  const message=error instanceof Error ? error.message : 'Emulator failed';
  send(isPeerCheckpointOperation(data) ? {type:'peer-checkpoint-error',requestId:data.requestId,message} : isLocalFileOperation(data) ? {type:`${localFileKind(data.type)}-error`,requestId:data.requestId,message} : {type:'error',message});
 }
};
