#!/usr/bin/env python3
"""Exercise the current lobby shell with a real coordinator and built client."""

import argparse
import json
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright
from layout_geometry import browser_zoom, zoom_context

ROOT = Path(__file__).resolve().parents[2]


def choose_section(page, name):
    selector = page.get_by_role('combobox', name='Settings section')
    if selector.is_visible():
        selector.select_option(label=name)
    else:
        page.get_by_role('button', name=name, exact=True).click()


def settings_controls_fit(page):
    return page.locator('.rc-tool-body').evaluate("""body => {
      const edge = body.closest('.rc-mobile-side-panel,.rc-side-panel,.rc-play-tools').getBoundingClientRect().bottom;
      return [...body.querySelectorAll('button,input,select')].filter(node => getComputedStyle(node).display !== 'none')
        .every(node => node.getBoundingClientRect().bottom <= edge + 1);
    }""")


def guide_fits(page):
    return page.locator('.rc-inline-settings').evaluate("""panel => {
      const edge = panel.getBoundingClientRect();
      const rows = [...panel.querySelectorAll('.rc-control-line,.rc-shortcuts')];
      return rows.length === 7 && rows.every(row => {
        const rect = row.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && rect.left >= edge.left - 1 && rect.right <= edge.right + 1 && rect.bottom <= edge.bottom + 1
          && row.scrollWidth <= row.clientWidth + 1 && [...row.querySelectorAll('strong,b')].every(text => {
            const box = text.getBoundingClientRect();
            return box.left >= rect.left - 1 && box.right <= rect.right + 1 && box.top >= rect.top - 1 && box.bottom <= rect.bottom + 1
              && text.scrollWidth <= text.clientWidth + 1;
          });
      });
    }""")


def regions(page):
    names = ('.rc-header', '.rc-status', '.rc-players', '.rc-game-toolbar',
             '.rc-game-display', '.rc-chat', '.rc-footer')
    boxes = {name: page.locator(name).bounding_box() for name in names}
    assert all(boxes.values()), boxes
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    for name, box in boxes.items():
        assert box['x'] >= -1 and box['y'] >= -1, (name, box)
        assert box['x'] + box['width'] <= page.evaluate('innerWidth') + 1, (name, box)
        assert box['y'] + box['height'] <= page.evaluate('innerHeight') + 1, (name, box)
    assert page.locator('.rc-chat-history').evaluate('(node) => getComputedStyle(node).overflowY === "auto"')
    return boxes


def theme_defaults(browser, url):
    for hour, expected in ((10, 'light'), (22, 'dark')):
        context = browser.new_context()
        context.add_init_script(f'const NativeDate=Date;window.Date=class extends NativeDate{{getHours(){{return {hour}}}}};')
        page = context.new_page()
        page.goto(url)
        assert page.evaluate('document.documentElement.dataset.theme') == expected
        assert page.evaluate("localStorage.getItem('retro-coop-theme')") is None
        page.get_by_role('button', name=f'Switch to {"dark" if expected == "light" else "light"} mode').click()
        changed = 'dark' if expected == 'light' else 'light'
        page.reload()
        assert page.evaluate('document.documentElement.dataset.theme') == changed
        context.close()


def automatic_voice(browser, url):
    def participant():
        context = browser.new_context(permissions=['microphone'])
        context.add_init_script("window.captures=[];const nativeCapture=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async options=>{const stream=await nativeCapture(options);captures.push(stream);return stream;};")
        page = context.new_page()
        page.goto(url)
        return context, page
    host_context, host = participant()
    guest_context, guest = participant()
    try:
        host.get_by_role('button', name='Host a new game').click()
        guest.locator('.rc-lobby-card').first.click()
        guest.locator('[data-page=lobby]').wait_for()
        for page in (host, guest):
            page.wait_for_function('captures.length === 1 && captures[0].getAudioTracks()[0].readyState === "live"', timeout=15000)
            assert not page.evaluate('captures[0].getAudioTracks()[0].enabled'), 'Voice must wait for push to talk.'
        host.get_by_role('button', name='Back to Main Page').focus()
        host.keyboard.down('v')
        host.wait_for_function('captures[0].getAudioTracks()[0].enabled')
        host.keyboard.up('v')
        host.wait_for_function('!captures[0].getAudioTracks()[0].enabled')
    finally:
        host_context.close()
        guest_context.close()


def restored_battery_preview(browser, url):
    # The ROM exercises the same preview path as every battery-backed game.
    context = browser.new_context(viewport={'width': 1280, 'height': 800})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))

    def load():
        page.goto(url)
        page.get_by_role('button', name='Host a new game').click()
        page.get_by_role('button', name='Load NES game').click()
        page.get_by_role('button', name='Super Tilt Bro', exact=False).click()
        page.get_by_role('button', name='Ready', exact=True).wait_for(timeout=30000)
        page.locator('.rc-preview img').wait_for()
        assert 'Unable to load' not in page.locator('.rc-status').inner_text()

    try:
        load()
        page.get_by_role('button', name='Ready', exact=True).click()
        page.get_by_role('button', name='Start →').click()
        page.get_by_text('Playing together.', exact=True).wait_for(timeout=15000)
        page.wait_for_function("async()=>new Promise(resolve=>{const q=indexedDB.open('retro-coop-local');q.onsuccess=()=>{const db=q.result,tx=db.transaction('batteries'),count=tx.objectStore('batteries').count();count.onsuccess=()=>resolve(count.result>0);tx.oncomplete=()=>db.close()}})", timeout=20000)
        page.get_by_role('button', name='Back to Main Page', exact=True).click()
        page.get_by_role('button', name='Close lobby').click()
        page.locator('.rc-listing').wait_for()
        load()
        assert not errors, errors
    finally:
        context.close()


def unavailable_preview_keeps_game(browser, url):
    context = browser.new_context(viewport={'width': 1280, 'height': 800})
    context.add_init_script("""window.previewRejected=0;const NativeWorker=Worker;
      window.Worker=class extends NativeWorker{postMessage(data,...rest){
        if(data.type==='state-preview'){previewRejected++;queueMicrotask(()=>this.onmessage?.({data:{type:'state-error',requestId:data.requestId,message:'Preview unavailable'}}));return;}
        return super.postMessage(data,...rest);
      }};""")
    try:
        page = context.new_page()
        page.goto(url)
        page.get_by_role('button', name='Host a new game').click()
        page.get_by_role('button', name='Load NES game').click()
        page.get_by_role('button', name='From Below', exact=True).click()
        page.get_by_role('button', name='Ready', exact=True).wait_for(timeout=30000)
        assert page.evaluate('previewRejected') == 1
        assert 'Unable to load' not in page.locator('.rc-status').inner_text()
    finally:
        context.close()


def abandoned_saved_game_cannot_reopen(browser, url):
    context = browser.new_context(viewport={'width': 1280, 'height': 800})
    try:
        page = context.new_page()
        page.goto(url)
        page.get_by_role('button', name='Host a new game').click()
        page.get_by_role('button', name='Load NES game').click()
        page.get_by_role('button', name='Add NES file').click()
        page.set_input_files('input[aria-label="NES cartridge file"]', {
            'name': 'saved-fixture.nes', 'mimeType': 'application/octet-stream',
            'buffer': (ROOT / 'spikes/d02/fixture.local.nes').read_bytes()})
        page.get_by_role('button', name='Ready', exact=True).wait_for(timeout=30000)
        page.wait_for_function("async()=>new Promise(resolve=>{const q=indexedDB.open('retro-coop-local');q.onsuccess=()=>{const db=q.result,tx=db.transaction('roms'),count=tx.objectStore('roms').count();count.onsuccess=()=>resolve(count.result>0);tx.oncomplete=()=>db.close()}})")
        page.get_by_role('button', name='Change game').click()
        page.get_by_role('button', name='Saved games').click()
        page.get_by_role('button', name='saved-fixture.nes').wait_for()
        page.evaluate("""() => {
          const digest=crypto.subtle.digest.bind(crypto.subtle);
          window.digestHeld=0;
          crypto.subtle.digest=(...args)=>new Promise(resolve=>{
            window.digestHeld++;
            window.releaseDigest=()=>resolve(digest(...args));
          });
        }""")
        page.get_by_role('button', name='saved-fixture.nes').click()
        page.wait_for_function('window.digestHeld === 1')
        page.get_by_role('button', name='Back to Main Page').click()
        page.get_by_role('button', name='Close lobby').click()
        page.locator('.rc-listing').wait_for()
        page.evaluate('window.releaseDigest()')
        page.wait_for_timeout(200)
        assert page.locator('main').get_attribute('data-page') == 'main'
        assert page.locator('.rc-session-holder').is_hidden()
        assert page.get_by_role('button', name='Resume', exact=True).count() == 0
    finally:
        context.close()


def host(page, url):
    page.goto(url, wait_until='domcontentloaded')
    page.get_by_role('button', name='Host a new game').click()
    page.get_by_role('button', name='Back to Main Page', exact=True).wait_for()
    assert page.locator('main').get_attribute('data-page') == 'lobby'
    assert page.get_by_role('heading', name='Create a lobby').count() == 0
    assert page.locator('.rc-players .slot-row').count() == 5
    assert page.get_by_role('button', name='Start →').count() == 0
    assert page.get_by_role('button', name='Load NES game').count() == 1
    assert page.get_by_role('button', name='Copy invite').count() == 1
    assert page.get_by_role('button', name='Voice', exact=True).count() == 1 or page.get_by_role('combobox', name='Settings section').is_visible()
    assert page.get_by_role('button', name='Settings', exact=True).count() == 0
    assert page.get_by_role('heading', name='Settings').is_visible()
    assert page.locator('.rc-side-panel button', has_text='×').count() == 0
    return page.locator('.rc-trail .rc-header-edit').inner_text().replace('✎', '').strip()


def exercise(page, url, size, output, play=False):
    page.set_viewport_size({'width': size[0], 'height': size[1]})
    name = host(page, url)
    assert name
    before = page.locator('.rc-identity').bounding_box()
    original_identity = page.locator('.rc-identity').inner_text()
    page.get_by_role('button', name='Edit your name:', exact=False).click()
    dialog = page.get_by_role('dialog', name='Change your name')
    assert dialog.is_visible()
    assert page.locator('.rc-identity').bounding_box() == before
    field = dialog.get_by_role('textbox', name='Your name')
    assert field.bounding_box()['width'] >= 200
    field.fill('Alex')
    dialog.get_by_role('button', name='Cancel').click()
    assert page.locator('.rc-identity').inner_text() == original_identity
    page.get_by_role('button', name='Edit your name:', exact=False).click()
    page.get_by_role('dialog', name='Change your name').get_by_role('textbox', name='Your name').fill('Alex')
    page.get_by_role('dialog', name='Change your name').get_by_role('button', name='Save name').click()
    page.get_by_role('button', name='Edit your name: Alex').wait_for()
    if size[0] <= 650:
        # The name must retain a readable track between the lobby title and theme control.
        identity_name = page.locator('.rc-identity .rc-header-edit').bounding_box()
        assert identity_name['width'] >= 120, (size, identity_name)
        assert page.locator('.rc-identity .rc-header-edit').evaluate(
            'node => node.scrollWidth <= node.clientWidth + 1'), size
    page.get_by_role('button', name='Edit lobby name:', exact=False).click()
    assert page.get_by_role('dialog', name='Change lobby name').is_visible()
    page.get_by_role('textbox', name='Lobby name').fill('Test Lobby')
    page.get_by_role('textbox', name='Lobby name').press('Enter')
    page.get_by_role('button', name='Edit lobby name: Test Lobby').wait_for()
    assert page.locator('.rc-identity').bounding_box() == before
    if size[0] == 320:
        long_name = 'The Very Long Lobby Name That Should Remain Readable On Small Screens'
        page.get_by_role('button', name='Edit lobby name: Test Lobby').click()
        page.get_by_role('textbox', name='Lobby name').fill(long_name)
        page.get_by_role('button', name='Save name').click()
        page.get_by_role('button', name=f'Edit lobby name: {long_name}').wait_for()
        assert page.locator('.rc-lobby-heading').evaluate('node => node.scrollHeight <= node.clientHeight')
        assert page.locator('.rc-identity').bounding_box() == before
        page.get_by_role('button', name=f'Edit lobby name: {long_name}').click()
        page.get_by_role('textbox', name='Lobby name').fill('Test Lobby')
        page.get_by_role('button', name='Save name').click()
        page.get_by_role('button', name='Edit lobby name: Test Lobby').wait_for()
    invite = page.get_by_role('button', name='Copy invite')
    assert invite.count() == 1 and invite.bounding_box()['y'] < page.locator('.rc-game-toolbar').bounding_box()['y']
    slot = page.locator('[data-slot-id="slot-3"] .slot-row')
    slot.click()
    menu = page.locator('[data-slot-id="slot-3"] .slot-menu')
    assert menu.get_by_role('menuitem').all_text_contents() == ['Close slot']
    slot.click()
    assert menu.count() == 0
    assert page.locator('.slot-index').count() == 0
    choose_section(page, 'Voice')
    assert page.locator('main').get_attribute('data-page') == 'lobby'
    page.locator('.rc-game-toolbar').click(position={'x': 2, 'y': 2})
    page.keyboard.press('Escape')
    assert page.get_by_role('heading', name='Settings').is_visible()
    if page.get_by_role('combobox', name='Settings section').is_visible():
        assert page.get_by_role('combobox', name='Settings section').input_value() == 'voice'
    else:
        assert page.get_by_role('button', name='Voice', exact=True).get_attribute('aria-current') == 'page'
    choose_section(page, 'Lobby')
    assert page.get_by_text('Who can join?', exact=True).is_visible()
    assert page.locator('.rc-lobby-access button').evaluate("node => { const button = node.getBoundingClientRect(), panel = node.closest('.rc-tool-body').getBoundingClientRect(); return button.bottom <= panel.bottom + 1 && button.top >= panel.top - 1; }")
    page.get_by_role('button', name='Copy invite').click()
    page.wait_for_function("document.querySelector('.rc-dialog-card') || document.querySelector('.rc-status-copy')?.textContent?.includes('Invitation copied.')")
    if page.get_by_role('dialog', name='Invitation link').count():
        page.get_by_role('button', name='Done').click()
    assert page.get_by_role('heading', name='Settings').is_visible()
    assert page.get_by_text('Who can join?', exact=True).is_visible()
    if size[0] <= 650:
        for section in ('Controls', 'Sound', 'Voice', 'Profile'):
            choose_section(page, section)
            assert settings_controls_fit(page), (size, section)
        page.get_by_role('combobox', name='Settings section').select_option(label='Voice')
        for option in ('Other players', 'Devices'):
            page.get_by_role('combobox', name='Voice setting').select_option(label=option)
            assert settings_controls_fit(page), (size, option)
        choose_section(page, 'Lobby')
    base = regions(page)
    page.screenshot(path=str(output / f'lobby-{size[0]}x{size[1]}.png'))
    if play:
        page.get_by_role('button', name='Load NES game').click()
        page.get_by_role('button', name='From Below', exact=True).click()
        page.get_by_role('button', name='Ready', exact=True).wait_for(timeout=30000)
        assert page.get_by_role('button', name='Change game').count() == 1
        assert page.locator('.rc-preview-actions').count() == 0
        assert page.locator('.rc-game-display button', has_text='Change game').count() == 0
        page.get_by_role('textbox', name='Message everyone').fill('hello')
        page.get_by_role('button', name='Send').click()
        page.get_by_text('(you) Alex: hello', exact=True).wait_for()
        page.get_by_role('button', name='Ready', exact=True).click()
        page.get_by_role('button', name='Start →').click(timeout=30000)
        page.get_by_text('Playing together.', exact=True).wait_for(timeout=15000)
        assert page.locator('.rc-game-heading').inner_text() == 'From Below'
        assert page.get_by_role('button', name='Mute game').count() == 0
        choose_section(page, 'Sound')
        assert page.get_by_role('button', name='Mute game').count() == 1
        choose_section(page, 'Game')
        assert page.locator('.rc-controller-art').is_visible()
        assert guide_fits(page), f'Controller guide overflowed at {size}'
        regions(page)
        page.screenshot(path=str(output / f'playing-{size[0]}x{size[1]}.png'))
        page.get_by_role('button', name='Expand game to full screen').click()
        expanded = page.locator('.rc-game-fullscreen').bounding_box()
        assert expanded['width'] == size[0] and expanded['height'] == size[1]
        page.get_by_role('button', name='Return game to lobby').click()
        assert page.locator('.rc-game-fullscreen').count() == 0
    if size == (1280, 800):
        page.evaluate("""() => {
          window.heldInvites=[];
          Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:()=>new Promise((resolve,reject)=>window.heldInvites.push({resolve,reject}))}});
        }""")
        page.get_by_role('button', name='Copy invite').click()
        page.wait_for_function('window.heldInvites.length === 1')
        page.get_by_role('button', name='Back to Main Page', exact=True).click()
        assert page.get_by_role('alertdialog', name='Close this lobby?').is_visible()
        page.evaluate('window.heldInvites[0].resolve()')
        page.wait_for_timeout(100)
        assert 'Invitation copied.' not in page.locator('.rc-status').inner_text()
        page.get_by_role('button', name='Stay').click()
        page.get_by_role('button', name='Copy invite').click()
        page.wait_for_function('window.heldInvites.length === 2')
    page.get_by_role('button', name='Back to Main Page', exact=True).click()
    assert page.get_by_role('alertdialog', name='Close this lobby?').is_visible()
    page.get_by_role('button', name='Close lobby').click()
    page.locator('.rc-listing').wait_for(timeout=10000)
    if size == (1280, 800):
        page.evaluate("window.heldInvites[1].reject(Error('clipboard unavailable'))")
        page.wait_for_timeout(100)
        assert page.get_by_role('dialog', name='Invitation link').count() == 0
        assert page.locator('main').get_attribute('data-page') == 'main'
    return {'size': size, 'lobby': name, 'regions': list(base), 'played': play}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', choices=('firefox', 'chromium'), default='chromium')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--zoom', action='store_true')
    parser.add_argument('--local-fast-exit', action='store_true')
    args = parser.parse_args()
    if args.zoom and args.browser != 'chromium':
        parser.error('--zoom needs Chromium')
    output = args.output or ROOT / 'spikes/d02/public-entrypoint.local/unified-shell'
    output.mkdir(parents=True, exist_ok=True)
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                               stdout=subprocess.PIPE, text=True)
    try:
        assert service.stdout
        url = json.loads(service.stdout.readline())['url']
        with sync_playwright() as playwright:
            errors = []
            if args.zoom:
                with zoom_context(playwright, {'width': 640, 'height': 1136}) as (context, worker):
                    page = context.new_page()
                    page.goto(url, wait_until='domcontentloaded')
                    zoom = browser_zoom(page, worker, 2)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    rows = [exercise(page, url, (320, 568), output, play=True)]
                    page.close()
                assert not errors, errors
                print(json.dumps({'result': 'pass', 'zoom': zoom, 'checks': rows}), flush=True)
                return
            browser = getattr(playwright, args.browser).launch(headless=True, **({'args': ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream']} if args.browser == 'chromium' else {}))
            try:
                page = browser.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                rows = [exercise(page, url, size, output, play=size in ((1280, 800), (320, 568)))
                        for size in ((1280, 800), (650, 760), (401, 760), (320, 650), (320, 568))]
                page.close()
                theme_defaults(browser, url)
                if args.browser == 'chromium':
                    automatic_voice(browser, url)
                    restored_battery_preview(browser, url)
                    unavailable_preview_keeps_game(browser, url)
                    abandoned_saved_game_cannot_reopen(browser, url)
                assert not errors, errors
                print(json.dumps({'result': 'pass', 'checks': rows, 'theme_defaults': True, 'automatic_voice': args.browser == 'chromium', 'restored_battery_preview': args.browser == 'chromium', 'preview_recovery': args.browser == 'chromium', 'abandoned_saved_game': args.browser == 'chromium'}), flush=True)
            finally:
                browser.close()
    finally:
        service.terminate()
        service.wait(timeout=10)


if __name__ == '__main__':
    main()
