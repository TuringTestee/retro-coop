#!/usr/bin/env python3
"""Exercise game selection, cancellation, and recovery after lobby creation."""

import asyncio
import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.async_api import Error as PlaywrightError, async_playwright
from ui_helpers import choose_section_async


ROOT = Path(__file__).resolve().parents[2]
URL = 'http://127.0.0.1:8895/'
FIXTURE = ROOT / 'spikes/d02/fixture.local.nes'


async def create_lobby(page, name, protected=False):
    await page.goto(URL)
    await page.get_by_role('button', name='Host a new game').click()
    await page.locator('.rc-trail .rc-header-edit').click()
    await page.get_by_role('textbox', name='Lobby name').fill(name)
    await page.get_by_role('textbox', name='Lobby name').press('Enter')
    if protected:
        await choose_section_async(page, 'Lobby')
        await page.get_by_role('button', name='Require password').click()
        await page.get_by_label('New lobby password').fill('blue-sky-room')
        await page.get_by_role('button', name='Save password').click()
    await page.get_by_role('button', name='Load NES game').wait_for(timeout=15000)
    assert await page.get_by_role('button', name='Start →').count() == 0
    assert await page.get_by_test_id('room-slot').count() == 5


async def selected_file(page, file):
    await page.locator('input[type=file]').evaluate('(input) => { input.value = ""; }')
    await page.set_input_files('input[type=file]', file)


async def wait_for_empty_game(page):
    await page.get_by_role('button', name='Load NES game').wait_for(timeout=20000)
    assert await page.get_by_role('button', name='Start →').count() == 0
    assert await page.get_by_test_id('room-slot').count() == 5


async def main():
    assert FIXTURE.exists(), 'Run sh scripts/foundation/prepare.sh first'
    output = Path(os.environ.get('RETRO_COOP_RT2_OUTPUT', '/tmp/retro-coop-rt2'))
    output.mkdir(parents=True, exist_ok=True)
    rom_dir = tempfile.TemporaryDirectory(prefix='retro-coop-rt2-')
    env = {**os.environ, 'RETRO_COOP_SKIP_INSTALL': '1',
           'RETRO_COOP_SKIP_PREPARE': '1', 'RETRO_COOP_CLIENT_PORT': '8895',
           'RETRO_COOP_COORDINATOR_PORT': '8897', 'COORDINATOR_ROM_DIR': rom_dir.name}
    log = open('/tmp/retro-coop-rt2-demo.log', 'w')
    service = subprocess.Popen(['sh', 'scripts/demo.sh'], cwd=ROOT, env=env,
                               stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    started = time.monotonic()
    try:
        for _ in range(100):
            try:
                with urlopen(URL, timeout=.2) as response:
                    if response.status == 200:
                        break
            except OSError:
                await asyncio.sleep(.1)
        else:
            raise AssertionError('The README demo did not start: ' +
                                 Path('/tmp/retro-coop-rt2-demo.log').read_text())

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            context = await browser.new_context()
            host = await context.new_page()
            await create_lobby(host, 'Private Upload', protected=True)

            release = asyncio.Event()
            seen = asyncio.Event()

            async def hold_upload(route):
                seen.set()
                await release.wait()
                try:
                    await route.continue_()
                except PlaywrightError:
                    # Cancel aborts the request while its route is held.
                    pass

            await host.route('**/rooms/*/rom', hold_upload)
            await selected_file(host, str(FIXTURE))
            await asyncio.wait_for(seen.wait(), 20)
            assert await host.get_by_role('button', name='Cancel selection').is_visible()
            assert await host.get_by_test_id('room-slot').count() == 5
            await host.get_by_role('button', name='Cancel selection').click()
            release.set()
            await wait_for_empty_game(host)
            await host.unroute('**/rooms/*/rom', hold_upload)

            guest = await context.new_page()
            await guest.goto(URL)
            await guest.locator('.rc-listing').wait_for()
            protected_row = guest.locator('.rc-lobby-card').filter(has_text='Private Upload')
            await protected_row.wait_for(timeout=15000)
            assert 'Password' in await protected_row.inner_text()
            await protected_row.click()
            assert await guest.get_by_label('Lobby password').is_visible()

            failed = [False]

            async def fail_once(route):
                if not failed[0]:
                    failed[0] = True
                    await route.abort('failed')
                else:
                    await route.continue_()

            await host.route('**/rooms/*/rom', fail_once)
            await selected_file(host, str(FIXTURE))
            await host.get_by_text('Upload connection failed. Retry upload.', exact=True).wait_for(timeout=20000)
            assert failed[0], 'The failed upload route was never reached'
            await wait_for_empty_game(host)
            await host.unroute('**/rooms/*/rom', fail_once)

            await selected_file(host, str(FIXTURE))
            await host.get_by_role('button', name='Change game').wait_for(timeout=30000)
            preview = host.locator('.rc-preview img')
            await preview.wait_for(timeout=15000)
            assert (await preview.get_attribute('src')).startswith('data:image/png')
            assert await host.get_by_role('button', name='Start →').count() == 0
            await host.get_by_role('button', name='Ready', exact=True).click()
            await host.get_by_role('button', name='Start →').wait_for(state='visible')
            assert await host.get_by_role('button', name='Start →').is_enabled()
            selected_title = await host.locator('.rc-game-heading').inner_text()
            await selected_file(host, {'name': 'bad.nes',
                                       'mimeType': 'application/octet-stream',
                                       'buffer': b'invalid'})
            await host.get_by_text('This is not an NES game', exact=False).wait_for(timeout=15000)
            await host.get_by_role('button', name='Change game').wait_for(timeout=15000)
            assert await host.locator('.rc-game-heading').inner_text() == selected_title
            assert await host.get_by_role('button', name='Start →').count() == 0
            await host.get_by_role('button', name='Ready', exact=True).click()
            assert await host.get_by_role('button', name='Start →').is_enabled()

            public = await context.new_page()
            await create_lobby(public, 'Open Arcade')
            await guest.locator('.rc-join-detail').get_by_role('button', name='Cancel').click()
            await guest.locator('.rc-listing').wait_for()
            await guest.get_by_placeholder('Search lobbies').fill('Open Arcade')
            row = guest.locator('.rc-lobby-card').filter(has_text='Open Arcade')
            await row.wait_for(timeout=15000)
            assert 'No game yet' in await row.inner_text()
            assert 'Public' in await row.inner_text()

            invalid = await context.new_page()
            await create_lobby(invalid, 'Invalid NES')
            await selected_file(invalid, {'name': 'bad.nes',
                                          'mimeType': 'application/octet-stream',
                                          'buffer': b'invalid'})
            await invalid.get_by_text('This is not an NES game', exact=False).wait_for(timeout=15000)
            await wait_for_empty_game(invalid)

            included = await context.new_page()
            await create_lobby(included, 'Included NES')
            await included.get_by_role('button', name='Load NES game').click()
            await included.get_by_role('button', name='Super Tilt Bro', exact=False).click()
            await included.get_by_role('button', name='Change game').wait_for(timeout=30000)
            await browser.close()

        result = {'result': 'pass', 'public_entrypoint': URL,
                  'cancel_keeps_lobby': True, 'failed_upload_retry': True,
                  'protected_requires_password': True, 'public_empty_lobby_listed': True,
                  'invalid_file_keeps_lobby': True, 'failed_replacement_keeps_game': True,
                  'custom_game_preview': True, 'included_game_after_creation': True,
                  'duration_seconds': round(time.monotonic() - started, 2)}
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
    finally:
        os.killpg(service.pid, signal.SIGTERM)
        try:
            service.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(service.pid, signal.SIGKILL)
            service.wait()
        log.close()
        rom_dir.cleanup()


if __name__ == '__main__':
    asyncio.run(main())
