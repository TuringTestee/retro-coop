"""Actual core-cycle history, mapper CPU writes, exact replay and local confirmation."""
import json
from worker_probe import prepare_worker_probe, finish_worker_probe


def verify_rewind_worker(browser,url,rom,worker_path):
    page,requests=prepare_worker_probe(browser,url)
    result=page.evaluate('''({rom,workerPath})=>runWorkerProbe(workerPath,async ({ensure,digest,equal,create,ask})=>{
      const results=[];
      for(const region of [0,1,3]) {
        const cartridge=new Uint8Array(16+32768+8192);cartridge.set(rom.slice(0,16));cartridge[4]=2;cartridge[6]=0x12;cartridge[7]=8;cartridge[10]=0x70;cartridge[12]=region;
        cartridge.set(rom.slice(16,16+16384),16);cartridge.set(rom.slice(16,16+16384),16+16384);cartridge.set(rom.slice(16+16384),16+32768);
        // Real CPU writes: switch PRG bank, leave MMC1 half-written through A001,
        // and continuously mutate battery RAM. Identical code remains mapped after switching.
        const program=[0x78];
        const write=(address,value)=>program.push(0xa9,value,0x8d,address&255,address>>8,0xea,0xea);
        for(const bit of [1,0,0,0,0])write(0xe000,bit);
        for(const bit of [1,0,1])write(0xa001,bit);
        write(0x6000,0x79);const loop=0x8000+program.length;program.push(0xee,0x01,0x60,0x4c,loop&255,loop>>8);
        cartridge.set(program,16);cartridge.set(program,16+16384);
        const worker=create(),reference=create();
        for(const target of [worker,reference])ensure((await ask(target,{type:'load',rom:cartridge.buffer})).type==='ready','regional mapper load');
        const frame=async(target,one,two)=>{const r=await ask(target,{type:'frame',p1:one,p2:two});ensure(r.type==='frame','frame '+r.message);return r;};
        const saved=async(target,id)=>{const r=await ask(target,{type:'state-export',requestId:id});ensure(r.type==='state-exported','export '+r.message);return r.bytes;};
        let current=await frame(worker,0,0);const first=await saved(worker,1),initial=JSON.parse(new TextDecoder().decode(new Uint8Array(first).slice(72)));
        ensure(initial.mapper.Sxrom.mmc1.prg===1 && initial.mapper.Sxrom.mmc1.shift_count===3,'CPU bank/partial serial writes');
        ensure(initial.hardware.memory.ram[0]===0x79,'CPU battery RAM write');
        const rate=initial.hardware.apu.clock_rate,trace=[{cycles:0,p1:0,p2:0}];
        while(current.rewind.cycles/rate<12.25) {
          const i=trace.length,p1=Math.floor(i/7)%256,p2=Math.floor(i/13)%256;current=await frame(worker,p1,p2);
          ensure(!current.rewind.issue,'recording '+current.rewind.issue);trace.push({cycles:current.rewind.cycles,p1,p2});
        }
        const original=await saved(worker,2),last=JSON.parse(new TextDecoder().decode(new Uint8Array(original).slice(72)));
        const actualCycles=(last.hardware.cpu.cycle-initial.hardware.cpu.cycle)>>>0;
        ensure(actualCycles===current.rewind.cycles && actualCycles/rate>=12.25,'independent exported CPU timing');
        ensure(current.rewind.availableSeconds===10 && current.rewind.spanSeconds>=10,'ten actual seconds retained');
        ensure(current.rewind.budgetBytes===32*1024*1024,'approved32MiB budget');
        ensure(current.rewind.retainedBytes<=current.rewind.budgetBytes && current.rewind.peakBytes<=current.rewind.budgetBytes,'real capacity budget');
        const desired=actualCycles-10*rate;let target=trace.length-1;while(trace[target].cycles>desired)target--;
        const rewound=await ask(worker,{type:'state-rewind',requestId:3,seconds:10});ensure(rewound.type==='state-rewound','rewind '+rewound.message);
        ensure(rewound.info.frame===target,'exact target frame');
        const liveHash=await ask(worker,{type:'state-hash',requestId:16});ensure(liveHash.type==='state-hash' && !liveHash.info.fresh,'rewind cannot claim a fresh initial state');
        ensure((actualCycles-rewound.info.cycles)/rate>=10,'requested elapsed duration');
        ensure((await ask(reference,{type:'state-import',requestId:4,bytes:first})).type==='state-imported','reference restore');
        let expected;
        for(let i=1;i<=target;i++)expected=await frame(reference,trace[i].p1,trace[i].p2);
        ensure(equal(new Uint8Array(await saved(worker,5)),new Uint8Array(await saved(reference,6))),'target canonical state');
        ensure(equal(new Uint8Array(rewound.pixels),new Uint8Array(expected.pixels)),'target pixels');
        for(let i=target+1;i<trace.length;i++)await frame(worker,trace[i].p1,trace[i].p2);
        ensure(equal(new Uint8Array(original),new Uint8Array(await saved(worker,7))),'forward replay after rewind');
        const before=await saved(worker,8);ensure((await ask(worker,{type:'state-rewind',requestId:9,seconds:11})).type==='state-error','invalid duration nonfatal');
        ensure(equal(new Uint8Array(before),new Uint8Array(await saved(worker,10))),'invalid duration changed timeline');
        ensure((await ask(worker,{type:'state-import',requestId:11,bytes:first})).type==='state-imported','manual import');
        ensure((await ask(worker,{type:'state-history',requestId:12})).info.availableSeconds===0,'import clears future/history');
        const battery=await ask(worker,{type:'battery-export',requestId:13});await frame(worker,1,0);
        ensure((await ask(worker,{type:'battery-import',requestId:14,bytes:battery.bytes})).type==='battery-imported','battery import');
        ensure((await ask(worker,{type:'state-history',requestId:15})).info.retainedBytes===0,'battery import releases history allocations');
        results.push({region,traceFrames:trace.length-1,targetFrame:target,actualCycles,clockRate:rate,actualRewoundSeconds:(actualCycles-rewound.info.cycles)/rate,history:current.rewind,rewound:rewound.info,canonicalReplay:true,pixels:true,cpuBank:initial.mapper.Sxrom.mmc1.prg,partialSerial:initial.mapper.Sxrom.mmc1.shift_count,batteryByte:initial.hardware.memory.ram[0]});
        worker.terminate();reference.terminate();
      }
      return {regionalCpuMapperReplay:results};
    })''',{'rom':list(rom),'workerPath':worker_path})
    return finish_worker_probe(page,requests,url,result)


def verify_rewind_ui(browser,url,rom,output):
    page=browser.new_page(viewport={'width':1280,'height':1000},accept_downloads=True)
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.add_init_script('''window.rewindAudio={buffers:0,finite:true,peak:0};const copy=AudioBuffer.prototype.copyToChannel;
      AudioBuffer.prototype.copyToChannel=function(samples,...args){rewindAudio.buffers++;for(const value of samples){rewindAudio.finite &&= Number.isFinite(value);rewindAudio.peak=Math.max(rewindAudio.peak,Math.abs(value))}return copy.call(this,samples,...args)};''')
    page.goto(url)
    page.get_by_label('NES cartridge file').set_input_files({'name':'rewind-local.nes','mimeType':'application/octet-stream','buffer':rom})
    page.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>5")
    page.get_by_role('button',name='Rewind',exact=True).click();dialog=page.get_by_role('dialog',name='Rewind local game')
    dialog.get_by_text('Not enough history yet.',exact=False).wait_for();assert dialog.get_by_role('button',name='Rewind 1 second',exact=True).is_disabled()
    dialog.get_by_role('button',name='Close rewind').click();page.get_by_role('button',name='Resume',exact=True).click()
    # Actual user-visible play: do not accelerate the RAF clock or worker frame loop.
    page.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>=650",timeout=25000)
    page.get_by_role('button',name='Rewind',exact=True).click();dialog.get_by_test_id('rewind-history').filter(has_text='10.00 seconds').wait_for()
    dialog.get_by_label('Seconds to rewind').select_option('10');dialog.get_by_role('button',name='Rewind 10 seconds',exact=True).click()
    page.screenshot(path=str(output.with_suffix('.rewind-before.png')),full_page=False)
    before=page.get_by_test_id('frames').inner_text();dialog.get_by_role('button',name='Cancel',exact=True).click();assert page.get_by_test_id('frames').inner_text()==before
    dialog.get_by_role('button',name='Rewind 10 seconds',exact=True).click();dialog.get_by_role('button',name='Confirm rewind',exact=True).click()
    dialog.get_by_test_id('rewind-status').filter(has_text='Future history was discarded').wait_for()
    after=page.get_by_test_id('frames').inner_text();assert int(before.split()[0])-int(after.split()[0])>=601
    page.screenshot(path=str(output.with_suffix('.rewind-after.png')),full_page=False)
    page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(output.with_suffix('.rewind-mobile.png')),full_page=False)
    audio_before=page.evaluate('rewindAudio.buffers')
    dialog.get_by_role('button',name='Close rewind').click();page.get_by_role('button',name='Resume',exact=True).click()
    page.wait_for_function("before=>Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>before+3",arg=int(after.split()[0]))
    page.wait_for_function('before=>rewindAudio.buffers>before',arg=audio_before)
    audio=page.evaluate('rewindAudio');assert audio['finite'] and audio['peak']>0
    page.get_by_label('NES cartridge file').set_input_files({'name':'replacement.nes','mimeType':'application/octet-stream','buffer':rom})
    page.get_by_role('button',name='Rewind',exact=True).click();dialog.get_by_text('Not enough history yet.',exact=False).wait_for()
    assert not errors,errors
    page.close();return {'shortHistoryDisabled':True,'cancelPreservesFrame':True,'before':before,'after':after,'confirmedRewindPaused':True,'explicitResumeWorks':True,'replacementClearsHistory':True,'mobileNoOverflow':True,'resumedPcmObserved':audio,'pageErrors':errors}
