#!/usr/bin/env python3
"""Exercise the public-room to protected-room journey with fixed task regions."""
import argparse
import base64
import json
import os
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
from layout_geometry import GeometryRecorder, browser_zoom, control_visibility, verify_zoom, zoom_context

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(os.environ.get('RETRO_COOP_STATIC_ROOT', ROOT / 'apps/client/dist'))


def capture(page, path, label):
    if label.startswith(('zoom-', 'effective-')):
        session = page.context.new_cdp_session(page)
        try:
            shot = session.send('Page.captureScreenshot',
                                {'format': 'png', 'fromSurface': False, 'captureBeyondViewport': False})
            path.write_bytes(base64.b64decode(shot['data']))
        finally:
            session.detach()
    else:
        page.screenshot(path=str(path))


def public_room(browser, url):
    host = browser.new_page(viewport={'width': 1440, 'height': 900})
    host.goto(url)
    host.get_by_role('button', name='Create game', exact=True).click()
    host.locator('input[type=file]').set_input_files(STATIC / 'generated/diagnostic.nes')
    host.get_by_text('diagnostic.nes is loaded and ready.', exact=True).wait_for()
    host.get_by_role('button', name='Create room', exact=True).click()
    host.get_by_role('button', name='Start game', exact=True).wait_for(timeout=30000)
    return host


def profile(page, browser, url, output, label, *, navigate=True):
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    if navigate:
        page.goto(url)
    page.get_by_test_id('directory').wait_for()
    page.wait_for_function("document.querySelector('[data-directory-status]')?.dataset.directoryStatus==='live'")
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
    proof = {'label': label, 'viewport': page.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio})'),
             'states': [], 'captures': [], 'page_errors': errors}
    directory = GeometryRecorder(page, 'directory-query', '.directory-panel [data-layout-region]')
    directory.mark('live')
    if label in ('wide', 'compact'):
        path = output / f'{label}-public-rooms.png'
        capture(page, path, label)
        proof['captures'].append(path.name)
    host = public_room(browser, url)
    host_name = host.get_by_test_id('guest').inner_text().strip()
    search = page.get_by_role('searchbox', name='Search room, game, host, or code')
    search.fill(host_name)
    page.locator('.room-list li').filter(has_text=host_name).wait_for()
    directory.mark('room added')
    if label in ('wide', 'narrow', 'short'):
        path = output / f'{label}-populated-rooms.png'
        capture(page, path, label)
        proof['captures'].append(path.name)
    search.fill('no matching game for this probe')
    page.get_by_text('No matching public rooms.', exact=True).wait_for()
    directory.mark('empty result')
    if label == 'wide':
        path = output / f'{label}-empty-search.png'
        capture(page, path, label)
        proof['captures'].append(path.name)
    page.get_by_role('button', name='Clear search').click()
    page.get_by_text('No matching public rooms.', exact=True).wait_for(state='hidden')
    directory.mark('cleared')
    search.fill(host_name)
    page.locator('.room-list li').filter(has_text=host_name).wait_for()
    host.get_by_role('button', name='Leave room', exact=True).click()
    host.get_by_role('button', name='Confirm leave', exact=True).click()
    page.get_by_text('No matching public rooms.', exact=True).wait_for()
    directory.mark('room removed')
    page.get_by_role('button', name='Clear search').click()
    host.close()
    proof['directory_geometry'] = directory.finish(output / f'{label}-directory-layout.json',
        required=('directory-heading','directory-search','directory-feedback','directory-list','directory-actions'))
    proof['states'].extend(('public rooms', 'room added', 'empty search', 'search recovery', 'room removed'))
    page.get_by_role('button', name='Create game', exact=True).click()
    page.get_by_role('heading', name='Choose a game').wait_for()
    assert page.get_by_role('button', name='Create room', exact=True).is_disabled()
    create = GeometryRecorder(page, 'create-game', '.create-game [data-layout-region]')
    create.mark('choose game')
    if not label.startswith(('zoom-', 'effective-')):
        path = output / f'{label}-choose-game.png'
        capture(page, path, label)
        proof['captures'].append(path.name)
    create.allow_user_scroll(True)
    page.locator('input[type=file]').set_input_files({'name':'invalid.nes','mimeType':'application/octet-stream','buffer':b'invalid'})
    page.wait_for_function("()=>!!document.querySelector('.create-feedback')?.textContent?.trim()")
    assert page.get_by_role('button', name='Create room', exact=True).is_disabled()
    create.mark('invalid file')
    if label in ('wide', 'narrow'):
        path = output / f'{label}-invalid-file.png'
        capture(page, path, label)
        proof['captures'].append(path.name)
    proof['states'].append('invalid file feedback')
    page.locator('input[type=file]').set_input_files(STATIC / 'generated/diagnostic.nes')
    page.get_by_text('diagnostic.nes is loaded and ready.', exact=True).wait_for()
    create.allow_user_scroll(False)
    create.mark('validated file')
    create.allow_user_scroll(True)
    page.get_by_label('Room access', exact=True).select_option('protected')
    page.get_by_label('Room password', exact=True).wait_for()
    assert page.get_by_role('button', name='Create room', exact=True).is_disabled()
    create.mark('password required')
    password = page.get_by_label('Room password', exact=True)
    page.get_by_label('Room access', exact=True).focus()
    page.keyboard.press('Tab')
    assert password.evaluate('node=>node===document.activeElement')
    page.keyboard.type('protected room password')
    control_visibility(password, require_focus=True)
    show = page.get_by_role('button', name='Show', exact=True)
    page.keyboard.press('Tab')
    control_visibility(show, require_focus=True)
    page.keyboard.press('Enter')
    hide = page.get_by_role('button', name='Hide', exact=True)
    control_visibility(hide, require_focus=True)
    page.keyboard.press('Enter')
    action = page.get_by_role('button', name='Create room', exact=True)
    for _ in range(4):
        page.keyboard.press('Tab')
        if action.evaluate('node=>node===document.activeElement'):
            break
    assert action.evaluate('node=>node===document.activeElement'), 'Create room was not reachable by Tab'
    proof['keyboard_create_visibility'] = control_visibility(action, require_focus=True)
    create.allow_user_scroll(False)
    action.wait_for(state='visible')
    page.wait_for_function("()=>!document.querySelector('.create-actions button')?.disabled")
    create.mark('ready to create')
    proof['create_action_visibility'] = control_visibility(action)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
    path = output / f'{label}-protected-ready.png'
    capture(page, path, label)
    proof['captures'].append(path.name)
    proof['states'].extend(('validated file', 'password required', 'protected room ready'))
    held = []
    def hold_upload(route):
        held.append(route)
        page.evaluate('window.__uploadHeld=true')
    page.route('**/rooms/*/rom', hold_upload)
    action.click()
    page.wait_for_function('()=>!!document.querySelector(".create-actions button")?.disabled')
    page.wait_for_function('()=>!!document.querySelector(".create-actions button:last-child")?.textContent?.includes("Cancel")')
    page.wait_for_function('window.__uploadHeld===true')
    assert held, 'Upload request did not reach the real network boundary'
    create.mark('upload busy')
    cancel = page.get_by_role('button', name='Cancel', exact=True)
    proof['cancel_visibility'] = control_visibility(cancel)
    if label in ('wide', 'short', 'narrow', 'zoom-200', 'effective-320'):
        path = output / f'{label}-upload-busy.png'
        capture(page, path, label)
        proof['captures'].append(path.name)
    cancel.click()
    held.pop().abort('failed')
    page.unroute('**/rooms/*/rom', hold_upload)
    page.wait_for_function("()=>!document.querySelector('.create-actions button')?.disabled")
    create.mark('upload cancelled')
    failed = []
    def fail_once(route):
        failed.append(route.request.url)
        route.abort('failed')
    page.route('**/rooms/*/rom', fail_once)
    action.click()
    page.get_by_text('Upload connection failed', exact=False).wait_for(timeout=15000)
    create.mark('upload failed')
    assert failed
    if label in ('wide', 'short', 'narrow', 'zoom-200', 'effective-320'):
        path = output / f'{label}-upload-failed.png'
        capture(page, path, label)
        proof['captures'].append(path.name)
    page.unroute('**/rooms/*/rom', fail_once)
    proof['create_geometry'] = create.finish(output / f'{label}-create-layout.json',
        required=('create-heading','library-feedback','library-list','create-option-fields','create-feedback','create-actions','create-primary'))
    action.click()
    page.get_by_role('button', name='Start game', exact=True).wait_for(timeout=30000)
    page.get_by_test_id('room-view').wait_for()
    proof['states'].extend(('upload busy', 'upload cancelled', 'upload failed', 'retry succeeded', 'waiting room'))
    assert not errors, errors
    return proof


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--only', help='Run one profile while investigating a failure')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    service = subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=ROOT,
                               env=os.environ.copy(),stdout=subprocess.PIPE,text=True)
    try:
        url = json.loads(service.stdout.readline())['url']
        results = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            for label, size in [('wide',(1440,900)),('short',(1024,600)),('narrow',(390,700)),('compact',(320,400))]:
                if args.only and label != args.only:
                    continue
                context = browser.new_context(viewport={'width':size[0],'height':size[1]})
                try:
                    results.append(profile(context.new_page(),browser,url,args.output,label))
                finally:
                    context.close()
            for label, size in [('zoom-200',(1280,800)),('effective-320',(640,800))]:
                if args.only and label != args.only:
                    continue
                with zoom_context(playwright,{'width':size[0],'height':size[1]}) as (context,worker):
                    page = context.new_page()
                    page.goto(url)
                    zoom = browser_zoom(page,worker,2)
                    row = profile(page,browser,url,args.output,label,navigate=False)
                    row['zoom'] = zoom
                    row['zoom_verified'] = verify_zoom(worker,zoom)
                    results.append(row)
            browser.close()
        result = {'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  'result':'pass','profiles':results}
        (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'head':result['head'],'result':'pass','profiles':[
            {'label':row['label'],'viewport':row['viewport'],'states':row['states'],
             'directory_geometry':row.get('directory_geometry'), 'create_geometry':row.get('create_geometry')}
            for row in results]}))
    finally:
        service.terminate()
        service.wait(timeout=5)


if __name__ == '__main__':
    main()
