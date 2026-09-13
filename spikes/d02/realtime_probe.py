"""Measure two local browsers; never transmit ROMs through the peer connection."""
import argparse
import asyncio
import base64
import hashlib
import json
import os
import platform
import time
from pathlib import Path
from playwright.async_api import async_playwright

async def run():
    parser=argparse.ArgumentParser()
    parser.add_argument('rom',type=Path)
    parser.add_argument('--wasm',type=Path,default=Path('target/wasm32-unknown-unknown/release/retro_coop_d02.wasm'))
    parser.add_argument('--seconds',type=int,choices=[10,600],default=600)
    parser.add_argument('--pair',choices=['Chrome-Chrome','Firefox-Firefox','Chrome-Firefox'],default='Chrome-Firefox')
    parser.add_argument('--bundled-chromium',action='store_true')
    parser.add_argument('--output',type=Path,default=Path('realtime.local.json'))
    args=parser.parse_args()
    assert 10<=args.seconds<=600
    rom=args.rom.read_bytes();wasm=args.wasm.read_bytes()
    adapter=hashlib.sha256()
    for filename in ['realtime.js','realtime-worker.js','realtime-audio.js','realtime.html']:
        adapter.update(filename.encode()+b'\0'+Path(filename).read_bytes())
    result={'run_id':os.environ.get('D02_RUN_ID'),'platform':platform.platform(),'rom_bytes':len(rom),'wasm_bytes':len(wasm),'rom_sha256':hashlib.sha256(rom).hexdigest(),'wasm_sha256':hashlib.sha256(wasm).hexdigest(),'adapter_sha256':adapter.hexdigest(),'pair':args.pair,'seconds':args.seconds,'impairment':'isolated kernel netem:50ms+/-10ms delay,1% packet loss on loopback','route':'isolated private host ICE; no STUN/TURN','voice':'synthetic oscillator, not real microphone/speaker listening','chromium_launch':'headless, default --mute-audio removed','runs':[]}
    identity=json.dumps({'adapter':result['adapter_sha256'],'protocol':'D02-RT1','rom':result['rom_sha256'],'wasm':result['wasm_sha256'],'region':'NTSC','input_lead':12},sort_keys=True,separators=(',',':'))
    async with async_playwright() as p:
        browsers=[];pages=[];page_errors=[]
        try:
            for role,name in enumerate(args.pair.split('-')):
                if name=='Chrome':
                    options={} if args.bundled_chromium else {'executable_path':'/usr/bin/google-chrome'}
                    browser=await p.chromium.launch(headless=True,ignore_default_args=['--mute-audio'],**options)
                else: browser=await p.firefox.launch(headless=True)
                browsers.append(browser);page=await browser.new_page();pages.append(page)
                errors=[];page_errors.append(errors)
                page.on('pageerror', lambda error, errors=errors: errors.append(str(error)))
                page.on('console',lambda message: print('browser console:',message.type,message.text,flush=True) if message.type in ['error','warning'] else None)
                await page.goto('http://127.0.0.1:8765/realtime.html')
                await page.evaluate('args=>probe.init(args)',{'role':role,'identity':identity,'seconds':args.seconds,'rom64':base64.b64encode(rom).decode(),'wasm64':base64.b64encode(wasm).decode()})
            await asyncio.gather(*(page.click('#enable') for page in pages))
            await asyncio.gather(*(page.wait_for_function("probe.audio.state==='running'",timeout=15000) for page in pages))
            offer=await pages[0].evaluate("probe.description('offer')")
            await pages[1].evaluate('d=>probe.pc.setRemoteDescription(d)',offer)
            answer=await pages[1].evaluate("probe.description('answer')")
            await pages[0].evaluate('d=>probe.pc.setRemoteDescription(d)',answer)
            await asyncio.gather(*(page.wait_for_function('probe.ready',timeout=30000) for page in pages))
            await asyncio.gather(*(page.evaluate('probe.start()') for page in pages))
            started=time.monotonic();last_report=-1
            while True:
                progress=await asyncio.gather(*(page.evaluate('({frame:probe.frame,completed:!!probe.completedAt,errors:probe.stats.errors})') for page in pages))
                if int(time.monotonic()-started)//10!=last_report:
                    last_report=int(time.monotonic()-started)//10
                    print(json.dumps({'elapsed_seconds':round(time.monotonic()-started,2),'progress':progress}),flush=True)
                if all(x['completed'] for x in progress) or any(x['errors'] for x in progress):break
                if time.monotonic()-started>args.seconds+125:raise TimeoutError('Whole pair deadline exceeded')
                await asyncio.sleep(.5)
            # Explicit hash-comparison readiness, not a guessed network drain delay.
            await asyncio.gather(*(page.wait_for_function('probe.stats.hashes.every(x=>probe.peerHashes?.has(x.frame))',timeout=10000) for page in pages))
            measurements=await asyncio.gather(*(page.evaluate('probe.result()') for page in pages))
            teardowns=await asyncio.gather(*(page.evaluate('probe.close()') for page in pages))
            for name,browser,measurement,teardown in zip(args.pair.split('-'),browsers,measurements,teardowns):
                result['runs'].append({'browser':'Chromium' if name=='Chrome' and args.bundled_chromium else name,'version':browser.version,**measurement,'teardown':teardown})
            result['canonical_equal']=result['runs'][0]['hashes']==result['runs'][1]['hashes']
            result['page_errors']=page_errors
            if any(page_errors):
                raise RuntimeError('Unhandled browser error: '+str(page_errors))
            if any(run['errors'] for run in result['runs']):
                raise RuntimeError('Browser runtime errors: '+str([run['errors'] for run in result['runs']]))
        except Exception as error:
            result['error']=str(error)
            result['diagnostics']=[]
            result['page_errors']=page_errors
            for page in pages:
                try: result['diagnostics'].append(await page.evaluate("({audioState:probe.audio?.state,audioEnableAtMs:probe.stats?.audioEnableAtMs,audioRunningAtMs:probe.stats?.audioRunningAtMs,frame:probe.frame,ready:probe.ready,errors:probe.stats?.errors,identityMatched:probe.stats?.identityMatched,channel:probe.channel?.readyState,connection:probe.pc?.connectionState,ice:probe.pc?.iceConnectionState,localCandidates:probe.pc?.localDescription?.sdp.split('\\r\\n').filter(s=>s.startsWith('a=candidate'))})"))
                except Exception: pass
        finally:
            args.output.write_text(json.dumps(result,indent=2)+'\n')
            if os.environ.get('D02_EVIDENCE_DIR'):
                (Path(os.environ['D02_EVIDENCE_DIR'])/'result-pointer.json').write_text(json.dumps({'output':str(args.output.resolve()),'run_id':result['run_id']}))
            await asyncio.gather(*(browser.close() for browser in browsers))
    if 'error' in result:raise RuntimeError(result['error'])

asyncio.run(run())
