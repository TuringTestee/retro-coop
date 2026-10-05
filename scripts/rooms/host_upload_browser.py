#!/usr/bin/env python3
"""Exercise game selection, cancellation, and recovery after lobby creation."""

import asyncio
import json
import io
import zipfile
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.async_api import Error as PlaywrightError, async_playwright, expect
from ui_helpers import choose_section_async


ROOT = Path(__file__).resolve().parents[2]
URL = 'http://127.0.0.1:8895/'
FIXTURE = ROOT / 'spikes/d02/fixture.local.nes'


async def create_lobby(page, name, protected=False, fresh=False):
    await page.goto(URL)
    await page.get_by_role('button', name='Host a new game').click()
    if fresh:
        await page.get_by_role('alertdialog', name='Restore your last hosted game?').wait_for()
        await page.get_by_role('button', name='Start fresh', exact=True).click()
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
    rom_dir = tempfile.TemporaryDirectory(prefix='roms-', dir=output)
    env = {**os.environ, 'RETRO_COOP_SKIP_INSTALL': '1',
           'RETRO_COOP_SKIP_PREPARE': '1', 'RETRO_COOP_CLIENT_PORT': '8895',
           'RETRO_COOP_COORDINATOR_PORT': '8897', 'COORDINATOR_ROM_DIR': rom_dir.name}
    log = open(output / 'demo.log', 'w')
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
                                 (output / 'demo.log').read_text())

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(ignore_default_args=['--mute-audio'])
            context = await browser.new_context()
            errors = []
            await context.add_init_script("""window.uploadProof={workers:[],room:null};
              const WorkerBase=Worker;window.Worker=class extends WorkerBase{
                constructor(...args){super(...args);const record={worker:this,id:uploadProof.workers.length,ended:false};uploadProof.workers.push(record);this.record=record;
                  this.addEventListener('message',({data})=>{if(data.type==='state-hash')record.hash=data.info;});}
                postMessage(data,...args){if(data.type==='load')this.record.rom={bytes:data.rom.byteLength,magic:Array.from(new Uint8Array(data.rom,0,4))};return super.postMessage(data,...args);}
                terminate(){this.record.ended=true;super.terminate();}
              };
              const Socket=WebSocket;window.WebSocket=class extends Socket{constructor(...args){super(...args);this.addEventListener('message',({data})=>{const message=JSON.parse(data);if(message.type==='room')uploadProof.room=message.room;else if(message.type==='result'&&message.ok&&message.data?.room)uploadProof.room=message.data.room;});}};
            """)
            context.on('page', lambda page: page.on('pageerror', lambda error: errors.append(str(error))))
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
            await host.get_by_text('Upload connection failed. Retry upload.', exact=False).wait_for(timeout=20000)
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

            # Both ZIP entries use the ordinary preparation function and extracted NES identity.
            def archive(name, data):
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zipped:
                    zipped.writestr(name, data)
                return buffer.getvalue()

            async def pick_zip(name, data):
                await host.get_by_role('button', name='Change game').click()
                async with host.expect_file_chooser() as chosen:
                    await host.get_by_role('button', name='Add game file', exact=True).click()
                await (await chosen.value).set_files({'name': name, 'mimeType': 'application/zip', 'buffer': data})

            async def preserved():
                await host.get_by_role('button', name='Change game').wait_for(timeout=20000)
                assert await host.locator('.rc-game-heading').inner_text() == selected_title
                assert await preview.get_attribute('src') == old_preview
                assert await host.evaluate('id=>!uploadProof.workers[id].ended', old_worker)
                assert await host.evaluate('uploadProof.room.fingerprint.romSha256') == old_sha
                await expect(host.get_by_role('button', name='Ready', exact=True)).to_be_enabled()

            old_preview = await preview.get_attribute('src')
            old_worker = await host.evaluate('uploadProof.workers.filter(worker=>!worker.ended).at(-1).id')
            old_sha = await host.evaluate('uploadProof.room.fingerprint.romSha256')
            await pick_zip('empty.zip', archive('readme.txt', b'No cartridge'))
            await host.get_by_text('This ZIP contains no NES game. Choose another file.', exact=True).wait_for()
            await preserved()
            await host.screenshot(path=str(output / 'zip-failure-preserves-game.png'))

            # Use a new identity so a failed post-extraction upload cannot masquerade as cache reuse.
            replacement = bytearray(FIXTURE.read_bytes())
            replacement[-1] ^= 1
            picker_zip = archive('games/ZIP Picker Game.nes', replacement)
            failed[0] = False
            await host.route('**/rooms/*/rom', fail_once)
            await pick_zip('outer-picker.zip', picker_zip)
            await host.get_by_text('Upload connection failed. Retry upload.', exact=False).wait_for(timeout=20000)
            assert failed[0]
            await preserved()
            await host.unroute('**/rooms/*/rom', fail_once)
            await pick_zip('outer-picker.zip', picker_zip)
            await expect(host.locator('.rc-game-heading')).to_have_attribute('title', 'ZIP Picker Game', timeout=30000)
            await host.get_by_role('button', name='Change game').wait_for()
            await preview.wait_for()
            await host.screenshot(path=str(output / 'zip-picker-preview.png'))
            assert await host.evaluate('id=>uploadProof.workers[id].ended', old_worker)

            drop_zip = archive('nested/ZIP Drop Game.nes', FIXTURE.read_bytes())
            await host.locator('.rc-game-zone').evaluate("""(node,bytes)=>{
              const transfer=new DataTransfer();transfer.items.add(new File([new Uint8Array(bytes)],'outer-drop.zip',{type:'application/zip'}));
              node.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer}));
            }""", list(drop_zip))
            await expect(host.locator('.rc-game-heading')).to_have_attribute('title', 'ZIP Drop Game', timeout=30000)
            await host.get_by_role('button', name='Change game').wait_for()
            await preview.wait_for()
            await host.screenshot(path=str(output / 'zip-drop-preview.png'))
            await guest.get_by_label('Lobby password').fill('blue-sky-room')
            await guest.get_by_role('button', name='Join lobby', exact=True).click()
            await expect(guest.get_by_role('button', name='Ready', exact=True)).to_be_enabled(timeout=30000)
            await guest.get_by_role('button', name='Ready', exact=True).click()
            await host.get_by_role('button', name='Ready', exact=True).click()
            await expect(host.get_by_role('button', name='Start →')).to_be_enabled(timeout=30000)
            await host.get_by_role('button', name='Start →').click()
            for page in (host, guest):
                await page.wait_for_function('uploadProof.room?.game.status === "playing"', timeout=30000)
                await choose_section_async(page, 'Sound')
                await page.get_by_role('button', name='Mute game', exact=True).click()
                await page.wait_for_function('Number(document.querySelector("canvas").dataset.frameCount) >= 200', timeout=30000)
                assert await page.evaluate('uploadProof.workers.filter(worker=>!worker.ended).at(-1).rom.magic') == [78, 69, 83, 26]
                assert await page.evaluate('uploadProof.workers.filter(worker=>!worker.ended).at(-1).rom.bytes') == FIXTURE.stat().st_size
            await host.get_by_role('button', name='Pause', exact=True).click()
            hashes = []
            for page in (host, guest):
                await page.wait_for_function('uploadProof.room?.game.status === "paused"')
                await page.evaluate('uploadProof.workers.filter(worker=>!worker.ended).at(-1).worker.postMessage({type:"state-hash",requestId:900005})')
                await page.wait_for_function('uploadProof.workers.filter(worker=>!worker.ended).at(-1).hash')
                hashes.append(await page.evaluate('uploadProof.workers.filter(worker=>!worker.ended).at(-1).hash'))
            assert hashes[0] == hashes[1], hashes
            await host.screenshot(path=str(output / 'zip-paired-play.png'))
            await host.get_by_role('button', name='Back to Main Page').click()
            await host.get_by_role('button', name='Close lobby', exact=True).click()
            await guest.locator('.rc-listing').wait_for()

            public = await context.new_page()
            await create_lobby(public, 'Open Arcade', fresh=True)
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
            assert not errors, errors
            await browser.close()

        result = {'result': 'pass', 'public_entrypoint': URL,
                  'cancel_keeps_lobby': True, 'failed_upload_retry': True,
                  'protected_requires_password': True, 'public_empty_lobby_listed': True,
                  'invalid_file_keeps_lobby': True, 'failed_replacement_keeps_game': True,
                  'custom_game_preview': True, 'zip_picker_and_drop': True,
                  'zip_title_uses_extracted_name': True, 'zip_failure_preserves_worker_preview_blob': True,
                  'zip_post_extraction_upload_retry': True, 'zip_paired_play_hash': hashes[0], 'included_game_after_creation': True,
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
