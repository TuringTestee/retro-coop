// Each worker owns one cartridge and one bounded unmodified OSS machine.
import createCore from './generated/fceumm.mjs';
import {FceStateSchema,FCE_STATE_LIMIT} from './fceumm-state.ts';
type Module={HEAPU8:Uint8Array;HEAP16:Int16Array;HEAPU32:Uint32Array;HEAPF64:Float64Array;
 FS:{writeFile(path:string,bytes:Uint8Array):void};
 addFunction(callback:(...args:number[])=>number|void,signature:string):number;
 UTF8ToString(ptr:number):string;lengthBytesUTF8(value:string):number;stringToUTF8(value:string,ptr:number,size:number):void;
 _malloc(size:number):number;_free(ptr:number):void;
 _retro_set_environment(ptr:number):void;_retro_set_video_refresh(ptr:number):void;_retro_set_audio_sample(ptr:number):void;_retro_set_audio_sample_batch(ptr:number):void;
 _retro_set_input_poll(ptr:number):void;_retro_set_input_state(ptr:number):void;_retro_init():void;
 _retro_set_controller_port_device(port:number,device:number):void;_retro_load_game(ptr:number):number;
 _retro_run():void;_retro_serialize_size():number;_retro_serialize(ptr:number,size:number):number;_retro_unserialize(ptr:number,size:number):number;_retro_get_system_av_info(ptr:number):void;
};
let machine:Module|undefined,schema:FceStateSchema|undefined,statePtr=0,stateSize=0,one=0,two=0;
let pixels=new Uint8Array(256*240*4),audio=new Float32Array(),pixelFormat=1;
const buttons=[8,0,2,3,4,5,6,7]; // libretro IDs corresponding to the application's A,B,Select,Start,U,D,L,R.
function save(){
 if(!machine||!statePtr||!machine._retro_serialize(statePtr,stateSize))throw Error('OSS state export failed');
 return machine.HEAPU8.slice(statePtr,statePtr+stateSize);
}
async function initialize(rom:ArrayBuffer,wasm:ArrayBuffer){
 if(machine)throw Error('OSS instance already initialized');
 machine=await createCore({wasmBinary:new Uint8Array(wasm),print:()=>{},printErr:()=>{}}) as Module;
 const m=machine;const strings=new Map<string,number>();
 const str=(value:string)=>{let p=strings.get(value);if(p===undefined){const n=m.lengthBytesUTF8(value)+1;p=m._malloc(n);if(!p)throw Error('OSS memory limit');m.stringToUTF8(value,p,n);strings.set(value,p);}return p;};
 const options=new Map<string,string>([
  ['fceumm_region','NTSC'],['fceumm_ramstate','fill $00'],['fceumm_sndrate_hint','48KHz'],['fceumm_sndquality','Low'],
  ['fceumm_sndstereodelay','disabled'],['fceumm_sndlowpass','disabled'],['fceumm_ntsc_filter','disabled'],
  ['fceumm_turbo_enable','None'],['fceumm_overclocking','disabled'],['fceumm_overscan_h_left','0'],['fceumm_overscan_h_right','0'],['fceumm_overscan_v_top','0'],['fceumm_overscan_v_bottom','0']
 ]);
 m._retro_set_environment(m.addFunction((command,p)=>{
  if(command===9||command===31){m.HEAPU32[p>>>2]=str('/');return 1;}
  if(command===10){pixelFormat=m.HEAPU32[p>>>2];if(pixelFormat!==1)throw Error('Unsupported OSS pixel format');return 1;}
  if(command===15){const key=m.UTF8ToString(m.HEAPU32[p>>>2]);const value=options.get(key);if(value===undefined)return 0;m.HEAPU32[(p+4)>>>2]=str(value);return 1;}
  if(command===16){for(let q=p;m.HEAPU32[q>>>2];q+=8){const key=m.UTF8ToString(m.HEAPU32[q>>>2]),values=m.UTF8ToString(m.HEAPU32[(q+4)>>>2]);if(!options.has(key))options.set(key,values.split('; ')[1].split('|')[0]);}return 1;}
  if(command===52){m.HEAPU32[p>>>2]=0;return 1;}
  if(command===17){m.HEAPU8[p]=0;return 1;}
  if(command===3){m.HEAPU8[p]=1;return 1;}
  // No host filesystem, network, storage, threads, HD packs or device extensions.
  return 0;
 },'iii'));
 m._retro_set_video_refresh(m.addFunction((p,w,h,pitch)=>{
  if(!p)return;if(w!==256||h!==240||pitch<1024||pitch>4096||p+pitch*h>m.HEAPU8.length)throw Error('Invalid OSS video output');
  const next=new Uint8Array(256*240*4);for(let y=0;y<h;y++)for(let x=0;x<w;x++){
   const at=p+y*pitch+x*4,out=(y*w+x)*4;next[out]=m.HEAPU8[at+2];next[out+1]=m.HEAPU8[at+1];next[out+2]=m.HEAPU8[at];next[out+3]=255;
  }pixels=next;
 },'viiii'));
 m._retro_set_audio_sample(m.addFunction(()=>{},'vii'));
 m._retro_set_audio_sample_batch(m.addFunction((p,n)=>{
  if(n<0||n>2048||p+n*4>m.HEAPU8.length)throw Error('Invalid OSS audio output');
  const next=new Float32Array(n);for(let index=0;index<n;index++)next[index]=m.HEAP16[(p>>>1)+index*2]/32768;audio=next;return n;
 },'iii'));
 m._retro_set_input_poll(m.addFunction(()=>{},'v'));
 m._retro_set_input_state(m.addFunction((port,device,index,key)=>{
  if(port>1||device!==1||index!==0)return 0;const bit=buttons.indexOf(key);return bit<0?0:(((port===0?one:two)>>>bit)&1);
 },'iiiii'));
 m.FS.writeFile('/game.nes',new Uint8Array(rom));m._retro_init();m._retro_set_controller_port_device(0,1);m._retro_set_controller_port_device(1,1);
 const info=m._malloc(16);if(!info)throw Error('OSS memory limit');m.HEAPU8.fill(0,info,info+16);m.HEAPU32[info>>>2]=str('/game.nes');
 try{if(!m._retro_load_game(info))throw Error('This NES game cannot run here.');}finally{m._free(info);}
 stateSize=m._retro_serialize_size();if(stateSize<16||stateSize>FCE_STATE_LIMIT)throw Error('OSS state exceeds codec limit');
 statePtr=m._malloc(stateSize);if(!statePtr)throw Error('OSS memory limit');schema=new FceStateSchema(save());
 const av=m._malloc(40);m._retro_get_system_av_info(av);const fps=m.HEAPF64[(av+24)>>>3],rate=m.HEAPF64[(av+32)>>>3];m._free(av);
 if(fps<59||fps>61||rate!==48000)throw Error('Unsupported OSS timing profile');
 return {fps,state:save(),memoryBytes:m.HEAPU8.length};
}
onmessage=async({data}:{data:{id:number;type:string;rom?:ArrayBuffer;wasm?:ArrayBuffer;bytes?:Uint8Array;p1?:number;p2?:number}})=>{
 try{
  let result:unknown;
  if(data.type==='initialize')result=await initialize(data.rom!,data.wasm!);
  else if(!machine||!schema)throw Error('OSS instance not loaded');
  else if(data.type==='save')result=save();
  else if(data.type==='restore'){
   const bytes=data.bytes!;schema.validate(bytes);machine.HEAPU8.set(bytes,statePtr);
   if(!machine._retro_unserialize(statePtr,bytes.length))throw Error('OSS state restore failed');
   const restored=save();if(restored.length!==bytes.length||restored.some((v,index)=>v!==bytes[index]))throw Error('OSS restore changed canonical hardware state');
   // Exercise a frame only in this isolated candidate. Rewind it before activation.
   one=0;two=0;machine._retro_run();machine.HEAPU8.set(bytes,statePtr);
   if(!machine._retro_unserialize(statePtr,bytes.length))throw Error('OSS candidate recovery failed');
   const canonical=save();if(canonical.some((v,index)=>v!==bytes[index]))throw Error('OSS restore is not repeatable');
   pixels=new Uint8Array(256*240*4);audio=new Float32Array();result=canonical;
  }else if(data.type==='frame'){
   if(!Number.isInteger(data.p1)||!Number.isInteger(data.p2)||data.p1!<0||data.p1!>255||data.p2!<0||data.p2!>255)throw Error('Invalid OSS input');
   one=data.p1!;two=data.p2!;audio=new Float32Array();machine._retro_run();result={pixels,audio,memoryBytes:machine.HEAPU8.length};
  }else throw Error('Invalid OSS operation');
  postMessage({id:data.id,result});
 }catch(error){postMessage({id:data.id,error:error instanceof Error?error.message:'OSS emulator failed'});}
};
