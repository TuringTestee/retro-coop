"""Exercise local file admission, transactional replacement, real input/audio and privacy."""
import argparse
import functools
import hashlib
import http.server
import json
import threading
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from battery_smoke import verify_battery
from settings_smoke import verify_settings, verify_disconnected_load

parser = argparse.ArgumentParser()
parser.add_argument('--output', default='foundation.local.json')
parser.add_argument('--chrome', action='store_true')
args = parser.parse_args()
started = time.monotonic()
root = Path(__file__).resolve().parents[2]
output = Path(args.output)
rom = (root / 'apps/client/dist/generated/diagnostic.nes').read_bytes()
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root / 'apps/client/dist'))
with http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler) as server:
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with sync_playwright() as p:
        browser = p.chromium.launch(ignore_default_args=['--mute-audio'], **({'channel': 'chrome'} if args.chrome else {}))
        page = browser.new_page(viewport={'width': 1280, 'height': 1000})
        errors, requests = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: requests.append((request.method, request.url)))
        page.add_init_script('''window.proof={buffers:0,peak:0,starts:0,muted:true};
        const copy=AudioBuffer.prototype.copyToChannel;
        AudioBuffer.prototype.copyToChannel=function(data,...rest){proof.buffers++;for(const x of data)proof.peak=Math.max(proof.peak,Math.abs(x));return copy.call(this,data,...rest)};
        const connect=AudioNode.prototype.connect;
        AudioNode.prototype.connect=function(node,...rest){if(node instanceof GainNode)proof.muted=proof.muted && node.gain.value===0;return connect.call(this,node,...rest)};
        const start=AudioBufferSourceNode.prototype.start;
        AudioBufferSourceNode.prototype.start=function(...args){proof.starts++;return start.apply(this,args)};
        ''')
        page.goto(f'http://127.0.0.1:{server.server_port}/')
        page.screenshot(path=str(output.with_suffix('.before.png')), full_page=True)
        def select(data=rom, name='unknown-private-title.nes'):
            page.set_input_files('input[type=file]', {'name':name,'mimeType':'application/octet-stream','buffer':bytes(data)})
        def running():
            page.wait_for_function("document.querySelector('[data-testid=player-status]').textContent.startsWith('Playing locally')")
            page.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>10")
        def fingerprint():
            return page.locator('[data-testid=fingerprint]').inner_text()
        # A single keyboard-accessible picker action goes directly to playable frames.
        page.get_by_role('button',name='Choose NES file',exact=True).focus()
        with page.expect_file_chooser() as chooser:
            page.keyboard.press('Enter')
        chooser.value.set_files({'name':'unknown-private-title.nes','mimeType':'application/octet-stream','buffer':rom})
        running()
        page.wait_for_function('proof.starts>3 && proof.peak>0')
        page.locator('canvas').focus()
        before = page.locator('canvas').evaluate('c=>c.toDataURL()')
        page.keyboard.down('ArrowRight')
        page.wait_for_function("before=>document.querySelector('canvas').toDataURL()!==before", arg=before)
        page.keyboard.up('ArrowRight')
        page.screenshot(path=str(output.with_suffix('.after.png')), full_page=True)
        page.locator('.panel summary').click()
        assert hashlib.sha256(rom).hexdigest() in fingerprint()
        wasm = (root / 'apps/client/dist/generated/retro_coop_d02.wasm').read_bytes()
        assert hashlib.sha256(wasm).hexdigest() in fingerprint()
        assert 'unknown-private-title' not in page.locator('body').inner_text()
        neutral_title = page.locator('#player-title').inner_text()
        # Invalid file and invalid hardware leave the valid cartridge and its progress intact.
        old_hash = hashlib.sha256(rom).hexdigest()
        select(b'not a ROM')
        page.wait_for_function("document.querySelector('[data-testid=player-status]').textContent.includes('not an NES')")
        assert old_hash in fingerprint()
        broken = bytearray(rom); broken[6] = 240; broken[7] = 240
        select(broken)
        page.wait_for_function("document.querySelector('[data-testid=player-status]').textContent.startsWith('Unable to load:')")
        assert old_hash in fingerprint() and page.locator('#player-title').inner_text() == neutral_title
        assert page.get_by_role('button',name='Pause',exact=True).is_enabled()
        # Chooser dismissal is a no-op, rather than a reload or loss of progress.
        page.set_input_files('input[type=file]', [])
        assert old_hash in fingerprint()
        # Hold candidate WASM: Cancel and window-blur both permanently revoke pending intent.
        for cancel in ['button','blur']:
            held = []
            page.route('**/retro_coop_d02.wasm', lambda route: held.append(route))
            select()
            page.wait_for_function("document.querySelector('[data-testid=player-status]').textContent.startsWith('Starting your game')")
            page.wait_for_timeout(100)
            assert len(held) == 1
            if cancel == 'button':
                page.get_by_role('button',name='Cancel loading').click()
            else:
                page.evaluate("dispatchEvent(new Event('blur'))")
            held[0].continue_()
            page.unroute('**/retro_coop_d02.wasm')
            page.wait_for_timeout(100)
            assert old_hash in fingerprint()
            assert page.get_by_role('button',name='Cancel loading').count() == 0
        assert page.get_by_role('button',name='Resume',exact=True).is_enabled()
        # Later selection wins even when an earlier digest completes afterward.
        page.evaluate('''() => {
          const digest=crypto.subtle.digest.bind(crypto.subtle); let first=true;
          crypto.subtle.digest=async (...args)=>{
            const result=await digest(...args);
            if(first){first=false;await new Promise(resolve=>window.releaseDigest=resolve);}
            return result;
          };
        }''')
        select()
        page.wait_for_function('typeof releaseDigest === "function"')
        newer = bytearray(rom); newer.extend(b'header differences and trailing bytes are significant')
        select(newer,'second-private.nes'); running()
        newest_hash = hashlib.sha256(newer).hexdigest()
        assert newest_hash in fingerprint()
        page.evaluate('releaseDigest()')
        page.wait_for_timeout(100)
        assert newest_hash in fingerprint()
        # Supported non-NROM admission uses the same original diagnostic program in mirrored banks.
        for mapper in [1,2,3,4,7]:
            variant = bytearray(rom)
            variant[4] = 2
            variant[16+16384:16+16384] = rom[16:16+16384]
            variant[6] = mapper << 4
            select(variant,f'unknown-mapper-{mapper}.nes'); running()
            assert hashlib.sha256(variant).hexdigest() in fingerprint()
        # NES 2.0 and a >8 MiB file are not silently excluded by the application.
        large = bytearray(rom); large[7] = 8; large.extend(bytes(9*1024*1024-len(large)))
        select(large); running()
        assert hashlib.sha256(large).hexdigest() in fingerprint()
        # Drag/drop is also a one-action local start.
        transfer = page.evaluate_handle('''bytes=>{const dt=new DataTransfer();dt.items.add(new File([new Uint8Array(bytes)],'drag-private.nes'));return dt}''',list(rom))
        page.locator('.panel').dispatch_event('drop',{'dataTransfer':transfer}); running()
        assert old_hash in fingerprint()
        page.get_by_role('button', name='Pause', exact=True).click()
        page.wait_for_timeout(100) # Allow the already requested committed frame to arrive.
        frozen = page.locator('canvas').evaluate('c=>c.toDataURL()')
        page.wait_for_timeout(200)
        assert frozen == page.locator('canvas').evaluate('c=>c.toDataURL()')
        proof = page.evaluate('proof')
        assert proof['muted'] and proof['peak'] > 0 and proof['starts'] > 3
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(output.with_suffix('.mobile.png')),full_page=True)
        # Audio permission failure is visible and never blocks frames; an explicit retry recovers.
        audio_page = browser.new_page()
        audio_page.add_init_script('''const resume=AudioContext.prototype.resume; window.denySound=true;
          AudioContext.prototype.resume=function(){return denySound ? Promise.reject(new Error('denied')) : resume.call(this)};''')
        audio_page.goto(f'http://127.0.0.1:{server.server_port}/')
        audio_page.set_input_files('input[type=file]', {'name':'audio-check.nes','mimeType':'application/octet-stream','buffer':rom})
        audio_page.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>10")
        assert audio_page.get_by_role('button',name='Retry sound').is_visible()
        audio_page.evaluate('denySound=false')
        audio_page.get_by_role('button',name='Retry sound').click()
        audio_page.get_by_role('button',name='Retry sound').wait_for(state='detached')
        audio_page.close()
        disconnected_proof = verify_disconnected_load(browser,f'http://127.0.0.1:{server.server_port}/',rom)
        settings_proof = verify_settings(browser,f'http://127.0.0.1:{server.server_port}/',rom,output)
        assert not errors, errors
        assert all(method == 'GET' and url.startswith(f'http://127.0.0.1:{server.server_port}/') for method,url in requests), requests
        assert not any(name in url for _,url in requests for name in ['private','unknown','drag-'])
        worker_path='/assets/'+next((root/'apps/client/dist/assets').glob('worker-*.js')).name
        battery=verify_battery(browser,f'http://127.0.0.1:{server.server_port}/',rom,worker_path)
        assert battery['coreSha256']==hashlib.sha256(wasm).hexdigest()
        result = {'battery':battery,'result':'pass','settings':settings_proof,'disconnected_startup':disconnected_proof,'browser':browser.version,'duration_seconds':round(time.monotonic()-started,2),'audio':proof,'audio_denial_does_not_block_and_retry_recovers':True,'input_changed_canvas':True,'paused_canvas_stable':True,'cancel_and_blur_preserve_previous':True,'latest_selection_wins':True,'invalid_header_and_mapper_preserve_previous':True,'chooser_dismissal_preserved':True,'exact_rom_and_core_sha256':True,'unknown_mappers_loaded':[0,1,2,3,4,7],'nes2_over_8mib_loaded':True,'picker_and_drop_start_automatically':True,'mobile_no_overflow':True,'page_errors':errors,'requests':requests,'coordinator_url':page.locator('main').get_attribute('data-coordinator')}
        output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
        browser.close()
    server.shutdown()
