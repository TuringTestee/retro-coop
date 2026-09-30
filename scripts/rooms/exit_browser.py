#!/usr/bin/env python3
"""Exercise directory exits through the public browser entry point."""
import json
import os
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(os.environ.get('RETRO_COOP_STATIC_ROOT', ROOT / 'apps/client/dist'))


def main():
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                               env={**os.environ, 'COORDINATOR_EMPTY_OFFERS': 'super-tilt-bro-pal'},
                               stdout=subprocess.PIPE, text=True)
    try:
        assert service.stdout
        url = json.loads(service.stdout.readline())['url']
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.get_by_role('button', name='Create game', exact=True).click()
            page.locator('input[type=file]').set_input_files(STATIC / 'generated/diagnostic.nes')
            page.get_by_role('button', name='Create room', exact=True).click()
            page.get_by_test_id('room-view').wait_for(state='attached')
            page.get_by_role('button', name='Public rooms', exact=True).click()
            page.get_by_role('group', name='Confirm leave').wait_for()
            assert page.get_by_test_id('directory').count() == 0
            page.get_by_role('button', name='Stay in room', exact=True).click()
            assert page.locator('.room-panel').is_visible()
            page.get_by_role('button', name='Public rooms', exact=True).click()
            page.get_by_role('button', name='Confirm leave', exact=True).click()
            page.get_by_test_id('directory').wait_for()
            page.wait_for_function("!document.querySelector('[data-testid=room-view]') && !document.querySelector('.panel .controls button[aria-pressed]')")
            assert page.get_by_role('button', name='Resume local game', exact=True).count() == 0
            local = browser.new_page()
            local.goto(url)
            local.get_by_role('button', name='Create game', exact=True).click()
            local.locator('input[type=file]').set_input_files(STATIC / 'generated/diagnostic.nes')
            local.get_by_role('button', name='Play locally', exact=True).click()
            local.get_by_role('button', name='Resume', exact=True).wait_for()
            local.get_by_role('button', name='Public rooms', exact=True).click()
            local.get_by_test_id('directory').wait_for()
            assert local.get_by_role('button', name='Resume local game', exact=True).count() == 0
            assert local.get_by_test_id('frames').inner_text() == '0 frames'
            browser.close()
        print(json.dumps({'host_close_before_directory': True, 'stay_retains_room': True, 'local_game_ends_before_directory': True}))
    finally:
        service.terminate()
        service.wait(timeout=10)


if __name__ == '__main__':
    main()
