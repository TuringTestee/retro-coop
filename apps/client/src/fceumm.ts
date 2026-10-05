import wasmUrl from './generated/fceumm.wasm?url';
import bindingUrl from './generated/fceumm.mjs?url';
import adapterSource from './fceumm.ts?raw';
import instanceSource from './fceumm-instance.ts?raw';
import stateSource from './fceumm-state.ts?raw';
import workerSource from './worker.ts?raw';
import {inspectCartridge,hex} from './cartridge.ts';
import {FCE_STATE_LIMIT} from './fceumm-state.ts';
import type {Core} from './worker.ts';
const encoder=new TextEncoder();
const PROFILE='FCEUmm-7a542dab;emscripten-6.0.11;adapter-1;225-ines-ntsc;zero-ram;48000hz;low-audio;no-stereo-delay;standard-p1-p2';
const MAGIC=encoder.encode('RCFCEU01');
export function isFceCartridge(rom:ArrayBuffer){return inspectCartridge(new Uint8Array(rom)).mapper===225;}
function admit(rom:ArrayBuffer){
 const b=new Uint8Array(rom),cart=inspectCartridge(b);
 if(cart.mapper!==225||cart.format!=='iNES'||cart.region!=='NTSC'||b[6]&15||b[7]&15||b[8]>1||b[10]||b.subarray(11,16).some(v=>v)||!b[5]||b[4]>128||b[5]>128||rom.byteLength!==16+b[4]*16384+b[5]*8192)throw Error('This NES game cannot run here.');
}
const sha=async(bytes:Uint8Array)=>new Uint8Array(await crypto.subtle.digest('SHA-256',bytes as Uint8Array<ArrayBuffer>));
const joined=(...parts:Uint8Array[])=>{const out=new Uint8Array(parts.reduce((n,p)=>n+p.length,0));let offset=0;for(const p of parts){out.set(p,offset);offset+=p.length;}return out;};
class Instance{
 private worker=new Worker(new URL('./fceumm-instance.ts',import.meta.url),{type:'module'});
 private serial=0;
 private pending=new Map<number,{resolve:(value:unknown)=>void;reject:(error:Error)=>void;timer:ReturnType<typeof setTimeout>}>();
 private closed=false;
 constructor(){
  this.worker.onmessage=({data})=>{const pending=this.pending.get(data.id);if(!pending)return;clearTimeout(pending.timer);this.pending.delete(data.id);data.error?pending.reject(Error(data.error)):pending.resolve(data.result);};
  this.worker.onerror=()=>this.dispose('OSS emulator failed');
 }
 request<T>(type:string,data:Record<string,unknown>={}):Promise<T>{
  if(this.closed)return Promise.reject(Error('OSS operation cancelled'));
  return new Promise((resolve,reject)=>{const id=++this.serial;const timer=setTimeout(()=>this.dispose('OSS emulator exceeded its execution limit'),5000);this.pending.set(id,{resolve:value=>resolve(value as T),reject,timer});this.worker.postMessage({id,type,...data});});
 }
 dispose(message='OSS operation cancelled'){
  if(this.closed)return;this.closed=true;this.worker.terminate();for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(Error(message));}this.pending.clear();
 }
}
type Prepared={instance:Instance;bytes:Uint8Array};
export async function createFceCore(rom:ArrayBuffer):Promise<{core:Core;coreSha256:string}>{
 admit(rom);
 const fetched=await Promise.all([fetch(wasmUrl),fetch(bindingUrl)]);if(fetched.some(r=>!r.ok))throw Error('The emulator is unavailable. Reload the page to retry.');
 const [wasm,binding]=await Promise.all(fetched.map(r=>r.arrayBuffer()));
 const coreHash=await sha(joined(new Uint8Array(wasm),new Uint8Array(binding),encoder.encode(JSON.stringify([PROFILE,adapterSource,instanceSource,stateSource,workerSource]))));
 const identity=await sha(joined(MAGIC,coreHash,await sha(new Uint8Array(rom)),encoder.encode(PROFILE)));
 let instance=new Instance(),stage:Instance|undefined,prepared:Prepared|undefined,generation=0;
 let loaded:{fps:number;state:Uint8Array;memoryBytes:number};
 try{loaded=await instance.request('initialize',{rom,wasm});}catch(error){instance.dispose();throw error;}
 const memory=new WebAssembly.Memory({initial:64,maximum:64});const outputs=new Map<number,Uint8Array>();let outputLength=0;
 const emit=(bytes:Uint8Array,kind=0)=>{if(bytes.length>FCE_STATE_LIMIT)throw Error('OSS output exceeds limit');outputs.set(kind,bytes);return 1;};
 const envelope=async(raw:Uint8Array)=>joined(MAGIC,identity,await sha(raw),raw);
 const current=async()=>envelope(await instance.request<Uint8Array>('save'));
 function cancelStage(){generation++;stage?.dispose();stage=undefined;prepared?.instance.dispose();prepared=undefined;}
 async function validate(bytes:Uint8Array){
  cancelStage();const owner=generation;
  if(bytes.length<88||bytes.length>FCE_STATE_LIMIT||MAGIC.some((v,i)=>bytes[i]!==v)||identity.some((v,i)=>bytes[8+i]!==v))throw Error('State belongs to a different game, core, settings or schema');
  const raw=bytes.slice(72);const digest=await sha(raw);if(digest.some((v,i)=>bytes[40+i]!==v))throw Error('Damaged local state');
  if(owner!==generation)throw Error('OSS operation cancelled');
  const candidate=new Instance();stage=candidate;
  try{
   await candidate.request('initialize',{rom,wasm});await candidate.request('restore',{bytes:raw});
   if(owner!==generation)throw Error('OSS operation cancelled');
   prepared={instance:candidate,bytes:bytes.slice()};stage=undefined;
  }catch(error){candidate.dispose();if(stage===candidate)stage=undefined;throw error;}
  return 1;
 }
 const input=(ptr:number,size:number)=>new Uint8Array(memory.buffer,ptr,size).slice();
 async function restore(bytes:Uint8Array,replay:{p1:number;p2:number}[]=[]){
  if(!prepared||prepared.bytes.length!==bytes.length||prepared.bytes.some((v,i)=>v!==bytes[i]))await validate(bytes);
  if(!prepared)throw Error('OSS operation cancelled');
  const candidate=prepared;let last:{pixels:Uint8Array;audio:Float32Array}|undefined;
  // Rewind replay also finishes in the candidate, before replacing live progress.
  for(const entry of replay)last=await candidate.instance.request('frame',entry);
  if(prepared!==candidate)throw Error('OSS operation cancelled');
  const prior=instance;instance=candidate.instance;prepared=undefined;prior.dispose();outputs.delete(2);outputs.delete(5);
  if(last){emit(last.pixels,5);emit(new Uint8Array(last.audio.buffer),2);}return 1;
 }
 let ticks=0,peak=0;const inputs:{frame:number;p1:number;p2:number}[]=[];const history:{frame:number;bytes:Uint8Array;pixels:Uint8Array}[]=[];
 const clearHistory=()=>{inputs.length=0;history.length=0;};
 const info=()=>{
  const oldest=history[0]?.frame??ticks,span=(ticks-oldest)/loaded.fps;
  const retained=history.reduce((n,v)=>n+v.bytes.length+v.pixels.length,0)+inputs.length*24;peak=Math.max(peak,retained);
  return {availableSeconds:Math.min(10,span),spanSeconds:span,maxSeconds:10,retainedBytes:retained,peakBytes:peak,budgetBytes:32*1024*1024,frame:ticks,cycles:0,clockRate:1789773,checkpoints:history.length,inputs:inputs.length};
 };
 const facade={memory,
  local_alloc:(size:number)=>size>0&&size<=FCE_STATE_LIMIT?8:0,local_state_alloc:(size:number)=>size>0&&size<=FCE_STATE_LIMIT?8:0,local_battery_alloc:()=>0,
  local_initialize:()=>1,local_bind_core:()=>1,local_has_battery:()=>0,local_fps:()=>loaded.fps,
  local_state_limit:()=>FCE_STATE_LIMIT,local_battery_limit:()=>0,
  local_state_info:()=>emit(encoder.encode(JSON.stringify({identity:hex(identity.buffer),limit:FCE_STATE_LIMIT}))),
  local_battery_info:()=>emit(encoder.encode(JSON.stringify({hasBattery:false,identity:hex(identity.buffer),limit:0}))),
  local_state_export:async()=>emit(await current()),
  local_state_hash:async()=>{const bytes=await current();return emit(await sha(joined(identity,bytes.subarray(72))));},
  local_state_validate:async(ptr:number,size:number)=>validate(input(ptr,size)),
  local_state_import:async(ptr:number,size:number)=>{await restore(input(ptr,size));clearHistory();return 1;},
  local_battery_export:()=>{throw Error('This game has no battery save');},local_battery_import:()=>{throw Error('This game has no battery save');},
  local_frame:async(p1:number,p2:number)=>{const out=await instance.request<{pixels:Uint8Array;audio:Float32Array}>('frame',{p1,p2});emit(out.pixels,5);emit(new Uint8Array(out.audio.buffer),2);ticks++;return 1;},
  local_output:(kind:number)=>{const out=outputs.get(kind)??new Uint8Array();new Uint8Array(memory.buffer,FCE_STATE_LIMIT,out.length).set(out);outputLength=out.length;return FCE_STATE_LIMIT;},local_output_len:()=>outputLength,
  local_rewind_clear:clearHistory,
  local_rewind_info:()=>emit(encoder.encode(JSON.stringify(info()))),
  local_rewind_record:async(p1:number,p2:number)=>{
   inputs.push({frame:ticks,p1,p2});if(!history.length||ticks%60===0)history.push({frame:ticks,bytes:await current(),pixels:outputs.get(5)!.slice()});
   while(history.length>1&&ticks-history[0].frame>loaded.fps*10){history.shift();while(inputs[0]?.frame<history[0].frame)inputs.shift();}
   if(history.length>12||inputs.length>4096||info().retainedBytes>32*1024*1024)throw Error('Rewind memory budget exceeded');return 1;
  },
  local_rewind:async(seconds:number)=>{
   if(!Number.isFinite(seconds)||seconds<=0||seconds>10||seconds>info().availableSeconds)throw Error('Choose a rewind duration within available history');
   const target=ticks-Math.round(seconds*loaded.fps);const saved=history.findLast(v=>v.frame<=target);if(!saved)throw Error('No rewind history is available');
   const replay=inputs.filter(v=>v.frame>saved.frame&&v.frame<=target);if(replay.length!==target-saved.frame||replay.some((v,i)=>v.frame!==saved.frame+i+1))throw Error('Incomplete rewind history');
   await restore(saved.bytes,replay);if(!replay.length)emit(saved.pixels.slice(),5);
   ticks=target;history.splice(history.findIndex(v=>v.frame>target)<0?history.length:history.findIndex(v=>v.frame>target));inputs.splice(inputs.findIndex(v=>v.frame>target)<0?inputs.length:inputs.findIndex(v=>v.frame>target));
   return emit(outputs.get(5)??new Uint8Array(256*240*4));
  },
  setFrame:(value:number)=>{ticks=value;},cancelStage,dispose:()=>{cancelStage();instance.dispose();clearHistory();outputs.clear();}
 };
 return {core:facade as unknown as Core,coreSha256:hex(coreHash.buffer)};
}
