import {test} from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {runInNewContext} from 'node:vm';
import {stripTypeScriptTypes} from 'node:module';
import * as contracts from '../../../packages/contracts/src/index.ts';

test('preview renders a title frame and restores the exact unplayed machine state',async()=>{
 const memory=new WebAssembly.Memory({initial:5});let output:Uint8Array<ArrayBufferLike>=new Uint8Array(),machine=0,frames=0,restores=0;
 const pixels=new Uint8Array(256*240*4);
 const emit=(bytes:Uint8Array)=>{output=bytes;new Uint8Array(memory.buffer,4096,bytes.length).set(bytes);return 1;};
 const core={memory,
  local_state_hash:()=>emit(new Uint8Array([machine])),
  local_state_export:()=>emit(new Uint8Array([machine])),
  local_state_limit:()=>128,
  local_state_alloc:()=>1024,
  local_state_import:(ptr:number)=>{machine=new Uint8Array(memory.buffer)[ptr];restores++;return 1;},
  local_rewind_clear:()=>{},
  local_battery_limit:()=>128,
  local_battery_alloc:()=>1024,
  local_battery_import:(ptr:number)=>{machine=new Uint8Array(memory.buffer)[ptr];return 1;},
  local_frame:()=>{machine++;frames++;return 1;},
  local_output:(kind:number)=>{if(kind===5){pixels.fill(machine);emit(pixels);}return 4096;},
  local_output_len:()=>output.length,
 };
 const messages:contracts.WorkerResponse[]=[];
 const source=readFileSync(new URL('./worker.ts',import.meta.url),'utf8')
  .replace(/^import .*;$/gm,'')
  .replace('let core: Core | undefined;','let core: Core | undefined = injectedCore;');
 const context={...contracts,injectedCore:core,hex:(bytes:ArrayBuffer)=>Buffer.from(bytes).toString('hex'),
  WebAssembly,ArrayBuffer,Uint8Array,TextDecoder,TextEncoder,crypto,setTimeout,clearTimeout,
  postMessage:(message:contracts.WorkerResponse)=>messages.push(structuredClone(message)),onmessage:undefined};
 runInNewContext(stripTypeScriptTypes(source),context);
 const rpc=context.onmessage as unknown as (event:{data:unknown})=>Promise<void>;
 assert.equal(contracts.isWorkerRequest({type:'state-preview',requestId:7}),true);
 await rpc({data:{type:'state-preview',requestId:7}});
 const result=messages.at(-1);
 assert.equal(result?.type,'state-preview');
 if(result?.type==='state-preview'){
  assert.equal(result.pixels.byteLength,256*240*4);
  assert.equal(new Uint8Array(result.pixels)[0],60);
 }
 assert.deepEqual({machine,frames,restores},{machine:0,frames:60,restores:1});
 await rpc({data:{type:'state-hash',requestId:8}});
 assert.deepEqual(messages.at(-1),{type:'state-hash',requestId:8,info:{hash:'00',frame:0,fresh:true}});
 await rpc({data:{type:'battery-import',requestId:9,bytes:new Uint8Array([9]).buffer}});
 assert.equal(messages.at(-1)?.type,'battery-imported',JSON.stringify(messages.at(-1)));
 await rpc({data:{type:'state-preview',requestId:10}});
 const afterBattery=messages.at(-1);
 assert.equal(afterBattery?.type,'state-preview');
 if(afterBattery?.type==='state-preview')assert.equal(new Uint8Array(afterBattery.pixels)[0],69);
 await rpc({data:{type:'state-hash',requestId:11}});
 assert.deepEqual(messages.at(-1),{type:'state-hash',requestId:11,info:{hash:'09',frame:0,fresh:true}});
 // A full save-state import is a resumed session. Later battery imports must
 // never reopen a preview window, even if no frame has run in this worker.
 await rpc({data:{type:'state-import',requestId:12,bytes:new Uint8Array([4]).buffer}});
 assert.equal(messages.at(-1)?.type,'state-imported');
 await rpc({data:{type:'battery-import',requestId:13,bytes:new Uint8Array([5]).buffer}});
 assert.equal(messages.at(-1)?.type,'battery-imported');
 await rpc({data:{type:'state-preview',requestId:14}});
 assert.equal(messages.at(-1)?.type,'state-error');
 await rpc({data:{type:'state-hash',requestId:15}});
 assert.deepEqual(messages.at(-1),{type:'state-hash',requestId:15,info:{hash:'05',frame:0,fresh:false}});
});

const wasmPath=new URL('./generated/retro_coop_d02.wasm',import.meta.url);
const romPath=new URL('../../../spikes/d02/fixture.local.nes',import.meta.url);
test('prepared native core previews games with and without restored battery data',{
 skip:!existsSync(wasmPath)||!existsSync(romPath)?'Run sh scripts/foundation/prepare.sh first':false,
},async()=>{
 const wasm=readFileSync(wasmPath),rom=readFileSync(romPath);
 const module=await WebAssembly.compile(wasm),imports:WebAssembly.Imports={};
 for(const item of WebAssembly.Module.imports(module)){
  assert.equal(item.kind,'function');
  (imports[item.module]??={})[item.name]=()=>{throw Error('Unexpected emulator host call');};
 }
 for(const hasBattery of [false,true]){
 const core=(await WebAssembly.instantiate(module,imports)).exports as unknown as {
  memory:WebAssembly.Memory;local_alloc(size:number):number;local_initialize(ptr:number,size:number):number;
  local_battery_alloc(size:number):number;local_bind_core(ptr:number,size:number):number;
  local_has_battery():number;local_battery_export():number;local_battery_import(ptr:number,size:number):number;
  local_state_hash():number;local_state_export():number;local_state_alloc(size:number):number;
  local_state_import(ptr:number,size:number):number;local_frame(p1:number,p2:number):number;
  local_output(kind:number):number;local_output_len():number;
 };
 const copy=(kind:number)=>new Uint8Array(core.memory.buffer,core.local_output(kind),core.local_output_len()).slice();
 const check=(value:number)=>assert.equal(value,1,new TextDecoder().decode(copy(0)));
 const cartridge=Uint8Array.from(rom);if(hasBattery)cartridge[6]|=2;
 const ptr=core.local_alloc(cartridge.length);new Uint8Array(core.memory.buffer,ptr,cartridge.length).set(cartridge);check(core.local_initialize(ptr,cartridge.length));
 const digest=createHash('sha256').update(wasm).digest(),identity=core.local_battery_alloc(digest.length);
 new Uint8Array(core.memory.buffer,identity,digest.length).set(digest);check(core.local_bind_core(identity,digest.length));
 assert.equal(!!core.local_has_battery(),hasBattery);
 if(hasBattery){
  check(core.local_battery_export());const battery=copy(0),location=core.local_battery_alloc(battery.length);
  new Uint8Array(core.memory.buffer,location,battery.length).set(battery);
  check(core.local_battery_import(location,battery.length));
 }
 check(core.local_state_hash());const before=Buffer.from(copy(0)).toString('hex');
 check(core.local_state_export());const snapshot=copy(0);
 for(let frame=0;frame<60;frame++)check(core.local_frame(0,0));
 const pixels=copy(5),restore=core.local_state_alloc(snapshot.length);
 new Uint8Array(core.memory.buffer,restore,snapshot.length).set(snapshot);check(core.local_state_import(restore,snapshot.length));
 check(core.local_state_hash());const after=Buffer.from(copy(0)).toString('hex');
 assert.equal(after,before);
 assert.equal(pixels.length,256*240*4);
 assert.ok(pixels.some(value=>value!==0),'The preview should contain visible pixels');
 }
});
