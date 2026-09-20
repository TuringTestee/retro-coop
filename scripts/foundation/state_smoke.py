"""Real worker/WASM whole-state replay, malformed imports and profile isolation."""
from worker_probe import prepare_worker_probe, finish_worker_probe


def verify_state(browser,url,rom,worker_path):
    page,requests=prepare_worker_probe(browser,url)
    variant=bytearray(rom)
    variant[4]=2
    variant[16+16384:16+16384]=rom[16:16+16384]
    variant[6]=0x12
    result=page.evaluate('''({rom,workerPath})=>runWorkerProbe(workerPath,async ({ensure,digest,equal,create,ask})=>{
      const worker=create(),other=create();
      for(const target of [worker,other]) ensure((await ask(target,{type:'load',rom:new Uint8Array(rom).buffer})).type==='ready','load');
      const frame={type:'frame',p1:64,p2:0};
      for(let i=0;i<8;i++)ensure((await ask(worker,frame)).type==='frame','advance before capture');
      const save=await ask(worker,{type:'state-export',requestId:1});
      ensure(save.type==='state-exported' && save.requestId===1,'state export');
      const bytes=new Uint8Array(save.bytes),header=72;
      ensure(new TextDecoder().decode(bytes.slice(0,8))==='RCSTATE1','state schema');
      const original=JSON.parse(new TextDecoder().decode(bytes.slice(header)));
      ensure(Object.keys(original.hardware.memory).join(',')==='ram','no imported memory geometry');
      ensure(original.mapper.Sxrom,'mutable mapper retained');
      const load=async target=>{
        const result=await ask(target,{type:'state-import',requestId:2,bytes:bytes.buffer});
        ensure(result.type==='state-imported' && result.requestId===2,'compatible restore: '+result.message);
      };
      for(let i=0;i<3;i++)await ask(worker,{type:'frame',p1:0,p2:0});
      await load(worker);await load(other); // Second codec is first constructed by import at power-on.
      for(let i=0;i<5;i++) {
        const a=await ask(worker,frame),b=await ask(other,frame);
        ensure(a.type==='frame' && b.type==='frame','restored frame');
        ensure(equal(new Uint8Array(a.pixels),new Uint8Array(b.pixels)),'restored video diverged');
        ensure(equal(new Uint8Array(a.audio),new Uint8Array(b.audio)),'fresh audio epochs diverged');
      }
      const before=await ask(worker,{type:'state-export',requestId:3});
      const unchanged=async()=>{
        const current=await ask(worker,{type:'state-export',requestId:4});
        ensure(current.type==='state-exported' && equal(new Uint8Array(current.bytes),new Uint8Array(before.bytes)),'invalid import changed live state');
      };
      const canonical=value=>Array.isArray(value) ? value.map(canonical) : value && typeof value==='object' ? Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])) : value;
      const malformed=[];
      for(const offset of [0,8,40,header]){const bad=bytes.slice();bad[offset]^=1;malformed.push(bad.buffer)}
      malformed.push(bytes.slice(0,-1).buffer,new Uint8Array([...bytes,0]).buffer);
      // Recompute the checksum to test schema admission, not merely damage detection.
      for(const change of [v=>v.hardware.memory={len:4294967295,ram_start:4294967295,ram:[]},v=>v.mapper.Sxrom.mmc1.shift_count=5,v=>v.hardware.ppu.spr_count=9]) {
        const value=JSON.parse(new TextDecoder().decode(bytes.slice(header)));change(value);
        const payload=new TextEncoder().encode(JSON.stringify(canonical(value)));
        const bad=new Uint8Array(header+payload.length);bad.set(bytes.slice(0,40));bad.set(await digest(payload),40);bad.set(payload,header);malformed.push(bad.buffer);
      }
      const cap=worker.proof.find(call=>call.name==='local_state_limit').result;
      let allocations=worker.proof.filter(call=>call.name==='local_state_alloc').length;
      const oversized=await ask(worker,{type:'state-import',requestId:5,bytes:new ArrayBuffer(cap+1)});
      ensure(oversized.type==='state-error' && oversized.requestId===5,'oversized error');
      ensure(allocations===worker.proof.filter(call=>call.name==='local_state_alloc').length,'oversized reached allocator');await unchanged();
      for(const bad of malformed) {
        const result=await ask(worker,{type:'state-import',requestId:6,bytes:bad});
        ensure(result.type==='state-error' && result.requestId===6,'malformed accepted');await unchanged();
      }
      const a=await ask(worker,frame),b=await ask(other,frame);
      ensure(equal(new Uint8Array(a.pixels),new Uint8Array(b.pixels)) && equal(new Uint8Array(a.audio),new Uint8Array(b.audio)),'rejection broke future execution');
      const mismatched=create();
      ensure((await ask(mismatched,{type:'load',rom:new Uint8Array([...rom,1]).buffer})).type==='ready','other ROM');
      ensure((await ask(mismatched,{type:'state-import',requestId:7,bytes:bytes.buffer})).type==='state-error','ROM mismatch');
      const unvalidated=create(),bandai=new Uint8Array(rom);bandai[6]=0xd2;bandai[7]=0x90;
      ensure((await ask(unvalidated,{type:'load',rom:bandai.buffer})).type==='ready','unvalidated profile must still load');
      ensure((await ask(unvalidated,frame)).type==='frame','unvalidated profile plays');
      const unsupported=await ask(unvalidated,{type:'state-export',requestId:8});
      ensure(unsupported.type==='state-error' && unsupported.message.includes('not yet validated'),'clear profile error');
      ensure((await ask(unvalidated,frame)).type==='frame','profile error must not stop play');
      ensure((await ask(unvalidated,{type:'battery-export',requestId:9})).type==='battery-exported','profile error must not block battery');
      return {bytes:bytes.length,core_owned_limit:cap,matching_identity_across_first_export_and_import:true,restored_video_and_fresh_epoch_pcm_match:true,malformed_cases:malformed.length,live_state_bytes_unchanged_on_failure:true,oversized_rejected_before_wasm_allocation:true,rom_mismatch_rejected:true,unvalidated_profile_keeps_play_and_battery:true,no_audio_presented:true};
    })''',{'rom':list(variant),'workerPath':worker_path})
    return finish_worker_probe(page,requests,url,result)
