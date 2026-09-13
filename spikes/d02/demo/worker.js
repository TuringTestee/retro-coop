let e;
const copy = kind => {const ptr=e.output(kind),len=e.output_len();return new Uint8Array(e.memory.buffer,ptr,len).slice().buffer;};
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
      const rom=new Uint8Array(data.rom),ptr=e.input_alloc(rom.length);
      new Uint8Array(e.memory.buffer,ptr,rom.length).set(rom);e.initialize(ptr,rom.length);
      postMessage({type:'ready'});
    }else if(data.type==='frame'){
      e.manual_frame(data.p1,data.p2);const pixels=copy(5),audio=copy(2);
      postMessage({type:'frame',pixels,audio},[pixels,audio]);
    }else if(data.type==='pause'){postMessage({type:'paused'});
    }else if(data.type==='save'){e.save();postMessage({type:'saved'});
    }else if(data.type==='restore'){e.restore();postMessage({type:'restored'});}
  }catch(error){postMessage({type:'error',message:error.message});}
};
