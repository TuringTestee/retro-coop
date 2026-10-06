import coreUrl from './generated/retro_coop_d02.wasm?url';
import {createFceCore,isFceCartridge} from './fceumm.ts';
import { hex } from './cartridge.ts';
import { isPeerCheckpointOperation, isLocalFileOperation, localFileKind, isWorkerRequest, type WorkerResponse, type RewindInfo } from '../../../packages/contracts/src/index.ts';
// Peer checkpoints reuse the validated canonical local-state codec through dedicated RPCs.
export type Core = {
 memory: WebAssembly.Memory; local_alloc(size:number):number; local_initialize(ptr:number,size:number):number;
 local_has_battery():number; local_battery_info():number; local_battery_limit():number; local_battery_alloc(size:number):number; local_bind_core(ptr:number,size:number):number;
 local_state_hash():number|Promise<number>; local_state_info():number; local_state_validate(ptr:number,size:number):number|Promise<number>; local_state_limit():number; local_state_alloc(size:number):number; local_state_export():number|Promise<number>; local_state_import(ptr:number,size:number):number|Promise<number>;
 local_rewind_record(p1:number,p2:number):number|Promise<number>; local_rewind_info():number; local_rewind(seconds:number):number|Promise<number>; local_rewind_clear():void;
 local_battery_export():number; local_battery_import(ptr:number,size:number):number;
 setFrame?(frame:number):void; cancelStage?():void; dispose?():void;
 local_frame(p1:number,p2:number):number|Promise<number>; local_fps():number; local_output(kind:number):number; local_output_len():number;
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
let candidate: {operationId:string;generation:number;epoch:string;frame:number;bytes:ArrayBuffer;identity:string;hash:string;deadline:number;transactionId?:string;initial?:boolean}|undefined;
let candidateTimer:ReturnType<typeof setTimeout>|undefined;
function clearCandidate(preserveStage=false){if(!preserveStage){core?.cancelStage?.();if(rollback&&!rollback.committed&&rollback.operationId===candidate?.transactionId)rollback=undefined;}checkpointGeneration++;candidate=undefined;clearTimeout(candidateTimer);candidateTimer=undefined;}
let rollback: {operationId:string;frame:number;epoch?:string;fresh:boolean;bytes:ArrayBuffer;hash:string;committed:boolean}|undefined;
async function snapshot(assertOwner:()=>void){check(await core!.local_state_export());assertOwner();const bytes=copy(0);check(await core!.local_state_hash());assertOwner();return {bytes,hash:hex(copy(0))};}
async function importState(bytes:ArrayBuffer){const ptr=core!.local_state_alloc(bytes.byteLength);if(!ptr)throw Error('Checkpoint allocation failed');new Uint8Array(core!.memory.buffer,ptr,bytes.byteLength).set(new Uint8Array(bytes));check(await core!.local_state_import(ptr,bytes.byteLength));}
async function inspectState(bytes:ArrayBuffer){
 // Establish a usable codec first: only its completed file rejection is permanent.
 check(await core!.local_state_info());
 if(bytes.byteLength<72||bytes.byteLength>core!.local_state_limit())throw Object.assign(Error('Checkpoint exceeds codec limit'),{code:'invalid_state'});
 const ptr=core!.local_state_alloc(bytes.byteLength);if(!ptr)throw Error('Checkpoint allocation failed');new Uint8Array(core!.memory.buffer,ptr,bytes.byteLength).set(new Uint8Array(bytes));
 const valid=await core!.local_state_validate(ptr,bytes.byteLength);
 if(!valid)throw Object.assign(Error(new TextDecoder().decode(copy(0))),{code:'invalid_state'});
 const state=new Uint8Array(bytes),identity=hex(state.slice(8,40).buffer);const canonical=new Uint8Array(32+state.byteLength-72);canonical.set(state.subarray(8,40));canonical.set(state.subarray(72),32);
 return {identity,hash:hex(await crypto.subtle.digest('SHA-256',canonical))};
}
async function historyInfo():Promise<RewindInfo> {check(await core!.local_rewind_info());return {...JSON.parse(new TextDecoder().decode(copy(0))),issue:rewindIssue};}
async function handle({data}: {data:unknown}) {
 try {
  if (!isWorkerRequest(data)) throw Error('Invalid worker request');
  if(data.type==='peer-checkpoint-rollback'){
   if(rollback&&rollback.operationId!==data.operationId)throw Error('Rollback ownership changed');
   if(candidate?.operationId===data.operationId)clearCandidate();
   if(rollback){if(rollback.committed)await importState(rollback.bytes);frame=rollback.frame;core!.setFrame?.(frame);sharedEpoch=rollback.epoch;fresh=rollback.fresh;core!.local_rewind_clear();rollback=undefined;}
   check(await core!.local_state_hash());send({type:'peer-checkpoint-rolled-back',requestId:data.requestId,operationId:data.operationId,epoch:sharedEpoch,frame,hash:hex(copy(0))});return;
  }
  if(data.type==='peer-checkpoint-finish'){
   if(!rollback||rollback.operationId!==data.operationId||!rollback.committed)throw Error('Commit ownership changed');rollback=undefined;send({type:'peer-checkpoint-finished',requestId:data.requestId,operationId:data.operationId});return;
  }
  if(data.type==='peer-checkpoint-cancel') {
   if(candidate?.operationId===data.operationId)clearCandidate();
   send({type:'peer-checkpoint-cancelled',requestId:data.requestId,operationId:data.operationId});return;
  }
  if(preparing){if(data.type==='peer-checkpoint-prepare'||data.type==='load')clearCandidate();throw Error('Checkpoint preparation is pending');}
  if (loading) throw Error('Emulator is loading');
  if(rollback&&(data.type==='frame'||data.type==='load'||data.type==='state-import'||data.type==='state-rewind'||data.type==='battery-import'||data.type==='state-capture'||data.type==='state-export'||data.type==='peer-checkpoint-bind'))throw Error('Shared load is awaiting its commit decision');
  if(data.type==='load'||data.type==='frame'||data.type==='state-rewind'||data.type==='state-import'||data.type==='battery-import')clearCandidate();
  if (data.type === 'load') {
   loading = true;rollback=undefined;
   try {
    if(isFceCartridge(data.rom)){
     const loaded=await createFceCore(data.rom);core?.dispose?.();core=loaded.core;
     frame=0;fresh=true;sharedEpoch=undefined;rewindIssue=undefined;
     send({type:'ready',fps:core.local_fps(),coreSha256:loaded.coreSha256,battery:false});return;
    }
    const previous=core;
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
    const loadedCore = (await WebAssembly.instantiate(module, imports)).exports as Core;
    const ptr = loadedCore.local_alloc(data.rom.byteLength);
    new Uint8Array(loadedCore.memory.buffer, ptr, data.rom.byteLength).set(new Uint8Array(data.rom));
    // Mapper and board diagnostics belong in local probes, not the player-facing status.
    if (loadedCore.local_initialize(ptr, data.rom.byteLength) !== 1) {
     throw Error('This NES game cannot run here.');
    }
    const identityPtr = loadedCore.local_battery_alloc(coreHash.byteLength);
    if (!identityPtr) throw Error('Cannot allocate core identity');
    new Uint8Array(loadedCore.memory.buffer, identityPtr, coreHash.byteLength).set(new Uint8Array(coreHash));
    check(await loadedCore.local_bind_core(identityPtr,coreHash.byteLength));
    core=loadedCore;previous?.dispose?.();frame=0;fresh=true;sharedEpoch=undefined;rewindIssue=undefined;send({type:'ready',fps:loadedCore.local_fps(),coreSha256,battery:!!loadedCore.local_has_battery()});
   } finally { loading = false; }
  } else if (!core) throw Error('Load the emulator first');
  else if (isPeerCheckpointOperation(data)) {
   if(data.type==='peer-checkpoint-bind'){
    if(frame!==data.frame)throw Error('Prepared frame changed');check(await core.local_state_hash());const hash=hex(copy(0));if(hash!==data.hash)throw Error('Prepared state changed');
    clearCandidate();core.local_rewind_clear();sharedEpoch=data.epoch;rewindIssue=undefined;
    send({type:'peer-checkpoint-bound',requestId:data.requestId,epoch:data.epoch,frame,hash});
   } else if(data.type==='peer-checkpoint-export') {
    if(data.frame!==undefined&&frame!==data.frame || sharedEpoch!==data.epoch)throw Error('Checkpoint boundary is stale');
    check(await core.local_state_export());const bytes=copy(0);
    check(await core.local_state_hash());const hash=hex(copy(0));
    check(await core.local_state_info());const {identity}=JSON.parse(new TextDecoder().decode(copy(0)));
    send({type:'peer-checkpoint-exported',requestId:data.requestId,epoch:data.epoch,frame,bytes,identity,hash},[bytes]);
   } else if(data.type==='peer-checkpoint-prepare') {
    if(rollback&&(rollback.operationId!==data.operationId||rollback.committed))throw Error('Another shared load is pending');
    if(data.transactionId!==undefined&&data.transactionId!==data.operationId)throw Error('Checkpoint transaction ownership mismatch');
    clearCandidate();const generation=checkpointGeneration;
    if(data.initial&&(!fresh||frame!==0||sharedEpoch||data.frame!==0))throw Error('Initial checkpoint requires a fresh cartridge candidate');
    const duration=data.transactionId?45_000:15_000;
    candidate={operationId:data.operationId,generation,epoch:data.epoch,frame:data.frame,bytes:data.bytes,identity:data.identity,hash:data.hash,transactionId:data.transactionId,initial:data.initial,deadline:performance.now()+duration};
    candidateTimer=setTimeout(()=>{if(candidate?.generation===generation)clearCandidate();},duration);
    const assertOwner=()=>{if(candidate?.generation!==generation||performance.now()>=candidate.deadline)throw Error('Checkpoint preparation cancelled or expired');};
    preparing=true;
    try {
     if(data.transactionId&&!rollback){
      const previous={operationId:data.operationId,frame,epoch:sharedEpoch,fresh,committed:false};
      const state=await snapshot(assertOwner);assertOwner();
      rollback={...previous,...state};
     }
     const info=await inspectState(data.bytes);assertOwner();
     if(info.identity!==data.identity)throw Error('Checkpoint identity mismatch');
     if(info.hash!==data.hash)throw Error('Checkpoint state hash mismatch');
     assertOwner();
     send({type:'peer-checkpoint-prepared',requestId:data.requestId,operationId:data.operationId,epoch:data.epoch,frame:data.frame,hash:data.hash});
    } catch(error){if(candidate?.generation===generation)clearCandidate();throw error;}
    finally {preparing=false;}
   } else if(data.type==='peer-checkpoint-commit') {
    const prepared=candidate;
    if(!prepared||prepared.operationId!==data.operationId)throw Error('Checkpoint commit is stale');
    if(performance.now()>=prepared.deadline){clearCandidate();throw Error('Checkpoint preparation expired');}
    if(prepared.transactionId&&rollback?.operationId!==prepared.operationId){clearCandidate();throw Error('Rollback state unavailable');}
    clearCandidate(true);
    // Dispatch queues commit/import and rollback; only preparation admits concurrent cancellation.
    const ptr=core.local_state_alloc(prepared.bytes.byteLength);
    if(!ptr)throw Error('Checkpoint allocation failed');
    new Uint8Array(core.memory.buffer,ptr,prepared.bytes.byteLength).set(new Uint8Array(prepared.bytes));
    // Import validates transactionally and consumes this allocation. A separate
    // validate call here would free the same bytes before import reads them.
    check(await core.local_state_import(ptr,prepared.bytes.byteLength));
    if(prepared.transactionId)rollback!.committed=true;
    check(await core.local_state_hash());const importedHash=hex(copy(0));if(importedHash!==prepared.hash)throw Error('Imported checkpoint hash mismatch');
    core.local_rewind_clear();rewindIssue=undefined;frame=prepared.frame;core.setFrame?.(frame);sharedEpoch=prepared.initial?undefined:prepared.epoch;fresh=!!prepared.initial;
    send({type:'peer-checkpoint-imported',requestId:data.requestId,operationId:data.operationId,epoch:prepared.epoch,frame,hash:importedHash});
   }
  }
  else if (isLocalFileOperation(data)) {
   const kind=localFileKind(data.type);
   const api=kind==='battery'
    ? {limit:core.local_battery_limit,alloc:core.local_battery_alloc,export:core.local_battery_export,import:core.local_battery_import}
    : {limit:core.local_state_limit,alloc:core.local_state_alloc,export:core.local_state_export,import:core.local_state_import};
   if(data.type==='state-hash') {check(await core.local_state_hash());send({type:'state-hash',requestId:data.requestId,info:{hash:hex(copy(0)),frame,fresh}});}
   else if(data.type==='state-capture') {
    // Worker messages run between completed frames; bytes and metadata share this boundary.
    check(await core.local_state_export());const bytes=copy(0);check(await core.local_state_hash());const hash=hex(copy(0));
    check(await core.local_state_info());const {identity}=JSON.parse(new TextDecoder().decode(copy(0)));
    send({type:'state-captured',requestId:data.requestId,frame,hash,identity,bytes},[bytes]);
   }
   else if(data.type==='state-inspect') {const info=await inspectState(data.bytes);send({type:'state-inspected',requestId:data.requestId,...info});}
   else if(data.type==='state-preview') {
    if(frame!==0||!fresh||sharedEpoch)throw Error('A preview is only available before play starts');
    check(await core.local_state_hash());const originalHash=hex(copy(0));
    check(await core.local_state_export());const saved=copy(0);
    let pixels:ArrayBuffer|undefined;
    try {
     for(let index=0;index<60;index++)check(await core.local_frame(0,0));
     pixels=copy(5);
    } finally {
     const ptr=core.local_state_alloc(saved.byteLength);
     if(!ptr)throw Error('Cannot restore the game after preview');
     new Uint8Array(core.memory.buffer,ptr,saved.byteLength).set(new Uint8Array(saved));
     check(await core.local_state_import(ptr,saved.byteLength));core.setFrame?.(frame);
    }
    check(await core.local_state_hash());if(hex(copy(0))!==originalHash)throw Error("The preview changed the game's starting state");
    if(!pixels||pixels.byteLength!==256*240*4)throw Error('The game preview has an invalid image');
    send({type:'state-preview',requestId:data.requestId,pixels},[pixels]);
   }
   else if(data.type==='state-history')send({type:'state-history',requestId:data.requestId,info:await historyInfo()});
   else if(data.type==='state-rewind') {check(await core.local_rewind(data.seconds));fresh=false;const pixels=copy(0);frame=(await historyInfo()).frame;send({type:'state-rewound',requestId:data.requestId,pixels,info:await historyInfo()},[pixels]);}
   else if(data.type==='state-info' || data.type==='battery-info') {
    check(kind==='state' ? core.local_state_info() : core.local_battery_info());send({type:`${kind}-info`,requestId:data.requestId,info:JSON.parse(new TextDecoder().decode(copy(0)))});
   } else if (data.type === 'battery-export' || data.type === 'state-export') {
    check(await api.export()); const bytes=copy(0);
    send({type:`${kind}-exported`,requestId:data.requestId,bytes},[bytes]);
   } else {
    if (data.bytes.byteLength > api.limit()) throw Error('Local file exceeds the import limit');
    const ptr=api.alloc(data.bytes.byteLength);
    if (!ptr) throw Error('Local file exceeds the import limit');
    new Uint8Array(core.memory.buffer,ptr,data.bytes.byteLength).set(new Uint8Array(data.bytes));
    if(data.type==='state-validate') {check(await core.local_state_validate(ptr,data.bytes.byteLength));send({type:'state-validated',requestId:data.requestId});}
    else {check(await api.import(ptr,data.bytes.byteLength));if(kind==='state')fresh=false;rewindIssue=undefined;send({type:`${kind}-imported`,requestId:data.requestId});}
   }
  }
  else if (data.type === 'pause') send({type:'paused'});
  else {
   check(await core.local_frame(data.p1,data.p2));frame=data.frame===undefined?frame+1:data.frame+1;core.setFrame?.(frame);fresh=false;
   if(data.epoch!==undefined){if(sharedEpoch!==data.epoch)core.local_rewind_clear();sharedEpoch=data.epoch;rewindIssue=undefined;}
   else {sharedEpoch=undefined;if(!rewindIssue) {try{check(await core.local_rewind_record(data.p1,data.p2));}catch(error){rewindIssue=error instanceof Error ? error.message : 'Rewind unavailable';core.local_rewind_clear();}}}
   const pixels = copy(5), audio = copy(2);
   send({type:'frame',pixels,audio,rewind:data.epoch===undefined?await historyInfo():undefined,...(data.epoch!==undefined?{epoch:data.epoch,frame:data.frame}:{})},[pixels,audio]);
  }
 } catch (error) {
  const message=error instanceof Error ? error.message : 'Emulator failed';
  const invalid=error instanceof Error&&'code' in error&&error.code==='invalid_state';
  send(isPeerCheckpointOperation(data) ? {type:'peer-checkpoint-error',requestId:data.requestId,message} : isLocalFileOperation(data) ? {type:`${localFileKind(data.type)}-error`,requestId:data.requestId,message,...(invalid?{code:'invalid_state' as const}:{})} : {type:'error',message});
 }
}
let processing:Promise<void>|undefined;
onmessage=({data}:MessageEvent<unknown>)=>{
 const dispatch=():Promise<void>=>{
  // Cancellation must reach an isolated candidate while its prepare awaits work.
  if(preparing)return handle({data});
  if(processing)return processing.then(dispatch,dispatch);
  const task=handle({data});processing=task;
  return task.finally(()=>{if(processing===task)processing=undefined;});
 };
 return dispatch();
};
