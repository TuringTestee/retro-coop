#!/usr/bin/env python3
"""Exercise the five secondary tasks at short, narrow, and actual zoom profiles."""
import argparse
import json
import os
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
from layout_geometry import browser_zoom, control_visibility, verify_zoom, zoom_context

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(os.environ.get('RETRO_COOP_STATIC_ROOT', ROOT / 'apps/client/dist'))


def visible_focus(page, locator):
    if not locator.is_enabled():
        page.wait_for_function('node=>!node.disabled', arg=locator.element_handle())
    locator.focus()
    page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
    control_visibility(locator, require_focus=True)


def confirmation_visible(page):
    bounds = page.evaluate("""()=>{const node=document.querySelector('.tool-content'),parent=node.getBoundingClientRect(),text=document.querySelector('.tool-confirmation p').getBoundingClientRect(),regionNode=document.querySelector('.tool-confirmation'),region=regionNode.getBoundingClientRect();return {parent:{top:parent.top,bottom:parent.bottom,scrollTop:node.scrollTop,scrollHeight:node.scrollHeight,clientHeight:node.clientHeight},text:{top:text.top,bottom:text.bottom},region:{top:region.top,bottom:region.bottom,scrollTop:regionNode.scrollTop,scrollHeight:regionNode.scrollHeight,clientHeight:regionNode.clientHeight},buttons:[...regionNode.querySelectorAll('button')].map(b=>({text:b.textContent,top:b.getBoundingClientRect().top,bottom:b.getBoundingClientRect().bottom,left:b.getBoundingClientRect().left,right:b.getBoundingClientRect().right,margin:getComputedStyle(b).scrollMarginBlockStart}))}}""")
    assert bounds['text']['top'] >= bounds['parent']['top'] - 1, bounds
    assert bounds['text']['bottom'] <= bounds['parent']['bottom'] + 1, bounds


def check_page(page, name, result):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (name, 'horizontal page overflow')
    assert page.get_by_role('button', name='Back', exact=True).is_visible(), (name, 'Back unavailable')
    region = page.locator('.tool-page .tool-content')
    metrics = region.evaluate('node=>({height:node.clientHeight,scroll:node.scrollHeight,tab:node.tabIndex})')
    if metrics['scroll'] > metrics['height'] + 1:
        page.wait_for_function("()=>document.querySelector('.tool-page .tool-content')?.tabIndex===0")
        region.focus()
        page.wait_for_function("()=>document.activeElement===document.querySelector('.tool-page .tool-content')")
        settle = """()=>new Promise(resolve=>{let prior=-1,still=0;const tick=()=>{const top=document.querySelector('.tool-page .tool-content').scrollTop;still=top===prior?still+1:0;prior=top;if(still>=3)resolve();else requestAnimationFrame(tick);};tick();})"""
        steps = int(metrics['scroll'] / max(metrics['height'], 1)) + 2
        for key, endpoint in [('End', 'bottom'), ('Home', 'top')]:
            for _ in range(steps):
                before = region.evaluate('node=>node.scrollTop')
                page.keyboard.press(key)
                page.evaluate(settle)
                state = region.evaluate('node=>({top:node.scrollTop,max:node.scrollHeight-node.clientHeight})')
                reached = state['top'] >= state['max'] - 2 if endpoint == 'bottom' else state['top'] <= 1
                if reached:
                    break
                assert abs(state['top'] - before) > 1, (result['label'], name, key, state)
            else:
                raise AssertionError((result['label'], name, key, 'keyboard did not reach scroll endpoint', state))
        result['keyboard_scroll_endpoints'].append(name)
    result['pages'].append(name)


def journey(page, url, output, label, navigate=True):
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    if navigate:
        page.goto(url)
    receipt = {'label': label, 'css_viewport': page.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio})'),
               'pages': [], 'keyboard_scroll_endpoints': [], 'captures': [], 'page_errors': errors}
    page.get_by_role('button', name='Settings', exact=True).click()
    page.get_by_role('heading', name='Local settings').wait_for()
    page.wait_for_function("document.activeElement?.id === 'settings-title'")
    visible_focus(page, page.get_by_role('button', name='Restore keyboard defaults'))
    page.get_by_role('button', name='Restore keyboard defaults').click()
    visible_focus(page, page.get_by_role('button', name='Keep mappings'))
    confirmation_visible(page)
    check_page(page, 'Settings confirmation', receipt)
    if label in ('short', 'narrow', 'zoom-200', 'effective-320'):
        visible_focus(page, page.get_by_role('button', name='Keep mappings'))
        path = output / f'{label}-settings-confirmation.png'
        page.screenshot(path=str(path));receipt['captures'].append(path.name)
    page.keyboard.press('Escape')
    page.get_by_role('button', name='Local data', exact=True).click()
    page.get_by_role('heading', name='Local data').wait_for()
    page.wait_for_function("document.activeElement?.id === 'local-data-title'")
    visible_focus(page, page.get_by_role('button', name='Delete all local data'))
    page.get_by_role('button', name='Delete all local data').click()
    visible_focus(page, page.get_by_role('button', name='Cancel', exact=True))
    confirmation_visible(page)
    check_page(page, 'Local data confirmation', receipt)
    if label in ('narrow', 'zoom-200', 'effective-320'):
        visible_focus(page, page.get_by_role('button', name='Cancel', exact=True))
        confirmation_visible(page)
        path = output / f'{label}-local-data-confirmation.png'
        page.screenshot(path=str(path));receipt['captures'].append(path.name)
    page.keyboard.press('Escape')
    page.get_by_role('button', name='Back', exact=True).click()
    page.get_by_role('button', name='Back', exact=True).click()
    page.get_by_role('button', name='Create game', exact=True).click()
    page.locator('input[type=file]').set_input_files(STATIC / 'generated/diagnostic.nes')
    page.get_by_role('button', name='Play locally', exact=True).click()
    page.get_by_role('button', name='Resume', exact=True).click()
    page.locator('.panel').get_by_role('button', name='Saves', exact=True).click()
    page.get_by_role('heading', name='Saves on this device').wait_for()
    page.wait_for_function("document.activeElement?.id === 'saves-title'")
    page.get_by_role('button', name='Save current point', exact=True).click()
    page.get_by_text('Saved in Slot 1 on this device.', exact=True).wait_for()
    visible_focus(page, page.get_by_role('button', name='Export current save', exact=True))
    visible_focus(page, page.get_by_role('button', name='Delete Slot 1', exact=True))
    page.get_by_role('button', name='Delete Slot 1', exact=True).click()
    visible_focus(page, page.get_by_role('button', name='Cancel', exact=True))
    confirmation_visible(page)
    check_page(page, 'Saves confirmation and feedback', receipt)
    if label in ('short', 'narrow', 'effective-320'):
        visible_focus(page, page.get_by_role('button', name='Cancel', exact=True))
        path = output / f'{label}-saves-confirmation.png'
        page.screenshot(path=str(path));receipt['captures'].append(path.name)
    page.keyboard.press('Escape')
    page.get_by_role('button', name='Back', exact=True).click()
    page.locator('.panel').get_by_role('button', name='Rewind', exact=True).click()
    page.get_by_role('heading', name='Rewind local game').wait_for()
    page.wait_for_function("document.activeElement?.id === 'rewind-title'")
    page.get_by_test_id('rewind-history').wait_for(state='visible')
    action = page.get_by_role('button', name='Rewind 1 second', exact=True)
    page.locator('.rewind .tool-content').evaluate('node=>node.scrollTop=node.scrollHeight')
    page.locator('.rewind [data-layout-region="tool-actions"]').evaluate('node=>node.scrollTop=node.scrollHeight')
    control_visibility(action)
    check_page(page, 'Rewind history or recovery', receipt)
    if label in ('short', 'zoom-200'):
        page.locator('.rewind .tool-content').evaluate('node=>node.scrollTop=node.scrollHeight')
        page.locator('.rewind [data-layout-region="tool-actions"]').evaluate('node=>node.scrollTop=node.scrollHeight')
        path = output / f'{label}-rewind.png'
        page.screenshot(path=str(path));receipt['captures'].append(path.name)
    page.get_by_role('button', name='Back', exact=True).click()
    page.locator('.panel').get_by_role('button', name='Game help', exact=True).click()
    page.get_by_role('heading', name='Game help', exact=True).wait_for()
    page.wait_for_function("document.activeElement?.id === 'game-help-title'")
    details = page.get_by_text('Technical details', exact=True)
    visible_focus(page, details)
    details.click()
    page.get_by_test_id('fingerprint').wait_for(state='visible')
    check_page(page, 'Help expanded details', receipt)
    if label in ('zoom-200', 'effective-320'):
        page.locator('.tool-page .tool-content').evaluate('node=>node.scrollTop=node.scrollHeight')
        path = output / f'{label}-help-expanded.png'
        page.screenshot(path=str(path));receipt['captures'].append(path.name)
    page.get_by_role('button', name='Back', exact=True).click()
    assert not errors, errors
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--only', help='Run one named viewport while diagnosing a focused failure')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                               env=os.environ.copy(), stdout=subprocess.PIPE, text=True)
    try:
        url = json.loads(service.stdout.readline())['url']
        results = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            for label, viewport in [('wide', (1440,900)), ('reported-short', (1366,682)),
                                    ('short', (1024,600)), ('narrow', (390,700)), ('width-320', (320,700))]:
                if args.only and label != args.only:
                    continue
                context = browser.new_context(viewport={'width': viewport[0], 'height': viewport[1]})
                try:
                    results.append(journey(context.new_page(), url, args.output, label))
                finally:
                    context.close()
            browser.close()
            for label, viewport in [('zoom-200', (1280,800)), ('effective-320', (640,800))]:
                if args.only and label != args.only:
                    continue
                with zoom_context(playwright, {'width': viewport[0], 'height': viewport[1]}) as (context, worker):
                    page = context.new_page()
                    page.goto(url)
                    zoom = browser_zoom(page, worker, 2)
                    row = journey(page, url, args.output, label, navigate=False)
                    row['zoom'] = zoom
                    row['zoom_verified'] = verify_zoom(worker, zoom)
                    results.append(row)
        data = {'head': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
                'result': 'pass', 'profiles': results}
        (args.output / 'result.json').write_text(json.dumps(data, indent=2)+'\n')
        print(json.dumps({'result':'pass','head':data['head'],'profiles':[
            {'label':r['label'],'css_viewport':r['css_viewport'],'pages':r['pages'],
             'keyboard_scroll_endpoints':r['keyboard_scroll_endpoints'],'captures':r['captures']}
            for r in results]}))
    finally:
        service.terminate();service.wait(timeout=5)


if __name__ == '__main__':
    main()
