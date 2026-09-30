#!/usr/bin/env python3
"""Measure local-player controls through a held replacement load and recovery."""
import argparse
import json
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright
from layout_geometry import GeometryRecorder, browser_zoom, control_visibility, zoom_context

ROOT = Path(__file__).resolve().parents[2]
ROM = ROOT / 'apps/client/dist/generated/diagnostic.nes'
REGIONS = '.screen, [data-layout-region=player-primary-actions], [data-layout-region=player-task-actions], [data-layout-region=player-feedback]'


def check(page, url, output, label, zoom_worker=None):
    page.add_init_script(path=ROOT / 'scripts/foundation/gamepad_fixture.js')
    page.goto(url)
    zoom = browser_zoom(page, zoom_worker) if zoom_worker else None
    page.get_by_role('button', name='Create game', exact=True).click()
    page.locator('input[type=file]').set_input_files(ROM)
    page.get_by_role('button', name='Play locally', exact=True).click()
    page.get_by_role('button', name='Resume', exact=True).click()
    page.wait_for_function("Number(document.querySelector('canvas').dataset.frameCount)>10")
    assert page.get_by_role('button', name='Pause', exact=True).is_visible()
    header = page.locator('main > header').bounding_box()
    panel = page.locator('main > .panel').bounding_box()
    assert header and panel and header['y']+header['height'] <= panel['y'], (header, panel)
    layout = GeometryRecorder(page, label, REGIONS)
    layout.mark('playing')
    page.screenshot(path=str(output / f'{label}-playing.png'), full_page=False)

    page.evaluate('window.originalRead=FileReader.prototype.readAsArrayBuffer;FileReader.prototype.readAsArrayBuffer=function(){}')
    changed = ROM.read_bytes() + b'new game candidate'
    layout.allow_user_scroll()
    page.locator('input[type=file]').set_input_files({'name':'replacement.nes','mimeType':'application/octet-stream','buffer':changed})
    cancel = page.get_by_role('button', name='Cancel loading', exact=True)
    cancel.wait_for(state='visible')
    page.get_by_role('button', name='Settings', exact=True).focus()
    for _ in range(4):
        page.keyboard.press('Tab')
        if cancel.evaluate('node=>document.activeElement===node'):
            break
    assert cancel.evaluate('node=>document.activeElement===node'), 'Tab did not reach Cancel loading'
    page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
    control_visibility(cancel, require_focus=True)
    assert cancel.evaluate("node=>node.matches(':focus-visible') && parseFloat(getComputedStyle(node).outlineWidth)>=3")
    layout.allow_user_scroll(False)
    layout.mark('loading')
    page.screenshot(path=str(output / f'{label}-loading.png'), full_page=False)
    layout.allow_user_scroll()
    page.keyboard.press('Enter')
    page.evaluate('()=>{FileReader.prototype.readAsArrayBuffer=window.originalRead}')
    page.get_by_role('button', name='Pause', exact=True).wait_for(state='visible')
    layout.allow_user_scroll(False)
    layout.mark('cancelled')
    page.locator('input[type=file]').set_input_files({'name':'invalid.nes','mimeType':'application/octet-stream','buffer':b'invalid'})
    page.wait_for_function("document.querySelector('[data-testid=player-status]')?.textContent?.includes('NES')")
    assert page.get_by_role('button', name='Pause', exact=True).is_visible()
    feedback = page.locator('[data-layout-region=player-feedback]')
    assert feedback.locator('[data-testid=player-status]').evaluate('node=>getComputedStyle(node).fontSize') == '16px'
    size=feedback.evaluate('node=>({scrollHeight:node.scrollHeight,clientHeight:node.clientHeight,text:node.innerText})')
    assert size['scrollHeight']<=size['clientHeight']+1, 'Current error needs hidden scrolling'
    control_visibility(feedback.locator('[data-testid=player-status]'))
    layout.mark('invalid-file')
    page.screenshot(path=str(output / f'{label}-recovery.png'), full_page=False)
    result = layout.finish(output / f'{label}-geometry.json', required=('player-primary-actions','player-task-actions','player-feedback'))
    pause = page.get_by_role('button', name='Pause', exact=True)
    pause.focus()
    page.keyboard.press('Tab')
    unmute = page.get_by_role('button', name='Unmute', exact=True)
    control_visibility(unmute, require_focus=True)
    assert unmute.evaluate("node=>node.matches(':focus-visible') && parseFloat(getComputedStyle(node).outlineWidth)>=3")
    page.keyboard.press('Tab')
    next_action = page.get_by_role('button', name='Tools', exact=True)
    control_visibility(next_action, require_focus=True)
    assert next_action.evaluate("node=>node.matches(':focus-visible') && parseFloat(getComputedStyle(node).outlineWidth)>=3")
    page.screenshot(path=str(output / f'{label}-keyboard-next.png'), full_page=False)
    page.keyboard.press('Shift+Tab')
    control_visibility(unmute, require_focus=True)
    page.keyboard.press('Shift+Tab')
    control_visibility(pause, require_focus=True)
    assert pause.evaluate("node=>node.matches(':focus-visible') && parseFloat(getComputedStyle(node).outlineWidth)>=3")
    page.keyboard.press('Tab')
    page.keyboard.press('Tab')
    tools = page.get_by_role('button', name='Tools', exact=True)
    control_visibility(tools, require_focus=True)
    page.keyboard.press('Enter')
    back = page.get_by_role('button', name='Back', exact=True)
    page.wait_for_function("document.activeElement?.textContent?.trim()==='Back'")
    control_visibility(back, require_focus=True)
    assert back.evaluate("node=>node.matches(':focus-visible') && parseFloat(getComputedStyle(node).outlineWidth)>=3")
    page.screenshot(path=str(output / f'{label}-tools.png'), full_page=False)
    page.keyboard.press('Tab')
    saves = page.get_by_role('button', name='Saves', exact=True)
    control_visibility(saves, require_focus=True)
    assert saves.evaluate("node=>node.matches(':focus-visible') && parseFloat(getComputedStyle(node).outlineWidth)>=3")
    page.screenshot(path=str(output / f'{label}-keyboard-saves.png'), full_page=False)
    page.keyboard.press('Shift+Tab')
    control_visibility(back, require_focus=True)
    for name in ('Saves','Rewind','Game help','Fullscreen'):
        action = page.get_by_role('button', name=name, exact=True)
        action.focus()
        page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        control_visibility(action, require_focus=True)
    page.evaluate('()=>{window.originalFullscreenRequest=Element.prototype.requestFullscreen;Element.prototype.requestFullscreen=()=>Promise.reject(Error("Denied"))}')
    page.keyboard.press('Enter')
    denied = page.get_by_test_id('fullscreen-issue')
    page.wait_for_function("document.activeElement?.dataset.testid==='fullscreen-issue'")
    control_visibility(denied, require_focus=True)
    assert denied.evaluate("node=>getComputedStyle(node).boxShadow.includes('inset')")
    page.screenshot(path=str(output / f'{label}-fullscreen-denied.png'), full_page=False)
    page.keyboard.press('Shift+Tab')
    if not page.get_by_role('button', name='Tools', exact=True).evaluate('node=>document.activeElement===node'):
        page.keyboard.press('Shift+Tab')
    control_visibility(page.get_by_role('button', name='Tools', exact=True), require_focus=True)
    page.evaluate('()=>{Element.prototype.requestFullscreen=window.originalFullscreenRequest}')
    page.get_by_role('button', name='Settings', exact=True).click()
    page.get_by_label('Input device', exact=True).select_option('0')
    page.get_by_role('button', name='Back', exact=True).click()
    page.get_by_role('button', name='Tools', exact=True).click()
    page.get_by_role('button', name='Back', exact=True).focus()
    page.evaluate('padConnected=false')
    keyboard = page.get_by_role('button', name='Use keyboard', exact=True)
    page.wait_for_function("document.activeElement?.textContent?.trim()==='Use keyboard'")
    control_visibility(keyboard, require_focus=True)
    assert keyboard.evaluate("node=>getComputedStyle(node).boxShadow.includes('inset')")
    page.screenshot(path=str(output / f'{label}-controller-recovery.png'), full_page=False)
    keyboard.click()
    page.get_by_role('button', name='Tools', exact=True).wait_for(state='visible')
    return {'geometry':result,'zoom':zoom}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    service = subprocess.Popen(['node','scripts/rooms/browser-server.ts'], cwd=ROOT, stdout=subprocess.PIPE, text=True)
    try:
        url = json.loads(service.stdout.readline())['url']
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                results = [check(browser.new_page(viewport=viewport), url, args.output, label)
                           for label,viewport in [('short',{'width':1024,'height':600}),('narrow',{'width':390,'height':700})]]
            finally:
                browser.close()
            with zoom_context(playwright, {'width':640,'height':800}) as (context, worker):
                results.append(check(context.new_page(), url, args.output, 'zoom-200', worker))
        print(json.dumps({'result':'pass','profiles':results}))
    finally:
        service.terminate()
        service.wait(timeout=10)


if __name__ == '__main__':
    main()
