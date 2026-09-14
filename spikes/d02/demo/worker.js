let e;
const copy = kind => {const ptr=e.local_output(kind),len=e.local_output_len();return new Uint8Array(e.memory.buffer,ptr,len).slice().buffer;};
const check = ok => {if(!ok)throw Error(new TextDecoder().decode(copy(0)));};
onmessage=async({data})=>{
  try{
    if(data.type==='load'){
      const response=await fetch('../target/wasm32-unknown-unknown/release/retro_coop_d02.wasm');
      if(!response.ok)throw Error('Emulator build not found. Run the demo build command.');
      const module=await WebAssembly.compile(await response.arrayBuffer()),imports={};
      for(const i of WebAssembly.Module.imports(module)){
        if(i.kind!=='function')throw Error('Unsupported emulator import');
        (imports[i.module]??={})[i.name]=()=>{throw Error('Unexpected host access: '+i.name)};
      }
      e=(await WebAssembly.instantiate(module,imports)).exports;
      const rom=new Uint8Array(data.rom),ptr=e.local_alloc(rom.length);
      new Uint8Array(e.memory.buffer,ptr,rom.length).set(rom);check(e.local_initialize(ptr,rom.length));
      postMessage({type:'ready',fps:e.local_fps()});
    }else if(data.type==='frame'){
      check(e.local_frame(data.p1,data.p2));const pixels=copy(5),audio=copy(2);
      postMessage({type:'frame',pixels,audio},[pixels,audio]);
    }else if(data.type==='pause'){postMessage({type:'paused'});
    }else if(data.type==='save'){check(e.local_save());postMessage({type:'saved'});
    }else if(data.type==='restore'){check(e.local_restore());postMessage({type:'restored'});}
  }catch(error){postMessage({type:'error',message:error.message});}
};
