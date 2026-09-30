#!/usr/bin/env python3
"""Exercise the public-room to protected-room journey with fixed task regions."""
import argparse
import json
import os
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
from layout_geometry import GeometryRecorder, browser_zoom, control_visibility, verify_zoom, zoom_context

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(os.environ.get('RETRO_COOP_STATIC_ROOT', ROOT / 'apps/client/dist'))


def profile(page, url, output, label, *, navigate=True, trace=False):
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    if navigate:
        page.goto(url)
    page.get_by_test_id('directory').wait_for()
    page.wait_for_function("document.querySelector('[data-directory-status]')?.dataset.directoryStatus==='live'")
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
    proof = {'label': label, 'viewport': page.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio})'),
             'states': [], 'captures': [], 'page_errors': errors}
    directory = GeometryRecorder(page, 'directory-query', '.directory-panel [data-layout-region]') if trace else None
    if directory:
        directory.mark('live')
    search = page.get_by_role('searchbox', name='Search room, game, host, or code')
    search.fill('no matching game for this probe')
    page.get_by_text('No matching public rooms.', exact=True).wait_for()
    if directory:
        directory.mark('empty result')
    page.get_by_role('button', name='Clear search').click()
    if directory:
        directory.mark('cleared')
        proof['directory_geometry'] = directory.finish(output / f'{label}-directory-layout.json',
            required=('directory-heading','directory-search','directory-feedback','directory-list','directory-actions'))
    proof['states'].extend(('public rooms', 'empty search', 'search recovery'))
    page.get_by_role('button', name='Create game', exact=True).click()
    page.get_by_role('heading', name='Choose a game').wait_for()
    assert page.get_by_role('button', name='Create room', exact=True).is_disabled()
    create = GeometryRecorder(page, 'create-game', '.create-game [data-layout-region]') if trace else None
    if create:
        create.mark('choose game')
    if not label.startswith(('zoom-', 'effective-')):
        path = output / f'{label}-choose-game.png'
        page.screenshot(path=str(path), full_page=True)
        proof['captures'].append(path.name)
    page.locator('input[type=file]').set_input_files({'name':'invalid.nes','mimeType':'application/octet-stream','buffer':b'invalid'})
    page.wait_for_function("()=>!!document.querySelector('.create-feedback')?.textContent?.trim()")
    assert page.get_by_role('button', name='Create room', exact=True).is_disabled()
    if create:
        create.mark('invalid file')
    if label in ('wide', 'narrow'):
        path = output / f'{label}-invalid-file.png'
        page.screenshot(path=str(path), full_page=True)
        proof['captures'].append(path.name)
    proof['states'].append('invalid file feedback')
    page.locator('input[type=file]').set_input_files(STATIC / 'generated/diagnostic.nes')
    page.get_by_text('diagnostic.nes is loaded and ready.', exact=True).wait_for()
    if create:
        create.mark('validated file')
    page.get_by_label('Room access', exact=True).select_option('protected')
    page.get_by_label('Room password', exact=True).wait_for()
    assert page.get_by_role('button', name='Create room', exact=True).is_disabled()
    if create:
        create.mark('password required')
    page.get_by_label('Room password', exact=True).fill('protected room password')
    page.get_by_role('button', name='Create room', exact=True).wait_for(state='visible')
    page.wait_for_function("()=>!document.querySelector('.create-actions button')?.disabled")
    if create:
        create.mark('ready to create')
        proof['create_geometry'] = create.finish(output / f'{label}-create-layout.json',
            required=('create-heading','library-feedback','library-list','create-option-fields','create-feedback','create-actions','create-primary'))
    action = page.get_by_role('button', name='Create room', exact=True)
    action.scroll_into_view_if_needed()
    proof['create_action_visibility'] = control_visibility(action)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
    if not label.startswith(('zoom-', 'effective-')):
        path = output / f'{label}-protected-ready.png'
        page.screenshot(path=str(path), full_page=True)
        proof['captures'].append(path.name)
    proof['states'].extend(('validated file', 'password required', 'protected room ready'))
    action.click()
    page.get_by_role('button', name='Start game', exact=True).wait_for(timeout=30000)
    page.get_by_test_id('room-view').wait_for()
    proof['states'].append('waiting room')
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
                    results.append(profile(context.new_page(),url,args.output,label,trace=label=='wide'))
                finally:
                    context.close()
            browser.close()
            for label, size in [('zoom-200',(1280,800)),('effective-320',(640,800))]:
                if args.only and label != args.only:
                    continue
                with zoom_context(playwright,{'width':size[0],'height':size[1]}) as (context,worker):
                    page = context.new_page()
                    page.goto(url)
                    zoom = browser_zoom(page,worker,2)
                    row = profile(page,url,args.output,label,navigate=False)
                    row['zoom'] = zoom
                    row['zoom_verified'] = verify_zoom(worker,zoom)
                    results.append(row)
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
