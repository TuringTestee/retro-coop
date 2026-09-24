#!/usr/bin/env python3
"""Exercise fixed page navigation from the public room browser in Chromium."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def geometry(page, label):
    canvas = page.locator('canvas').bounding_box()
    room = page.locator('.room-panel').bounding_box()
    assert canvas and room, (label, canvas, room)
    overlap = not (canvas['x'] + canvas['width'] <= room['x'] or room['x'] + room['width'] <= canvas['x']
                   or canvas['y'] + canvas['height'] <= room['y'] or room['y'] + room['height'] <= canvas['y'])
    assert not overlap, (label, canvas, room)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), label
    assert page.locator('.room-panel').evaluate("node => getComputedStyle(node).position !== 'fixed'"), label
    if room['y'] + room['height'] > page.viewport_size['height']:
        page.evaluate('window.scrollTo(0, document.documentElement.scrollHeight)')
        assert page.evaluate('window.scrollY > 0'), (label, 'room is below the viewport but the page cannot scroll')
        page.evaluate('window.scrollTo(0, 0)')
    return {'viewport': label, 'canvas': canvas, 'room': room}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT, stdout=subprocess.PIPE, text=True)
    try:
        assert service.stdout
        url = json.loads(service.stdout.readline())['url']
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            host = browser.new_page(viewport={'width': 1280, 'height': 720})
            errors = []
            host.on('pageerror', lambda error: errors.append(str(error)))
            host.goto(url)
            host.get_by_role('button', name='Settings', exact=True).click()
            host.wait_for_function("document.activeElement?.id === 'settings-title'")
            assert host.locator('dialog').count() == 0
            assert not host.locator('.directory-panel').is_visible()
            host.get_by_role('button', name='Restore keyboard defaults').click()
            host.keyboard.press('Escape')
            assert host.get_by_role('button', name='Keep mappings').count() == 0
            host.screenshot(path=str(args.output / 'settings.png'))
            host.get_by_role('button', name='Local data', exact=True).click()
            host.wait_for_function("document.activeElement?.id === 'local-data-title'")
            host.get_by_role('button', name='Delete all local data').click()
            host.keyboard.press('Escape')
            assert host.get_by_role('button', name='Confirm', exact=True).count() == 0
            host.screenshot(path=str(args.output / 'local-data.png'))
            host.get_by_role('button', name='Back', exact=True).click()
            host.wait_for_function("document.activeElement?.textContent === 'Local data'")
            host.get_by_role('button', name='Back', exact=True).click()
            host.wait_for_function("document.activeElement?.textContent === 'Settings'")
            host.get_by_role('button', name='Create game', exact=True).click()
            host.locator('input[type=file]').set_input_files(ROOT / 'apps/client/dist/generated/diagnostic.nes')
            host.get_by_role('button', name='Create room', exact=True).click()
            host.get_by_role('button', name='Start game', exact=True).wait_for(timeout=30000)
            invite = host.get_by_label('Room invitation', exact=True).input_value()
            host.screenshot(path=str(args.output / 'waiting.png'))
            host.get_by_text('Connection and session settings', exact=True).click()
            host.get_by_text('Session settings', exact=True).click()
            visibility = host.get_by_label('Unlisted · invitation only', exact=True)
            visibility.click()
            host.wait_for_function("document.querySelector('#room-heading')?.textContent.includes('Unlisted')")
            visibility.click()
            host.get_by_role('button', name='Make public', exact=True).wait_for()
            assert host.locator('dialog').count() == 0
            host.keyboard.press('Escape')
            host.wait_for_function("document.activeElement?.matches('.visibility input')")
            visibility.click()
            host.get_by_role('button', name='Make public', exact=True).click()
            host.wait_for_function("document.querySelector('#room-heading')?.textContent.includes('Public')")
            host.get_by_text('Session settings', exact=True).click()
            host.get_by_text('Connection and session settings', exact=True).click()
            guest = browser.new_page(viewport={'width': 390, 'height': 700})
            guest.on('pageerror', lambda error: errors.append(str(error)))
            guest.goto(invite)
            guest.get_by_role('button', name='Join room', exact=True).wait_for(timeout=15000)
            assert guest.locator('.room-panel').is_visible()
            assert guest.locator('.room-panel').evaluate("node => getComputedStyle(node).position !== 'fixed'")
            assert guest.evaluate('document.documentElement.scrollWidth <= innerWidth')
            guest.screenshot(path=str(args.output / 'invitation.png'), full_page=True)
            guest.close()
            host.get_by_role('button', name='Start game', exact=True).click()
            host.locator('main.playing.with-room').wait_for(timeout=15000)
            wide = geometry(host, '1280x720')
            host.screenshot(path=str(args.output / 'playing-wide.png'))
            host.get_by_role('button', name='Saves', exact=True).click()
            assert host.get_by_role('heading', name='Saves on this device').is_visible()
            assert host.locator('dialog').count() == 0
            assert not host.locator('.room-panel').is_visible()
            host.screenshot(path=str(args.output / 'saves.png'))
            host.get_by_role('button', name='Back', exact=True).click()
            host.wait_for_function("document.activeElement?.textContent === 'Saves'")
            host.get_by_role('button', name='Rewind', exact=True).click()
            assert host.get_by_role('heading', name='Rewind local game').is_visible()
            host.screenshot(path=str(args.output / 'rewind.png'))
            host.get_by_role('button', name='Back', exact=True).click()
            host.get_by_role('button', name='Game help', exact=True).click()
            assert host.get_by_role('heading', name='Game help').is_visible()
            host.screenshot(path=str(args.output / 'help.png'))
            host.get_by_text('Technical details', exact=True).click()
            expected = hashlib.sha256((ROOT / 'apps/client/dist/generated/diagnostic.nes').read_bytes()).hexdigest()
            assert expected in host.get_by_test_id('fingerprint').inner_text()
            host.get_by_role('button', name='Back', exact=True).click()
            host.set_viewport_size({'width': 390, 'height': 700})
            narrow = geometry(host, '390x700')
            host.screenshot(path=str(args.output / 'playing-narrow.png'), full_page=True)
            host.set_viewport_size({'width': 640, 'height': 360})
            zoom = geometry(host, '640x360 (200% zoom equivalent)')
            host.screenshot(path=str(args.output / 'playing-zoom.png'), full_page=True)
            host.get_by_role('button', name='Leave room', exact=True).click()
            host.get_by_role('button', name='Confirm leave', exact=True).wait_for()
            assert host.locator('dialog').count() == 0
            host.keyboard.press('Escape')
            host.wait_for_function("document.activeElement?.matches('[data-leave-room]')")
            host.get_by_role('button', name='Leave room', exact=True).click()
            host.get_by_role('button', name='Confirm leave', exact=True).click()
            host.get_by_test_id('directory').wait_for(state='visible')
            assert host.locator('.release-notice').count() == 0
            assert not errors, errors
            result = {'result': 'pass', 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                      'browser': browser.version, 'pages': ['Settings', 'Local data', 'Saves', 'Rewind', 'Game help', 'Invitation'],
                      'focus_return': True, 'inline_confirmations': True, 'dialogs': 0, 'layout': [wide, narrow, zoom], 'page_errors': errors}
            (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result))
            browser.close()
    finally:
        service.terminate()
        try:
            service.wait(timeout=5)
        except subprocess.TimeoutExpired:
            service.kill()
            service.wait()


if __name__ == '__main__':
    main()
