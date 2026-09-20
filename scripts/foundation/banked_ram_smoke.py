"""Real-worker CPU banking, validated files and regional rewind for original fixtures."""
from banked_ram_fixture import cartridge
from worker_probe import prepare_worker_probe, finish_worker_probe


def verify_banked_ram(browser, url, worker_path):
    cases = [('banked-controls', [17, 34, 51, 68, 68, 68, 17]),
             ('sorom', [17, 34]), ('single-bank', [68, 68, 68, 68]),
             ('large-chr', [68, 68, 68, 68]), ('mmc1a', [17, 34, 51, 68]),
             ('banked-partial', [17, 34, 51, 68]), ('mirrored', [16]),
             ('mirrored-control', [16])]
    page, requests = prepare_worker_probe(browser, url)
    result = page.evaluate('''({workerPath,cases,progress})=>runWorkerProbe(workerPath,async({ensure,digest,equal,create,ask})=>{
      const state=async(worker,id)=>{const r=await ask(worker,{type:'state-export',requestId:id});ensure(r.type==='state-exported','state export '+r.message);return r.bytes};
      const decode=bytes=>JSON.parse(new TextDecoder().decode(new Uint8Array(bytes).slice(72)));
      const frame=async(worker)=>{const r=await ask(worker,{type:'frame',p1:0,p2:0});ensure(r.type==='frame','frame '+r.message);return r};
      const mappings=[];
      for(const {name,rom,expected} of cases) {
        const worker=create();ensure((await ask(worker,{type:'load',rom:new Uint8Array(rom).buffer})).type==='ready','load '+name);await frame(worker);
        const before=await state(worker,1),v=decode(before);
        ensure(v.hardware.wram[32]===128 && equal(v.hardware.wram.slice(16,16+expected.length),expected),'CPU observations '+name);
        if(name==='sorom' || name==='banked-partial') {
          const banks=name==='sorom'?2:4;
          for(let b=0;b<banks;b++)ensure(v.hardware.memory.ram[b*8192]===(b+1)*17,'distinct actual RAM banks');
          if(name==='banked-partial')ensure(v.mapper.Sxrom.mmc1.shift_count===2,'CPU partial serial preserved');
          const battery=await ask(worker,{type:'battery-export',requestId:2});ensure(battery.type==='battery-exported','battery export');
          ensure(battery.bytes.byteLength===76+banks*8192,'explicit NES2 battery geometry');
          const blank=new Uint8Array(battery.bytes.slice(0));blank.fill(0,76);blank.set(await digest(blank.slice(76)),44);
          ensure((await ask(worker,{type:'battery-import',requestId:3,bytes:blank.buffer})).type==='battery-imported','valid blank battery');
          ensure(decode(await state(worker,4)).hardware.memory.ram[8192]===0,'battery replacement really happened');
          ensure((await ask(worker,{type:'battery-import',requestId:5,bytes:battery.bytes})).type==='battery-imported','restore all banks');
          ensure(equal(new Uint8Array(await state(worker,6)),new Uint8Array(before)),'battery restore preserves CPU/partial mapper');
          const broken=new Uint8Array(before.slice(0));broken[broken.length-1]^=1;
          ensure((await ask(worker,{type:'state-import',requestId:7,bytes:broken.buffer})).type==='state-error','damaged state nonfatal');
          const wrongCore=new Uint8Array(before.slice(0));wrongCore[8]^=1;
          ensure((await ask(worker,{type:'state-import',requestId:8,bytes:wrongCore.buffer})).type==='state-error','incompatible identity');
          ensure(equal(new Uint8Array(await state(worker,9)),new Uint8Array(before)),'rejected imports preserve timeline');
        }
        mappings.push({case:name,observed:v.hardware.wram.slice(16,16+expected.length),partialBits:v.mapper.Sxrom.mmc1.shift_count});worker.terminate();
      }
      const regional=[];
      for(const region of [0,1,3]) {
        const rom=new Uint8Array(progress);rom[12]=region;const worker=create(),reference=create();
        for(const target of [worker,reference])ensure((await ask(target,{type:'load',rom:rom.buffer})).type==='ready','progress load');
        let current=await frame(worker);const first=await state(worker,10),initial=decode(first),rate=initial.hardware.apu.clock_rate;
        const trace=[0];while(current.rewind.cycles/rate<11.25){current=await frame(worker);ensure(!current.rewind.issue,'history recording');trace.push(current.rewind.cycles)}
        const original=await state(worker,11),last=decode(original),cycles=(last.hardware.cpu.cycle-initial.hardware.cpu.cycle)>>>0;
        ensure(cycles===current.rewind.cycles && current.rewind.availableSeconds===10,'actual regional duration');
        let target=trace.length-1;while(trace[target]>cycles-10*rate)target--;
        const result=await ask(worker,{type:'state-rewind',requestId:12,seconds:10});ensure(result.type==='state-rewound','rewind '+result.message);
        ensure(result.info.frame===target && (cycles-result.info.cycles)/rate>=10,'exact target');
        ensure(result.info.peakBytes<=32*1024*1024 && result.info.retainedBytes<=32*1024*1024,'actual retained capacity');
        ensure((await ask(reference,{type:'state-import',requestId:13,bytes:first})).type==='state-imported','reference import');let expected;
        for(let i=1;i<=target;i++)expected=await frame(reference);
        ensure(equal(new Uint8Array(await state(worker,14)),new Uint8Array(await state(reference,15))),'banked target canonical state');
        ensure(equal(new Uint8Array(result.pixels),new Uint8Array(expected.pixels)),'banked target pixels');
        for(let i=target+1;i<trace.length;i++)await frame(worker);
        ensure(equal(new Uint8Array(await state(worker,16)),new Uint8Array(original)),'banked exact future replay');
        regional.push({region,target,frames:trace.length-1,cycles,clockRate:rate,actualSeconds:(cycles-result.info.cycles)/rate,history:result.info,canonicalReplay:true,pixels:true});
        worker.terminate();reference.terminate();
      }
      return {mappings,regional};
    })''', {'workerPath': worker_path, 'cases': [{'name': name, 'rom': list(cartridge(name)), 'expected': expected} for name, expected in cases], 'progress': list(cartridge('banked-progress'))})
    return finish_worker_probe(page, requests, url, result)


if __name__ == '__main__':
    from worker_probe import run_worker_check
    run_worker_check(verify_banked_ram)
