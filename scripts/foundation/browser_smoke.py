"""Exercise local file admission, transactional replacement, real input/audio and privacy."""
import argparse
import contextlib
import hashlib
import json
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from battery_smoke import verify_battery
from state_smoke import verify_state
from saves_smoke import verify_saves
from persistence_smoke import verify_persistence
from rewind_smoke import verify_rewind_worker, verify_rewind_ui
from settings_smoke import verify_settings, verify_disconnected_load
from local_play import CORE_PROBE, enter_create, read_fingerprint, start_solo


@contextlib.contextmanager
def room_test_server(root):
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=root,
                               stdout=subprocess.PIPE, text=True)
    try:
        yield json.loads(service.stdout.readline())['url']
    finally:
        if service.poll() is None:
            service.terminate()
        service.wait(timeout=5)

parser = argparse.ArgumentParser()
parser.add_argument('--output', default='foundation.local.json')
parser.add_argument('--chrome', action='store_true')
args = parser.parse_args()
started = time.monotonic()
root = Path(__file__).resolve().parents[2]
output = Path(args.output)
output.parent.mkdir(parents=True,exist_ok=True)
rom = (root / 'apps/client/dist/generated/diagnostic.nes').read_bytes()
with room_test_server(root) as url:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            ignore_default_args=['--mute-audio'],
            **({'channel':'chrome'} if args.chrome else {}))
        page = browser.new_page(viewport={'width':1280,'height':1000})
        errors, requests = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: requests.append((request.method,request.url)))
        page.add_init_script('''window.proof={buffers:0,peak:0,starts:0,muted:true};
          const copy=AudioBuffer.prototype.copyToChannel;
          AudioBuffer.prototype.copyToChannel=function(data,...rest){proof.buffers++;for(const x of data)proof.peak=Math.max(proof.peak,Math.abs(x));return copy.call(this,data,...rest)};
          const connect=AudioNode.prototype.connect;
          AudioNode.prototype.connect=function(node,...rest){if(node instanceof GainNode)proof.muted=proof.muted && node.gain.value===0;return connect.call(this,node,...rest)};
          const start=AudioBufferSourceNode.prototype.start;
          AudioBufferSourceNode.prototype.start=function(...args){proof.starts++;return start.apply(this,args)};''')
        page.goto(url)
        page.screenshot(path=str(output.with_suffix('.before.png')),full_page=False)
        page.evaluate(CORE_PROBE)

        def select(data=rom,name='private-title.nes'):
            page.get_by_label('NES cartridge file').set_input_files({
                'name':name,'mimeType':'application/octet-stream','buffer':bytes(data)})

        def fingerprint():
            return read_fingerprint(page)

        def fresh_variant(data,name):
            tab=browser.new_page()
            try:
                tab.goto(url)
                enter_create(tab)
                tab.get_by_label('NES cartridge file').set_input_files({
                    'name':name,'mimeType':'application/octet-stream','buffer':bytes(data)})
                start_solo(tab,data)
                assert hashlib.sha256(data).hexdigest() in read_fingerprint(tab)
            finally:
                tab.close()

        # One keyboard action must open the real browser file chooser.
        with page.expect_file_chooser() as pending:
            page.get_by_role('button',name='Play locally',exact=True).focus()
            page.keyboard.press('Enter')
        pending.value.set_files({'name':'private-title.nes',
                                 'mimeType':'application/octet-stream','buffer':rom})
        page.locator('[data-page="local"]').wait_for()
        start_solo(page,rom)
        page.wait_for_function('proof.starts>3 && proof.peak>0')
        canvas=page.locator('canvas')
        canvas.focus();before=canvas.evaluate('node=>node.toDataURL()')
        page.keyboard.down('ArrowRight')
        page.wait_for_function('previous=>document.querySelector("canvas").toDataURL()!==previous',arg=before)
        page.keyboard.up('ArrowRight')
        page.screenshot(path=str(output.with_suffix('.after.png')),full_page=False)
        wasm_files=list((root/'apps/client/dist/assets').glob('*.wasm'))
        assert len(wasm_files)==1,'The client must contain one versioned emulator asset'
        wasm=wasm_files[0].read_bytes()
        old_hash=hashlib.sha256(rom).hexdigest()
        assert old_hash in fingerprint()
        assert hashlib.sha256(wasm).hexdigest() in fingerprint()
        assert 'private-title' not in page.locator('body').inner_text()
        page.get_by_role('button',name='Pause',exact=True).click()
        page.wait_for_timeout(100)
        paused_frame=canvas.get_attribute('data-frame-count')

        # Invalid candidates never displace the previously loaded worker.
        select(b'not a ROM')
        page.locator('.rc-status').get_by_text('not an NES',exact=False).wait_for()
        assert old_hash in fingerprint()
        broken=bytearray(rom);broken[6]=240;broken[7]=240
        select(broken)
        page.locator('.rc-status').get_by_text('Unable to load:',exact=False).wait_for()
        assert old_hash in fingerprint()
        assert canvas.get_attribute('data-frame-count')==paused_frame
        page.get_by_label('NES cartridge file').set_input_files([])
        assert old_hash in fingerprint()

        # Holding the digest makes cancellation and a competing selection deterministic.
        page.evaluate('''() => {
          const digest=crypto.subtle.digest.bind(crypto.subtle);
          window.holdNextDigest=true;
          crypto.subtle.digest=async(...arguments)=>{
            const result=await digest(...arguments);
            if(holdNextDigest){holdNextDigest=false;
              await new Promise(resolve=>window.releaseDigest=resolve);}
            return result;
          };
        }''')
        select()
        page.wait_for_function("typeof releaseDigest==='function'")
        page.locator('.rc-status').get_by_role('button',name='Cancel selection').click()
        page.evaluate('releaseDigest()')
        page.locator('.rc-status').get_by_text('Selection cancelled.',exact=False).wait_for()
        assert old_hash in fingerprint()
        assert canvas.get_attribute('data-frame-count')==paused_frame
        assert page.get_by_role('button',name='Resume',exact=True).is_visible()

        page.evaluate('window.holdNextDigest=true;window.releaseDigest=undefined')
        select()
        page.wait_for_function("typeof releaseDigest==='function'")
        newer=bytearray(rom)
        newer.extend(b'header differences and trailing bytes are significant')
        select(newer,'second-private.nes')
        start_solo(page,newer)
        newest_hash=hashlib.sha256(newer).hexdigest()
        assert newest_hash in fingerprint()
        page.evaluate('releaseDigest()')
        page.wait_for_timeout(100)
        assert newest_hash in fingerprint()

        # The same admission path accepts supported mapper and NES 2.0 variants.
        for mapper in [1,2,3,4,7]:
            variant=bytearray(rom)
            variant[4]=2
            variant[16+16384:16+16384]=rom[16:16+16384]
            variant[6]=mapper<<4
            fresh_variant(variant,f'mapper-{mapper}.nes')
        large=bytearray(rom);large[7]=8
        large.extend(bytes(9*1024*1024-len(large)))
        fresh_variant(large,'large-nes2.nes')

        page.get_by_role('button',name='Pause',exact=True).click()
        page.wait_for_timeout(100)
        frozen=canvas.evaluate('node=>node.toDataURL()')
        page.wait_for_timeout(200)
        assert frozen==canvas.evaluate('node=>node.toDataURL()')
        audio=page.evaluate('proof')
        assert audio['muted'] and audio['peak']>0 and audio['starts']>3
        page.set_viewport_size({'width':390,'height':700})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth && document.scrollingElement.scrollHeight<=innerHeight+1')
        page.screenshot(path=str(output.with_suffix('.mobile.png')),full_page=False)

        # A browser audio refusal must not stop the game or hide recovery.
        audio_page=browser.new_page()
        audio_page.add_init_script('''const resume=AudioContext.prototype.resume;
          window.denySound=true;
          AudioContext.prototype.resume=function(){return denySound?Promise.reject(Error('denied')):resume.call(this)};''')
        audio_page.goto(url)
        enter_create(audio_page)
        audio_page.get_by_label('NES cartridge file').set_input_files({
            'name':'audio-check.nes','mimeType':'application/octet-stream','buffer':rom})
        start_solo(audio_page,rom)
        audio_page.wait_for_function("Number(document.querySelector('canvas').dataset.frameCount)>10")
        audio_page.locator('.rc-game-links').get_by_role('button',name='Settings').click()
        audio_page.locator('.rc-side-content:visible').get_by_role('button',name='Controls').click()
        sound=audio_page.locator('.rc-settings')
        sound.get_by_role('button',name='Sound',exact=True).click()
        sound.get_by_role('button',name='Retry game audio').wait_for()
        audio_page.evaluate('denySound=false')
        sound.get_by_role('button',name='Retry game audio').click()
        sound.get_by_role('button',name='Retry game audio').wait_for(state='detached')
        audio_page.close()

        disconnected=verify_disconnected_load(browser,url,rom)
        settings=verify_settings(browser,url,rom,output)
        assert not errors,errors
        assert all(method=='GET' and request_url.startswith(url) for method,request_url in requests),requests
        assert not any(name in request_url for _,request_url in requests
                       for name in ['private','mapper-','large-nes2']),requests
        worker_path='/assets/'+next((root/'apps/client/dist/assets').glob('worker-*.js')).name
        battery=verify_battery(browser,url,rom,worker_path)
        assert battery['coreSha256']==hashlib.sha256(wasm).hexdigest()
        state=verify_state(browser,url,rom,worker_path)
        saves=verify_saves(browser,url,rom,output)
        rewind_worker=verify_rewind_worker(browser,url,rom,worker_path)
        rewind_ui=verify_rewind_ui(browser,url,rom,output)
        persistence=verify_persistence(browser,url,rom,worker_path,output)
        result={'result':'pass','browser':browser.version,
                'duration_seconds':round(time.monotonic()-started,2),
                'audio':audio,'disconnected_startup':disconnected,'settings':settings,
                'battery':battery,'state':state,'saves':saves,
                'rewind_worker':rewind_worker,'rewind_ui':rewind_ui,
                'persistence':persistence,'keyboard_picker_and_local_play':True,
                'input_changed_canvas':True,'paused_canvas_stable':True,
                'invalid_file_preserved_previous':True,
                'cancelled_replacement_preserved_previous':True,
                'latest_selection_wins':True,'exact_rom_and_core_sha256':True,
                'unknown_mappers_loaded':[0,1,2,3,4,7],
                'nes2_over_8mib_loaded':True,
                'audio_denial_does_not_block_and_retry_recovers':True,
                'mobile_no_overflow':True,'page_errors':errors,'requests':requests,
                'coordinator_url':url}
        output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
        browser.close()
