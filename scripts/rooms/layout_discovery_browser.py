#!/usr/bin/env python3
"""Real coordinator/client L1 geometry through delayed reads and recovery.

Network and browser APIs are held or failed at their real boundaries. No DOM or
application state is fabricated. The room transition itself begins a new page.
"""
import argparse
import contextlib
import json
import os
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from layout_geometry import GeometryRecorder, INSTALL, artifact_provenance, control_visibility, keyboard_access, zoom_context, browser_zoom, verify_zoom

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(os.environ.get('RETRO_COOP_STATIC_ROOT', ROOT / 'apps/client/dist'))


def included_preview(browser, url, output):
    page = browser.new_page(viewport={'width': 1024, 'height': 600})
    page.goto(url)
    page.get_by_role('button', name='Create game', exact=True).click()
    selected = page.locator('.create-library li').filter(has_text='Super Tilt Bro').get_by_role('button')
    downloads = []
    def hold(route):
        downloads.append(route)
        page.evaluate('window.geometryDownloadCount=(window.geometryDownloadCount||0)+1')
    page.route('**/catalog/super-tilt-bro*.nes', hold)
    record = GeometryRecorder(page, 'included-download-error-retry')
    record.allow_user_scroll()
    selected.click()
    record.allow_user_scroll(False)
    page.wait_for_function('window.geometryDownloadCount===1')
    record.mark('included-request-held')
    page.screenshot(path=str(output / 'included-loading.png'))
    downloads.pop().abort('failed')
    page.get_by_role('button', name='Add NES file', exact=True).wait_for()
    page.wait_for_function("!document.querySelector('.create-library li button')?.disabled")
    record.mark('included-download-failed')
    page.screenshot(path=str(output / 'included-error.png'))
    record.allow_user_scroll()
    selected.click()
    record.allow_user_scroll(False)
    page.wait_for_function('window.geometryDownloadCount===2')
    downloads.pop().continue_()
    page.wait_for_function("!document.querySelector('.create-actions button')?.disabled")
    record.mark('included-ready')
    result = [record.finish(output / 'included-download.json')]
    page.unroute('**/catalog/super-tilt-bro*.nes')
    page.get_by_role('button', name='Play locally', exact=True).click()
    page.get_by_role('button', name='Resume', exact=True).click()
    page.wait_for_function("Number(document.querySelector('[data-testid=frames]')?.textContent?.match(/\\d+/)?.[0]||0)>=180", timeout=30000)
    page.wait_for_function('''async()=>{const db=await new Promise(r=>{const q=indexedDB.open('retro-coop-local',3);q.onsuccess=()=>r(q.result)});const rows=await new Promise(r=>{const q=db.transaction('roms').objectStore('roms').getAll();q.onsuccess=()=>r(q.result)});db.close();return rows.some(row=>row.label==='Super Tilt Bro'&&row.preview)}''', timeout=30000)
    page.get_by_role('button', name='Public rooms', exact=True).click()
    page.evaluate('''()=>{const decode=HTMLImageElement.prototype.decode;window.restoreDecode=()=>{HTMLImageElement.prototype.decode=decode};
      HTMLImageElement.prototype.decode=function(){if(this.src.startsWith('data:image/'))return new Promise((resolve,reject)=>{window.releasePreview=()=>decode.call(this).then(resolve,reject)});return decode.call(this)};}''')
    record = GeometryRecorder(page, 'preview-delayed-decode', selector='.create-game [data-layout-region]')
    page.get_by_role('button', name='Create game', exact=True).click()
    page.wait_for_function('!!window.releasePreview')
    page.get_by_text('No preview yet.', exact=True).wait_for()
    record.mark('preview-decode-held')
    page.screenshot(path=str(output / 'preview-held.png'))
    page.evaluate('releasePreview()')
    page.wait_for_function("document.querySelector('.create-preview img')?.naturalWidth===128")
    record.mark('preview-decoded')
    page.screenshot(path=str(output / 'preview-ready.png'))
    result.append(record.finish(output / 'preview-decode.json'))
    page.evaluate('()=>{restoreDecode();}')
    page.get_by_role('button', name='Back to rooms', exact=True).click()
    page.evaluate('''()=>{const decode=HTMLImageElement.prototype.decode;window.restoreDecode=()=>{HTMLImageElement.prototype.decode=decode};HTMLImageElement.prototype.decode=function(){return this.src.startsWith('data:image/')?Promise.reject(Error('Injected image decode failure')):decode.call(this)};}''')
    record = GeometryRecorder(page, 'preview-decode-fallback', selector='.create-game [data-layout-region]')
    page.get_by_role('button', name='Create game', exact=True).click()
    page.get_by_text('No preview yet.', exact=True).wait_for()
    page.locator('.create-library li').filter(has_text='Super Tilt Bro').get_by_role('button').click()
    page.wait_for_function("!document.querySelector('.create-actions button')?.disabled")
    assert page.locator('.create-preview img').count() == 0
    record.mark('fallback-with-usable-selection')
    page.screenshot(path=str(output / 'preview-fallback.png'))
    result.append(record.finish(output / 'preview-fallback.json'))
    page.evaluate('()=>{restoreDecode();}')
    page.close()
    return result


def directory_and_release(browser, host, url, output):
    viewer = browser.new_page(viewport={'width': 1366, 'height': 682})
    viewer.goto(url)
    viewer.locator('.directory-title [role=status]').filter(has_text='Live').wait_for()
    record = GeometryRecorder(viewer, 'directory-metadata-pages-and-capacity')
    settings = host.locator('details.session-settings')
    settings.locator(':scope > summary').click()
    settings.get_by_text('Session settings', exact=True).click()
    long_name = 'A deliberately long room name for geometry and readable wrapping'
    settings.get_by_label('Room name', exact=True).fill(long_name)
    settings.get_by_role('button', name='Save room name', exact=True).click()
    host.get_by_role('heading', name=long_name, exact=False).wait_for()
    record.allow_user_scroll()
    viewer.get_by_role('searchbox').fill(long_name)
    record.allow_user_scroll(False)
    viewer.get_by_text(long_name, exact=True).wait_for()
    nickname_before = host.get_by_test_id('guest').bounding_box()
    host.get_by_text('Nickname settings', exact=True).click()
    long_nickname = 'Host with a very long nickname!!'
    assert len(long_nickname) == 32
    host.get_by_label('Nickname', exact=True).fill(long_nickname)
    host.get_by_role('button', name='Save nickname', exact=True).click()
    viewer.get_by_text(long_nickname, exact=True).wait_for()
    host.get_by_test_id('guest').filter(has_text=long_nickname).wait_for()
    (output / 'nickname-header.json').write_text(json.dumps({'before': nickname_before, 'after': host.get_by_test_id('guest').bounding_box()}, indent=2))
    record.mark('long-name-and-host-live')
    viewer.screenshot(path=str(output / 'directory-long-name.png'))
    invite = host.get_by_label('Room invitation', exact=True).input_value()
    visitor = browser.new_page(viewport={'width': 390, 'height': 700})
    visitor.goto(invite)
    visitor.get_by_role('button', name='Join room', exact=True).wait_for()
    invitation = GeometryRecorder(visitor, 'invitation-closed-reopen')
    for slot in range(2, 6):
        host.locator(f'[data-slot-id=slot-{slot}]').get_by_role('button', name='Close slot', exact=True).click()
    viewer.get_by_text('No open slots', exact=False).wait_for()
    assert viewer.get_by_role('button', name='Join', exact=True).count() == 0
    visitor.wait_for_function("!Array.from(document.querySelectorAll('button')).some(n=>n.textContent==='Join room'&&!n.disabled)")
    record.mark('slots-closed')
    invitation.mark('all-slots-closed')
    visitor.screenshot(path=str(output / 'invitation-closed.png'))
    host.locator('[data-slot-id=slot-2]').get_by_role('button', name='Open slot', exact=True).click()
    viewer.get_by_role('button', name='Join', exact=True).wait_for()
    visitor.get_by_role('button', name='Join room', exact=True).wait_for()
    invitation.mark('slot-reopened')
    result = [invitation.finish(output / 'invitation-capacity.json')]
    record.allow_user_scroll()
    viewer.get_by_role('searchbox').fill('')
    record.allow_user_scroll(False)
    viewer.get_by_text('Page 1 of 2', exact=True).wait_for()
    record.mark('pagination-visible')
    record.allow_user_scroll()
    viewer.get_by_role('button', name='Next', exact=True).click()
    viewer.wait_for_function("document.activeElement?.hasAttribute('data-room-id')")
    record.allow_user_scroll(False)
    record.mark('next-page')
    result.append(record.finish(output / 'directory-capacity.json'))
    visitor.get_by_role('button', name='Join room', exact=True).click()
    visitor.get_by_role('button', name='Prepare to play', exact=True).wait_for(timeout=30000)
    release = GeometryRecorder(visitor, 'host-closed-release', selector='.release-notice')
    host.get_by_role('button', name='Leave room', exact=True).click()
    host.get_by_role('button', name='Confirm leave', exact=True).click()
    visitor.locator('.release-notice').wait_for()
    visitor.wait_for_function("document.activeElement?.closest('.release-notice')")
    release.mark('host-closed')
    control_visibility(visitor.locator('.release-notice button'), require_focus=True)
    visitor.screenshot(path=str(output / 'release-notice.png'))
    result.append(release.finish(output / 'release.json'))
    visitor.locator('.release-notice button').click()
    visitor.locator('.release-notice').wait_for(state='detached')
    visitor.close()
    viewer.close()
    return result


def invitation_release_keyboard(playwright, browser, url, output):
    results = []
    for backing in (None, 1280, 640):
        host = browser.new_page(viewport={'width': 1440, 'height': 900})
        host.goto(url)
        host.get_by_role('button', name='Create game', exact=True).click()
        host.set_input_files('input[type=file]', STATIC / 'generated/diagnostic.nes')
        host.get_by_role('button', name='Create room', exact=True).click()
        host.get_by_role('button', name='Start game', exact=True).wait_for(timeout=30000)
        invite = host.get_by_label('Room invitation', exact=True).input_value()
        with contextlib.ExitStack() as stack:
            if backing:
                context, worker = stack.enter_context(zoom_context(playwright, {'width': backing, 'height': 720}))
                visitor = context.pages[0]
                profiles = [(f'zoom-{backing}', None)]
            else:
                visitor = browser.new_page(viewport={'width': 1440, 'height': 900})
                stack.callback(visitor.close)
                profiles = [(f'{width}x{height}', {'width': width, 'height': height})
                            for width, height in ((1440, 900), (1366, 682), (1024, 600), (390, 700))]
            visitor.goto(invite)
            visitor.get_by_role('button', name='Join room', exact=True).wait_for()
            zoom = browser_zoom(visitor, worker) if backing else None
            for label, viewport in profiles:
                if viewport: visitor.set_viewport_size(viewport)
                results.append(keyboard_access(visitor, f'{label}-invitation', output / f'{label}-invitation-keyboard.json'))
            visitor.get_by_role('button', name='Join room', exact=True).click()
            visitor.get_by_role('button', name='Prepare to play', exact=True).wait_for(timeout=30000)
            visitor.wait_for_function("!Array.from(document.querySelectorAll('button')).find(n=>n.textContent==='Prepare to play')?.disabled", timeout=30000)
            host.get_by_role('button', name='Leave room', exact=True).click()
            host.get_by_role('button', name='Confirm leave', exact=True).click()
            visitor.locator('.release-notice').wait_for()
            for label, viewport in profiles:
                if viewport: visitor.set_viewport_size(viewport)
                results.append(keyboard_access(visitor, f'{label}-release', output / f'{label}-release-keyboard.json'))
                visitor.screenshot(path=str(output / f'{label}-release.png'))
            if zoom: verify_zoom(worker, zoom)
            visitor.locator('.release-notice button').click()
            visitor.locator('.release-notice').wait_for(state='detached')
        host.close()
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    provenance = artifact_provenance(ROOT, STATIC)
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
        env={**os.environ, 'COORDINATOR_EMPTY_OFFERS': 'super-tilt-bro-pal,from-below-1.0'}, stdout=subprocess.PIPE, text=True)
    results = []
    try:
        url = json.loads(service.stdout.readline())['url']
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            held = []
            gate = {'hold': True, 'messages': []}
            def socket_route(socket):
                held.append(socket)
                server = socket.connect_to_server()
                def message(raw):
                    if gate['hold']: gate['messages'].append((socket, raw))
                    else: socket.send(raw)
                server.on_message(message)
            page.route_web_socket('**/ws', socket_route)
            page.add_init_script('window.layoutSockets=[];const OriginalSocket=WebSocket;window.WebSocket=class extends OriginalSocket{constructor(...args){super(...args);layoutSockets.push(this)}}')
            page.add_init_script(f'({INSTALL})({json.dumps({"selector": "[data-layout-region]", "label": "directory-initial-loading"})})')
            page.goto(url)
            page.get_by_test_id('directory').wait_for()
            page.wait_for_function('layoutSockets.length>0')
            assert held
            record = GeometryRecorder.__new__(GeometryRecorder)
            record.page = page
            record.mark('socket-held-loading')
            page.screenshot(path=str(args.output / 'directory-loading.png'))
            gate['hold'] = False
            for socket, raw in gate['messages']: socket.send(raw)
            page.locator('.directory-title [role=status]').filter(has_text='Live').wait_for()
            record.mark('live')
            results.append(record.finish(args.output / 'directory-loading.json'))
            record = GeometryRecorder(page, 'directory-stale-retry')
            page.evaluate('layoutSockets.forEach(socket=>socket.close())')
            page.get_by_role('button', name='Retry', exact=True).wait_for()
            record.mark('stale')
            page.screenshot(path=str(args.output / 'directory-stale.png'))
            record.allow_user_scroll()
            page.get_by_role('button', name='Retry', exact=True).click()
            record.allow_user_scroll(False)
            page.wait_for_function('layoutSockets.length===2')
            assert len(held) == 2
            assert not gate['hold']
            page.locator('.directory-title [role=status]').filter(has_text='Live').wait_for()
            record.mark('retry-live')
            results.append(record.finish(args.output / 'directory-retry.json'))
            page.get_by_role('button', name='Create game', exact=True).click()
            page.get_by_test_id('create-game').wait_for()
            # Hold actual File.arrayBuffer during checking; then hold the native
            # module request during loading. Release only after visible milestones.
            page.evaluate('''()=>{const read=File.prototype.arrayBuffer;window.releaseFile=null;
              File.prototype.arrayBuffer=function(){if(this.name==='geometry.nes'){File.prototype.arrayBuffer=read;return new Promise(resolve=>{window.releaseFile=()=>resolve(read.call(this));});}return read.call(this)};}''')
            native = []
            page.route('**/*.wasm', lambda route: native.append(route))
            record = GeometryRecorder(page, 'create-check-load-storage-recovery')
            page.set_input_files('input[type=file]', {'name': 'geometry.nes', 'mimeType': 'application/octet-stream', 'buffer': (STATIC / 'generated/diagnostic.nes').read_bytes()})
            page.get_by_text('Checking the NES file…', exact=True).wait_for()
            page.wait_for_function('!!window.releaseFile')
            record.mark('checking-held')
            page.screenshot(path=str(args.output / 'create-checking.png'))
            with page.expect_request('**/*.wasm'):
                page.evaluate('releaseFile()')
            page.get_by_text('Loading geometry.nes…', exact=True).wait_for()
            record.mark('loading-held')
            page.screenshot(path=str(args.output / 'create-loading.png'))
            page.wait_for_function("document.querySelector('.create-actions button')?.disabled")
            # Browser worker fetches may not be routable on every Chromium build;
            # the visible loading state above is still required and sampled.
            assert native, 'native request was not intercepted; loading delay is unproven'
            page.evaluate('''()=>{const put=IDBObjectStore.prototype.put;window.restorePut=()=>IDBObjectStore.prototype.put=put;
              IDBObjectStore.prototype.put=function(...args){if(this.name==='roms')throw new DOMException('Geometry storage quota injection','QuotaExceededError');return put.apply(this,args)};}''')
            for route in native: route.continue_()
            page.unroute('**/*.wasm')
            page.get_by_text('Available in this tab only. Browser storage did not save the game.', exact=True).wait_for()
            record.mark('storage-warning-loaded')
            page.screenshot(path=str(args.output / 'create-storage-warning.png'))
            page.evaluate('()=>{restorePut();}')
            results.append(record.finish(args.output / 'create-loading.json'))
            # Upload cancellation and retry use the same real host-upload route as
            # host_upload_browser.py. Holding the request preserves the busy UI.
            uploads = []
            def hold_upload(route):
                uploads.append(route)
                page.evaluate('window.geometryUploadCount=(window.geometryUploadCount||0)+1')
            page.route('**/rooms/*/rom', hold_upload)
            record = GeometryRecorder(page, 'create-upload-cancel-error-retry')
            record.allow_user_scroll()
            page.get_by_role('button', name='Create room', exact=True).click()
            record.allow_user_scroll(False)
            page.get_by_role('button', name='Cancel', exact=True).wait_for()
            page.wait_for_function("document.querySelector('.create-actions button')?.disabled")
            page.wait_for_function('window.geometryUploadCount===1')
            assert uploads
            record.mark('upload-held')
            page.screenshot(path=str(args.output / 'create-upload.png'))
            record.allow_user_scroll()
            page.get_by_role('button', name='Cancel', exact=True).click()
            record.allow_user_scroll(False)
            uploads.pop().abort()
            page.wait_for_function("!document.querySelector('.create-actions button')?.disabled")
            record.mark('cancelled')
            record.allow_user_scroll()
            page.get_by_role('button', name='Create room', exact=True).click()
            record.allow_user_scroll(False)
            page.get_by_role('button', name='Cancel', exact=True).wait_for()
            page.wait_for_function('window.geometryUploadCount===2')
            assert uploads
            uploads.pop().abort('failed')
            page.get_by_text('Upload connection failed', exact=False).wait_for()
            record.mark('upload-error')
            page.screenshot(path=str(args.output / 'create-upload-error.png'))
            results.append(record.finish(args.output / 'create-upload.json'))
            page.unroute('**/rooms/*/rom')
            page.get_by_role('button', name='Create room', exact=True).click()
            page.get_by_role('button', name='Start game', exact=True).wait_for(timeout=30000)
            page.screenshot(path=str(args.output / 'retry-room.png'))
            unexpected_errors = [error for error in errors if error != 'Geometry storage quota injection']
            assert not unexpected_errors, unexpected_errors
            results.extend(directory_and_release(browser, page, url, args.output))
            results.extend(included_preview(browser, url, args.output))
            keyboard = invitation_release_keyboard(p, browser, url, args.output)
            assert provenance['artifacts'] == artifact_provenance(ROOT, STATIC)['artifacts'], 'Build changed during proof'
            result = {'result': 'pass', 'provenance': provenance, 'browser': browser.version, 'geometry': results, 'keyboard': keyboard,
                      'upload_retry_reaches_room': True, 'injected_storage_errors': errors.count('Geometry storage quota injection'), 'elapsed_seconds': time.monotonic() - started,
                      'unverified': []}
            (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result))
            browser.close()
    finally:
        service.terminate()
        try: service.wait(timeout=5)
        except subprocess.TimeoutExpired: service.kill(); service.wait()


if __name__ == '__main__':
    main()
