#!/usr/bin/env python3
"""Exercise the documented demo's custom host upload and recovery in Chromium."""
import asyncio
import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen
from playwright.async_api import async_playwright, Error as PlaywrightError

ROOT=Path(__file__).resolve().parents[2]
URL='http://127.0.0.1:8895/'
FIXTURE=ROOT/'apps/client/public/generated/diagnostic.nes'

async def main():
    assert FIXTURE.exists(), 'Run sh scripts/foundation/prepare.sh first'
    output=Path(os.environ.get('RETRO_COOP_RT2_OUTPUT','/tmp/retro-coop-rt2'))
    output.mkdir(parents=True,exist_ok=True)
    rom_dir=tempfile.TemporaryDirectory(prefix='retro-coop-rt2-')
    env={**os.environ,'RETRO_COOP_SKIP_INSTALL':'1','RETRO_COOP_SKIP_PREPARE':'1','RETRO_COOP_CLIENT_PORT':'8895','RETRO_COOP_COORDINATOR_PORT':'8897','COORDINATOR_ROM_DIR':rom_dir.name}
    log=open('/tmp/retro-coop-rt2-demo.log','w')
    service=subprocess.Popen(['sh','scripts/demo.sh'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    started=time.monotonic()
    try:
        for _ in range(100):
            try:
                with urlopen(URL,timeout=.2) as response:
                    if response.status==200:break
            except OSError:await asyncio.sleep(.1)
        else:raise AssertionError('The README demo did not start')
        async with async_playwright() as playwright:
            browser=await playwright.chromium.launch()
            context=await browser.new_context()
            host=await context.new_page()
            await host.goto(URL)
            await host.get_by_role('button',name='Create game',exact=True).click()
            await host.get_by_label('Room access').select_option('unlisted')
            release=asyncio.Event();seen=asyncio.Event()
            async def hold(route):
                seen.set();await release.wait();await route.continue_()
            await host.route('**/rooms/*/rom',hold)
            await host.set_input_files('input[type=file]',str(FIXTURE))
            await host.get_by_role('button',name='Create room',exact=True).click()
            await asyncio.wait_for(seen.wait(),15)
            assert await host.get_by_role('button',name='Cancel',exact=True).is_visible()
            assert await host.get_by_test_id('room-view').count()==0
            guest=await context.new_page();await guest.goto(URL)
            assert await guest.locator('.room-list li').filter(has_text='1/2 · Waiting for guest').count()==0
            await host.get_by_role('button',name='Cancel',exact=True).click()
            release.set()
            await host.get_by_role('button',name='Create room',exact=True).wait_for()
            await host.unroute('**/rooms/*/rom',hold)
            failed=[False]
            async def fail_once(route):
                if not failed[0]:failed[0]=True;await route.abort('failed')
                else:await route.continue_()
            await host.route('**/rooms/*/rom',fail_once)
            await host.get_by_role('button',name='Create room',exact=True).click()
            await host.wait_for_function("document.body.textContent.includes('Upload connection failed')",timeout=15000)
            await host.get_by_role('button',name='Create room',exact=True).wait_for()
            failure_text=await host.locator('.create-options [role=status]').first.inner_text()
            assert 'failed' in failure_text.lower() or 'timed out' in failure_text.lower(),failure_text
            assert await host.get_by_test_id('room-view').count()==0
            await host.unroute('**/rooms/*/rom',fail_once)
            expired=[False]
            async def expire_once(route):
                if route.request.method=='PUT' and not expired[0]:
                    expired[0]=True;await asyncio.sleep(6.5)
                try:await route.continue_()
                except PlaywrightError:
                    # The client aborts when the server expires the hidden intent.
                    pass
            await host.route('**/rooms/*/rom',expire_once)
            await host.get_by_role('button',name='Create room',exact=True).click()
            await host.wait_for_function("document.body.textContent.includes('Retry upload to create a fresh room')",timeout=20000)
            assert await host.get_by_test_id('room-view').count()==0
            await host.unroute('**/rooms/*/rom',expire_once)
            await host.get_by_role('button',name='Create room',exact=True).click()
            await host.get_by_role('button',name='Start game',exact=True).wait_for(timeout=30000)
            assert 'Unlisted' in await host.locator('#room-heading').inner_text()
            assert await host.get_by_test_id('room-view').count()==1
            assert await host.get_by_role('button',name='Start game',exact=True).is_enabled()
            await host.screenshot(path=str(output/'host.png'),full_page=True)
            public=await context.new_page();await public.goto(URL)
            await public.get_by_role('button',name='Create game',exact=True).click()
            await public.set_input_files('input[type=file]',str(FIXTURE))
            await public.get_by_role('button',name='Create room',exact=True).click()
            await public.get_by_role('button',name='Start game',exact=True).wait_for(timeout=30000)
            public_code=(await public.locator('#room-heading').inner_text()).split(' · ')[-1]
            await guest.get_by_role('searchbox',name='Search room, game, host, or code').fill(public_code)
            await guest.locator('.room-list li').filter(has_text=public_code).wait_for()
            invalid=await context.new_page();await invalid.goto(URL)
            await invalid.get_by_role('button',name='Create game',exact=True).click()
            await invalid.set_input_files('input[type=file]',{'name':'bad.nes','mimeType':'application/octet-stream','buffer':b'invalid'})
            await invalid.get_by_role('button',name='Create room',exact=True).wait_for()
            assert await invalid.get_by_role('button',name='Create room',exact=True).is_disabled()
            assert await invalid.get_by_test_id('room-view').count()==0
            included=await context.new_page();await included.goto(URL)
            await included.get_by_role('button',name='Join as host').first.click()
            await included.get_by_role('button',name='Start game',exact=True).wait_for(timeout=30000)
            await browser.close()
        result={'public_entrypoint':URL,'cancel_hidden':True,'failure_hidden':True,'expired_intent_hidden':True,'retry_unlisted':True,'public_directory':True,'invalid_file_hidden':True,'included_host':True,'duration_seconds':round(time.monotonic()-started,2)}
        (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
    finally:
        os.killpg(service.pid,signal.SIGTERM)
        try:service.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(service.pid,signal.SIGKILL);service.wait()
        log.close()
        rom_dir.cleanup()

if __name__=='__main__':asyncio.run(main())
