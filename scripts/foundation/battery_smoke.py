"""Exercise the actual worker/WASM battery ABI, without presenting audio or save UI."""

from worker_probe import prepare_worker_probe, finish_worker_probe

def verify_battery(browser, url, rom, worker_path):
    page,requests=prepare_worker_probe(browser,url)
    variant=bytearray(rom)
    variant[4]=2
    variant[16+16384:16+16384]=rom[16:16+16384]
    variant[6]=0x12  # MMC1, battery present.
    result=page.evaluate('''({rom,workerPath})=>runWorkerProbe(workerPath,async ({ensure,digest,equal,create,ask})=>{
        const worker=create(),twin=create();
        let identity;
        for(const target of [worker,twin]) {
          const ready=await ask(target,{type:'load',rom:new Uint8Array(rom).buffer});
          ensure(ready.type==='ready','worker failed to load');identity=ready.coreSha256;
        }
        const exported=await ask(worker,{type:'battery-export',requestId:1});
        ensure(exported.type==='battery-exported' && exported.requestId===1,'export correlation');
        const battery=new Uint8Array(exported.bytes),header=76;
        ensure(new TextDecoder().decode(battery.slice(0,8))==='RCBAT001','schema');
        ensure(battery.length>header,'nonempty battery');
        // Construct a valid nonzero battery payload and matching accidental-corruption digest.
        for(let i=header;i<battery.length;i++)battery[i]=(i*17+5)&255;
        battery.set(await digest(battery.slice(header)),44);
        for(const target of [worker,twin]) {
          const imported=await ask(target,{type:'battery-import',requestId:2,bytes:battery.buffer});
          ensure(imported.type==='battery-imported' && imported.requestId===2,'import correlation');
        }
        const cap=worker.proof.find(call=>call.name==='local_battery_limit').result;
        ensure(Number.isSafeInteger(cap) && cap>=battery.length,'core-owned limit');
        // Exact limit reaches file validation; cap+1 never reaches WASM allocation.
        let prior=worker.proof.filter(call=>call.name==='local_battery_alloc').length;
        const atLimit=await ask(worker,{type:'battery-import',requestId:7,bytes:new ArrayBuffer(cap)});
        ensure(atLimit.type==='battery-error' && atLimit.message==='Invalid battery file length','exact limit must reach format validator');
        ensure(worker.proof.filter(call=>call.name==='local_battery_alloc').length===prior+1,'exact limit allocation');
        prior++;
        const aboveLimit=await ask(worker,{type:'battery-import',requestId:8,bytes:new ArrayBuffer(cap+1)});
        ensure(aboveLimit.type==='battery-error' && aboveLimit.requestId===8,'oversized operation error');
        ensure(worker.proof.filter(call=>call.name==='local_battery_alloc').length===prior,'oversized copy/allocation occurred');
        const invalid=[];
        for(const offset of [0,8,40,44,header]) {const bytes=battery.slice();bytes[offset]^=1;invalid.push(bytes.buffer)}
        invalid.push(new ArrayBuffer(0),battery.slice(0,-1).buffer,new Uint8Array([...battery,0]).buffer,new ArrayBuffer(cap+1));
        for(const bytes of invalid) {
          const result=await ask(worker,{type:'battery-import',requestId:3,bytes});
          ensure(result.type==='battery-error' && result.requestId===3,'malformed battery accepted');
          const after=await ask(worker,{type:'battery-export',requestId:4});
          ensure(after.type==='battery-exported' && equal(new Uint8Array(after.bytes),battery),'failed import mutated battery');
        }
        for(let i=0;i<5;i++) {
          const request={type:'frame',p1:64,p2:0};
          const a=await ask(worker,request),b=await ask(twin,request);
          ensure(a.type==='frame' && b.type==='frame','failed import broke continued execution');
          ensure(equal(new Uint8Array(a.pixels),new Uint8Array(b.pixels)),'replay pixels diverged');
          ensure(equal(new Uint8Array(a.audio),new Uint8Array(b.audio)),'replay PCM diverged');
        }
        const other=create(),changed=new Uint8Array([...rom,1]);
        ensure((await ask(other,{type:'load',rom:changed.buffer})).type==='ready','different ROM load');
        ensure((await ask(other,{type:'battery-import',requestId:5,bytes:battery.buffer})).type==='battery-error','exact ROM mismatch accepted');
        const noBattery=create(),plain=new Uint8Array(rom);plain[6]&=~2;
        ensure((await ask(noBattery,{type:'load',rom:plain.buffer})).type==='ready','plain cartridge load');
        ensure((await ask(noBattery,{type:'battery-export',requestId:6})).type==='battery-error','no-battery cartridge exported');
        return {mapper:1,bytes:battery.length,core_owned_limit:cap,exact_limit_reaches_validator:true,oversized_rejected_before_wasm_allocation:true,coreSha256:identity,correlated_roundtrip:true,malformed_cases:invalid.length,failed_import_preserves_battery_and_future_pixels_pcm:true,exact_rom_mismatch_rejected:true,no_battery_error:true,audio_presented:false};
    })''',{'rom':list(variant),'workerPath':worker_path})
    return finish_worker_probe(page,requests,url,result)
