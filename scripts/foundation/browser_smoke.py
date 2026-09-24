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
from local_play import read_fingerprint


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
rom = (root / 'apps/client/dist/generated/diagnostic.nes').read_bytes()
with room_test_server(root) as url:
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
        # Keep the keyboard picker observable even when CI cannot deliver its chooser event.
        page.add_init_script('''window.pickerProof={events:[]};
        const describe=node=>node ? {tag:node.tagName,label:node.getAttribute?.('aria-label') || (node.tagName==='BUTTON' ? node.textContent : null)} : null;
        const record=event=>{if(pickerProof.events.length>=64)return;const entry={type:event.type,key:event.key,prevented:event.defaultPrevented,target:describe(event.target),active:describe(document.activeElement),activation:navigator.userActivation.isActive,time:performance.now()};pickerProof.events.push(entry);setTimeout(()=>{entry.prevented=event.defaultPrevented;},0);};
        const types=['focusin','focusout','keydown','keyup','click'];
        for(const type of types)document.addEventListener(type,record,true);
        window.finishPickerProof=()=>{for(const type of types)document.removeEventListener(type,record,true);return {...pickerProof,active:describe(document.activeElement),focused:document.hasFocus(),activation:navigator.userActivation.isActive};};
        ''')
        page.goto(url)
        page.screenshot(path=str(output.with_suffix('.before.png')), full_page=True)
        page.get_by_role('button', name='Create game', exact=True).click()
        def select(data=rom, name='unknown-private-title.nes'):
            page.set_input_files('input[type=file]', {'name':name,'mimeType':'application/octet-stream','buffer':bytes(data)})
        def running():
            if page.get_by_role('button', name='Play locally', exact=True).is_visible():
                page.get_by_role('button', name='Play locally', exact=True).click()
            page.get_by_role('button', name='Resume', exact=True).click()
            page.wait_for_function("document.querySelector('[data-testid=player-status]').textContent.startsWith('Playing locally')")
            page.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>10")
        def run_fresh_variant(data, name):
            variant_page = browser.new_page()
            try:
                variant_page.goto(url)
                variant_page.get_by_role('button', name='Create game', exact=True).click()
                variant_page.set_input_files('input[type=file]', {'name':name,'mimeType':'application/octet-stream','buffer':bytes(data)})
                variant_page.get_by_role('button', name='Play locally', exact=True).click()
                variant_page.get_by_role('button', name='Resume', exact=True).click()
                variant_page.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>10")
                assert hashlib.sha256(data).hexdigest() in read_fingerprint(variant_page)
            finally:
                variant_page.close()
        def fingerprint():
            return read_fingerprint(page)
        # The keyboard picker loads a game on Create Game, then Play locally starts frames.
        picker_result = {'browser':browser.version,'channel':'chrome' if args.chrome else 'default-headless-shell','protocolEvents':[]}
        # Python's listener subscription is sent without awaiting its protocol reply.
        # Confirm native-dialog interception before the one user action; keep testing
        # Enter -> real file chooser -> chosen file, never a direct-selection fallback.
        picker_protocol = page.context.new_cdp_session(page)
        picker_protocol.on('Page.fileChooserOpened', lambda event: picker_result['protocolEvents'].append(event))
        picker_protocol.send('Page.enable', {'enableFileChooserOpenedEvent':True})
        try:
            page.get_by_role('button',name='Add NES file',exact=True).focus()
            with page.expect_file_chooser() as chooser:
                picker_protocol.send('Page.setInterceptFileChooserDialog', {'enabled':True})
                picker_result['interceptionAcknowledged'] = True
                page.keyboard.press('Enter')
            picker_result['outcome'] = 'chooser received'
        except Exception as error:
            picker_result['outcome'] = str(error)
            try:
                page.screenshot(path=str(output.with_suffix('.failure.png')), full_page=True)
            except Exception as screenshot_error:
                picker_result['screenshotError'] = str(screenshot_error)
            raise
        finally:
            picker_result['pageErrors'] = list(errors)
            try:
                picker_result['events'] = page.evaluate('finishPickerProof()')
            except Exception as diagnostic_error:
                picker_result['diagnosticError'] = str(diagnostic_error)
            output.with_name('picker-'+output.name).write_text(json.dumps(picker_result,indent=2)+'\n')
            picker_protocol.detach()
        chooser.value.set_files({'name':'unknown-private-title.nes','mimeType':'application/octet-stream','buffer':rom})
        running()
        page.wait_for_function('proof.starts>3 && proof.peak>0')
        page.locator('canvas').focus()
        before = page.locator('canvas').evaluate('c=>c.toDataURL()')
        page.keyboard.down('ArrowRight')
        page.wait_for_function("before=>document.querySelector('canvas').toDataURL()!==before", arg=before)
        page.keyboard.up('ArrowRight')
        page.screenshot(path=str(output.with_suffix('.after.png')), full_page=True)
        assert hashlib.sha256(rom).hexdigest() in fingerprint()
        wasm_files = list((root / 'apps/client/dist/assets').glob('*.wasm'))
        assert len(wasm_files) == 1, 'The client must contain one versioned emulator asset'
        wasm = wasm_files[0].read_bytes()
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
            page.route('**/*.wasm', lambda route: held.append(route))
            select()
            page.wait_for_function("document.querySelector('[data-testid=player-status]').textContent.startsWith('Starting your game')")
            page.wait_for_timeout(100)
            assert len(held) == 1
            if cancel == 'button':
                page.get_by_role('button',name='Cancel loading').click()
            else:
                page.evaluate("dispatchEvent(new Event('blur'))")
            held[0].continue_()
            page.unroute('**/*.wasm')
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
            run_fresh_variant(variant,f'unknown-mapper-{mapper}.nes')
        # NES 2.0 and a >8 MiB file are not silently excluded by the application.
        large = bytearray(rom); large[7] = 8; large.extend(bytes(9*1024*1024-len(large)))
        run_fresh_variant(large,'large-nes2.nes')
        # Drag/drop replaces the local cartridge and still needs explicit Resume.
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
        audio_page.goto(url)
        audio_page.get_by_role('button', name='Create game', exact=True).click()
        audio_page.set_input_files('input[type=file]', {'name':'audio-check.nes','mimeType':'application/octet-stream','buffer':rom})
        audio_page.get_by_role('button', name='Play locally', exact=True).click()
        audio_page.get_by_role('button', name='Resume', exact=True).click()
        audio_page.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>10")
        assert audio_page.get_by_role('button',name='Retry sound').is_visible()
        audio_page.evaluate('denySound=false')
        audio_page.get_by_role('button',name='Retry sound').click()
        audio_page.get_by_role('button',name='Retry sound').wait_for(state='detached')
        audio_page.close()
        disconnected_proof = verify_disconnected_load(browser,url,rom)
        settings_proof = verify_settings(browser,url,rom,output)
        assert not errors, errors
        assert all(method == 'GET' and request_url.startswith(url) for method,request_url in requests), requests
        assert not any(name in url for _,url in requests for name in ['private','unknown','drag-'])
        worker_path='/assets/'+next((root/'apps/client/dist/assets').glob('worker-*.js')).name
        battery=verify_battery(browser,url,rom,worker_path)
        assert battery['coreSha256']==hashlib.sha256(wasm).hexdigest()
        state=verify_state(browser,url,rom,worker_path)
        saves=verify_saves(browser,url,rom,output)
        rewind_worker=verify_rewind_worker(browser,url,rom,worker_path)
        rewind_ui=verify_rewind_ui(browser,url,rom,output)
        persistence=verify_persistence(browser,url,rom,worker_path,output)
        result = {'rewind_worker':rewind_worker,'rewind_ui':rewind_ui,'persistence':persistence,'saves':saves,'state':state,'battery':battery,'result':'pass','settings':settings_proof,'disconnected_startup':disconnected_proof,'browser':browser.version,'duration_seconds':round(time.monotonic()-started,2),'audio':proof,'audio_denial_does_not_block_and_retry_recovers':True,'input_changed_canvas':True,'paused_canvas_stable':True,'cancel_and_blur_preserve_previous':True,'latest_selection_wins':True,'invalid_header_and_mapper_preserve_previous':True,'chooser_dismissal_preserved':True,'exact_rom_and_core_sha256':True,'unknown_mappers_loaded':[0,1,2,3,4,7],'nes2_over_8mib_loaded':True,'picker_and_drop_enter_local_play':True,'mobile_no_overflow':True,'page_errors':errors,'requests':requests,'coordinator_url':page.locator('main').get_attribute('data-coordinator')}
        output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
        browser.close()
