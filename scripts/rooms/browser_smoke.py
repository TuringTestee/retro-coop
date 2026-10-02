#!/usr/bin/env python3
"""Exercise the public create → gather → load → ready → play → exit journey."""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from ui_helpers import rename_lobby


ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(os.environ.get('RETRO_COOP_STATIC_ROOT', ROOT / 'apps/client/dist'))
ROM = STATIC / 'generated/diagnostic.nes'
parser = argparse.ArgumentParser()
parser.add_argument('--chrome', action='store_true')
parser.add_argument('--output', type=Path, default=Path('rooms.local.json'))
args = parser.parse_args()
assert ROM.exists(), 'Build the client and diagnostic NES fixture first.'
started = time.monotonic()
service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                           stdout=subprocess.PIPE, text=True)
try:
    assert service.stdout
    url = json.loads(service.stdout.readline())['url']
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**({'channel': 'chrome'} if args.chrome else {}))
        errors, sent, received = [], [], []

        def page(context):
            tab = context.new_page()
            tab.set_viewport_size({'width': 1280, 'height': 800})
            tab.on('pageerror', lambda error: errors.append(str(error)))
            tab.on('websocket', lambda socket: (
                socket.on('framesent', lambda raw: sent.append(json.loads(raw))),
                socket.on('framereceived', lambda raw: received.append(json.loads(raw))),
            ))
            return tab

        host_context = browser.new_context(permissions=['clipboard-read', 'clipboard-write'])
        host = page(host_context)
        host.goto(url)
        host.get_by_role('button', name='Host a new game').click()
        rename_lobby(host, 'Play Table')
        host.get_by_role('button', name='Load NES game').wait_for(timeout=15000)
        assert host.get_by_test_id('room-slot').count() == 5
        assert host.get_by_role('button', name='Start →').count() == 0
        assert any(frame['type'] == 'createLobby' for frame in sent)
        assert not any(frame['type'] == 'beginGameSelection' for frame in sent), \
            'The lobby needed a game before guests could join.'
        host.get_by_role('button', name='Copy invite').click()
        invitation = host.evaluate('navigator.clipboard.readText()')
        assert '#invite=' in invitation

        guest = page(browser.new_context())
        guest.goto(invitation)
        guest.get_by_role('button', name='Join lobby').click()
        guest.get_by_text('Waiting for the host to load a NES game').wait_for(timeout=15000)
        assert guest.get_by_test_id('room-slot').count() == 5
        assert guest.locator('canvas').get_attribute('data-frame-count') == '0'
        assert host.get_by_role('button', name='Start →').count() == 0
        args.output.parent.mkdir(parents=True, exist_ok=True)
        host.screenshot(path=str(args.output.with_suffix('.waiting.png')))

        host.locator('input[aria-label="NES cartridge file"]').set_input_files(ROM)
        host.get_by_role('button', name='Change game').wait_for(timeout=30000)
        assert any(frame['type'] == 'beginGameSelection' for frame in sent)
        host.locator('.rc-preview img').wait_for(timeout=15000)
        try:
            expect(host.get_by_role('button', name='Ready', exact=True)).to_be_enabled(timeout=30000)
        except AssertionError as error:
            latest = next((frame['room'] for frame in reversed(received)
                           if frame.get('type') == 'room' and 'room' in frame), None)
            raise AssertionError({'host_status': host.locator('.rc-status').inner_text(),
                                  'game': host.locator('.rc-preview').inner_text(),
                                  'room': latest}) from error
        expect(guest.get_by_role('button', name='Ready', exact=True)).to_be_enabled(timeout=30000)
        assert host.get_by_role('button', name='Start →').count() == 0
        host.get_by_role('button', name='Ready', exact=True).click()
        host.locator('[data-slot-id="slot-1"] .slot-state').get_by_text('Ready', exact=True).wait_for()
        assert host.get_by_role('button', name='Start →').count() == 0, \
            'The host could start while the guest was unprepared.'
        guest.get_by_role('button', name='Ready', exact=True).click()
        expect(host.get_by_role('button', name='Start →')).to_be_enabled(timeout=30000)
        host.get_by_role('button', name='Start →').click()
        host.locator('[data-page="playing"]').wait_for(timeout=30000)
        guest.locator('[data-page="playing"]').wait_for(timeout=30000)
        assert host.locator('.rc-players [data-testid="room-slot"]').count() == 5
        assert guest.locator('.rc-players [data-testid="room-slot"]').count() == 5
        assert any(frame.get('type') == 'room' and frame['room']['game']['status'] == 'countdown'
                   for frame in received), 'No broadcast countdown reached the browsers.'
        for tab in (host, guest):
            tab.wait_for_function("Number(document.querySelector('canvas')?.dataset.frameCount) > 30",
                                  timeout=15000)
        host.screenshot(path=str(args.output.with_suffix('.playing.png')))

        host.get_by_role('button', name='Back to Main Page').click()
        host.get_by_role('button', name='Close lobby').click()
        host.locator('.rc-listing').wait_for(timeout=15000)
        guest.locator('.rc-listing').wait_for(timeout=15000)
        assert host.locator('[data-page="playing"]').count() == 0
        assert guest.locator('[data-page="playing"]').count() == 0
        assert not errors, errors
        assert not any(key in frame for frame in sent for key in ('rom', 'filename', 'save', 'state'))
        result = {'result': 'pass', 'browser': browser.version,
                  'empty_lobby_then_guest_then_game': True,
                  'all_players_ready_before_start': True,
                  'shared_countdown_and_play': True,
                  'both_browsers_rendered_frames': True,
                  'visible_players_during_play': True,
                  'closing_lobby_exits_both_browsers': True,
                  'metadata_only_websocket_commands': True,
                  'seconds': round(time.monotonic() - started, 2),
                  'page_errors': errors}
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        browser.close()
finally:
    service.terminate()
    service.wait(timeout=10)
