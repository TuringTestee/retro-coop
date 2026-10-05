#!/usr/bin/env python3
"""Exercise game selection, cancellation, and recovery after lobby creation."""

import asyncio
import json
import hashlib
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
            await context.add_init_script("""window.uploadProof={workers:[],room:null,requests:{}};
              const WorkerBase=Worker;window.Worker=class extends WorkerBase{
                constructor(...args){super(...args);const record={worker:this,id:uploadProof.workers.length,ended:false};uploadProof.workers.push(record);this.record=record;
                  this.addEventListener('message',({data})=>{if(data.type==='state-hash')record.hash=data.info;});}
                postMessage(data,...args){if(data.type==='load'){this.record.rom={bytes:data.rom.byteLength,magic:Array.from(new Uint8Array(data.rom,0,4))};crypto.subtle.digest('SHA-256',data.rom).then(hash=>this.record.rom.sha=Array.from(new Uint8Array(hash),byte=>byte.toString(16).padStart(2,'0')).join(''));}return super.postMessage(data,...args);}
                terminate(){this.record.ended=true;super.terminate();}
              };
              const uploadSend=XMLHttpRequest.prototype.send;
              XMLHttpRequest.prototype.send=function(...args){
                if(uploadProof.holdCancelledUpload){uploadProof.holdCancelledUpload=false;const cancelled=this.onabort;
                  this.onabort=event=>{uploadProof.oldAbortHeld=true;uploadProof.releaseOldAbort=()=>{cancelled.call(this,event);uploadProof.oldAbortDelivered=true;};};}
                return uploadSend.apply(this,args);
              };
              const Socket=WebSocket;window.WebSocket=class extends Socket{
                send(raw){const value=JSON.parse(raw);uploadProof.requests[value.requestId]=value.type;if(value.type==='confirmGameSelection'){uploadProof.confirmRequest=value.requestId;uploadProof.confirmRequests=(uploadProof.confirmRequests??0)+1;}
                  if(uploadProof.rejectClose&&value.type==='close'){uploadProof.rejectClose=false;uploadProof.closeHeld=true;uploadProof.releaseClose=()=>this.dispatchEvent(new MessageEvent('message',{data:JSON.stringify({type:'result',requestId:value.requestId,ok:false,error:'close_rejected'})}));return;}return super.send(raw);}
                constructor(...args){super(...args);this.addEventListener('message',event=>{const {data}=event;const message=JSON.parse(data);
                  if(uploadProof.holdConfirm&&message.type==='result'&&message.requestId===uploadProof.confirmRequest&&!event.confirmReleased){event.stopImmediatePropagation();uploadProof.confirmHeld=true;uploadProof.releaseConfirmFailure=()=>{const reply=JSON.parse(data);this.dispatchEvent(new MessageEvent('message',{data:JSON.stringify({type:'result',requestId:reply.requestId,ok:false,error:'game_selection_changed'})}));};uploadProof.releaseConfirm=()=>{uploadProof.holdConfirm=false;const released=new MessageEvent('message',{data});Object.defineProperty(released,'confirmReleased',{value:true});this.dispatchEvent(released);};return;}
if(message.type==='room')uploadProof.room=message.room;else if(message.type==='result'&&message.ok&&message.data?.room&&(uploadProof.requests[message.requestId]!=='confirmGameSelection'||uploadProof.room?.id===message.data.room.id))uploadProof.room=message.data.room;});}};
            """)
            context.on('page', lambda page: page.on('pageerror', lambda error: errors.append(str(error))))
            host = await context.new_page()
            await create_lobby(host, 'Private Upload', protected=True)

            async def close_pending_and_replace(name, data, outcome):
                # Hold a real reply, leave through the public dialog, and select in the new lobby.
                # Delivering an old error is a controlled protocol fixture, not a server failure claim.
                await host.evaluate("outcome=>{uploadProof.oldConfirm=outcome==='success'?uploadProof.releaseConfirm:uploadProof.releaseConfirmFailure;}", arg=outcome)
                await host.get_by_role('button', name='Back to Main Page', exact=True).click()
                await host.get_by_role('button', name='Close lobby', exact=True).click()
                await host.locator('.rc-listing').wait_for()
                await host.get_by_role('button', name='Host a new game').click()
                await host.get_by_role('button', name='Load NES game').wait_for(timeout=5000)
                await host.screenshot(path=str(output / f'zip-{name}-new-lobby.png'))
                await host.locator('.rc-trail .rc-header-edit').click()
                await host.get_by_role('textbox', name='Lobby name').fill('Private Upload')
                await host.get_by_role('textbox', name='Lobby name').press('Enter')
                await choose_section_async(host, 'Lobby')
                await host.get_by_role('button', name='Require password').click()
                await host.get_by_label('New lobby password').fill('blue-sky-room')
                await host.get_by_role('button', name='Save password').click()
                await host.get_by_role('button', name='Load NES game').click()
                await host.evaluate('uploadProof.holdConfirm=true;uploadProof.confirmHeld=false')
                async with host.expect_file_chooser() as chosen:
                    await host.get_by_role('button', name='Add game file', exact=True).click()
                await (await chosen.value).set_files({'name':name+'.nes','mimeType':'application/octet-stream','buffer':bytes(data)})
                await host.wait_for_function('uploadProof.confirmHeld')
                room_id = await host.evaluate('uploadProof.room.id')
                sha = await host.evaluate('uploadProof.room.fingerprint.romSha256')
                await host.evaluate('uploadProof.oldConfirm()')
                await host.evaluate('async()=>{await new Promise(requestAnimationFrame);}')
                assert await host.evaluate('uploadProof.room.id') == room_id
                assert await host.evaluate('uploadProof.room.fingerprint.romSha256') == sha
                await expect(host.locator('.rc-status-copy')).to_have_text('Finishing game selection…')
                await expect(host.get_by_role('button', name='Cancel selection')).to_be_disabled()
                await host.evaluate('uploadProof.releaseConfirm()')
                await expect(host.get_by_role('button', name='Ready', exact=True)).to_be_enabled()

            # Initial confirmation leaves through a successful Close; its late failure is obsolete.
            await host.get_by_role('button', name='Load NES game').click()
            await host.evaluate('uploadProof.holdConfirm=true;uploadProof.confirmHeld=false')
            async with host.expect_file_chooser() as chosen:
                await host.get_by_role('button', name='Add game file', exact=True).click()
            await (await chosen.value).set_files(str(FIXTURE))
            await host.wait_for_function('uploadProof.confirmHeld')
            await close_pending_and_replace('initial-confirmation', FIXTURE.read_bytes(), 'failure')
            await host.get_by_role('button', name='Back to Main Page', exact=True).click()
            await host.get_by_role('button', name='Close lobby', exact=True).click()
            await host.close()
            # Independent setup scenarios use fresh guest authority, keeping production upload limits intact.
            # Each departure/replacement assertion above still crosses the boundary in the same session.
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
                assert await host.evaluate('id=>!uploadProof.workers[id].ended', arg=old_worker)
                assert await host.evaluate('uploadProof.room.fingerprint.romSha256') == old_sha
                await expect(host.get_by_role('button', name='Ready', exact=True)).to_be_enabled()

            # Delay A's actual XHR cancellation while B waits for its real lobby confirmation.
            # Completion must stay bound to A, even though B is now the current candidate.
            release.clear()
            seen.clear()
            await host.route('**/rooms/*/rom', hold_upload)
            await host.evaluate('uploadProof.holdCancelledUpload=true')
            old_selection = bytearray(FIXTURE.read_bytes())
            old_selection[-1] ^= 2
            await selected_file(host, {'name':'cancelled-A.nes', 'mimeType':'application/octet-stream', 'buffer':bytes(old_selection)})
            await seen.wait()
            await host.get_by_role('button', name='Cancel selection').click()
            await host.wait_for_function('uploadProof.oldAbortHeld')
            release.set()
            await host.unroute('**/rooms/*/rom', hold_upload)
            await host.evaluate('uploadProof.holdConfirm=true;uploadProof.confirmHeld=false;uploadProof.confirmRequests=0')
            current_selection = bytearray(FIXTURE.read_bytes())
            current_selection[-1] ^= 3
            await selected_file(host, {'name':'replacement-B.nes', 'mimeType':'application/octet-stream', 'buffer':bytes(current_selection)})
            await host.wait_for_function('uploadProof.confirmHeld')
            current_worker = await host.evaluate('uploadProof.workers.filter(worker=>!worker.ended).at(-1).id')
            pending_guidance = await host.locator('.rc-status-copy').inner_text()
            await expect(host.get_by_role('button', name='Back to Main Page', exact=True)).to_be_enabled()
            await host.screenshot(path=str(output / 'zip-cancel-retry-confirming.png'))
            await host.evaluate('uploadProof.releaseOldAbort()')
            await host.wait_for_function('uploadProof.oldAbortDelivered')
            # Let promise completions cross both task and rendering boundaries before asserting isolation.
            await host.evaluate('async()=>{await new Promise(resolve=>setTimeout(resolve,0));await new Promise(requestAnimationFrame);}')
            await expect(host.get_by_role('button', name='Cancel selection')).to_be_disabled()
            assert await host.evaluate('id=>!uploadProof.workers[id].ended', arg=current_worker)
            # Withhold all three real confirmation replies through the declared 24-second budget.
            await expect(host.get_by_role('button', name='Retry selection', exact=True)).to_be_enabled(timeout=30000)
            uncertain_guidance = await host.locator('.rc-status-copy').inner_text()
            assert await host.evaluate('uploadProof.confirmRequests') == 3
            await host.screenshot(path=str(output / 'zip-confirmation-uncertain.png'))
            confirmation_headings = []
            for width, height in [(1280, 720), (760, 520)]:
                await host.set_viewport_size({'width':width, 'height':height})
                await expect(host.get_by_role('button', name='Retry selection', exact=True)).to_be_enabled()
                heading = await host.locator('.rc-game-progress strong').evaluate('''element => {const bounds=element.getBoundingClientRect(), container=element.parentElement.getBoundingClientRect(), style=getComputedStyle(element);return {text:element.textContent, fits:element.scrollWidth<=element.clientWidth+1&&element.scrollHeight<=element.clientHeight+1&&bounds.top>=container.top&&bounds.bottom<=container.bottom, wraps:style.whiteSpace!=='nowrap'&&style.textOverflow!=='ellipsis'};}''')
                confirmation_headings.append(heading)
                await host.screenshot(path=str(output / f'zip-confirmation-heading-{width}.png'))
            await host.set_viewport_size({'width':1280, 'height':720})
            # A retry is active work until its real reply or the same declared deadline.
            await host.evaluate('uploadProof.confirmHeld=false')
            await host.get_by_role('button', name='Retry selection', exact=True).click()
            await host.wait_for_function('uploadProof.confirmHeld')
            retry_guidance = await host.locator('.rc-status-copy').inner_text()
            retry_heading = await host.locator('.rc-game-progress strong').inner_text()
            await host.screenshot(path=str(output / 'zip-retry-pending.png'))
            assert retry_guidance == retry_heading == 'Finishing game selection…', (retry_guidance, retry_heading)
            assert await host.get_by_role('button', name='Retry selection', exact=True).count() == 0
            await expect(host.get_by_role('button', name='Cancel selection', exact=True)).to_be_disabled()
            await expect(host.get_by_role('button', name='Retry selection', exact=True)).to_be_enabled(timeout=30000)
            assert await host.locator('.rc-status-copy').inner_text() == uncertain_guidance
            assert await host.locator('.rc-game-progress strong').inner_text() == uncertain_guidance
            assert await host.evaluate('uploadProof.confirmRequests') == 6
            await host.evaluate('uploadProof.confirmHeld=false')
            await host.get_by_role('button', name='Retry selection', exact=True).click()
            await host.wait_for_function('uploadProof.confirmHeld')
            await expect(host.locator('.rc-status-copy')).to_have_text('Finishing game selection…')
            await expect(host.locator('.rc-game-progress strong')).to_have_text('Finishing game selection…')
            await close_pending_and_replace('replacement-B', current_selection, 'success')
            current_sha = hashlib.sha256(current_selection).hexdigest()
            await host.wait_for_function('sha=>uploadProof.workers.filter(worker=>!worker.ended).at(-1).rom.sha===sha&&uploadProof.room.fingerprint.romSha256===sha', arg=current_sha)
            await expect(host.locator('.rc-game-heading')).to_have_attribute('title', 'replacement-B')
            await expect(host.get_by_role('button', name='Ready', exact=True)).to_be_enabled()
            assert await host.get_by_role('button', name='Cancel selection').count() == 0
            await host.screenshot(path=str(output / 'zip-cancel-retry-installed.png'))
            assert 'selection' in pending_guidance.lower() and 'Retry game' not in pending_guidance, pending_guidance
            assert uncertain_guidance == 'Game selection needs confirmation. Choose Retry selection.', uncertain_guidance
            assert all(heading['text']==uncertain_guidance and heading['fits'] and heading['wraps'] for heading in confirmation_headings), confirmation_headings
            selected_title = 'replacement-B'

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
            await host.set_viewport_size({'width':760,'height':520})
            await host.evaluate('uploadProof.holdConfirm=true;uploadProof.confirmHeld=false')
            await pick_zip('outer-picker.zip', picker_zip)
            await host.wait_for_function('uploadProof.confirmHeld')
            await expect(host.get_by_role('button', name='Cancel selection')).to_be_disabled()
            back = host.get_by_role('button', name='Back to Main Page', exact=True)
            await back.focus()
            await host.keyboard.press('Enter')
            dialog = host.get_by_role('alertdialog', name='Close this lobby?')
            await expect(dialog.get_by_role('button', name='Stay', exact=True)).to_be_focused()
            for button in await dialog.get_by_role('button').all():
                box = await button.bounding_box()
                assert box and 0 <= box['x'] and box['x']+box['width'] <= 760 and 0 <= box['y'] and box['y']+box['height'] <= 520, box
            await host.screenshot(path=str(output / 'zip-confirm-back-narrow.png'))
            await host.evaluate('uploadProof.releaseConfirm()')
            await host.wait_for_function('id=>uploadProof.workers[id].ended', arg=old_worker)
            await host.keyboard.press('Enter')
            await expect(dialog).to_have_count(0)
            await expect(back).to_be_focused()
            await expect(host.locator('.rc-game-heading')).to_have_attribute('title', 'ZIP Picker Game', timeout=30000)
            await host.get_by_role('button', name='Change game').wait_for()
            await preview.wait_for()
            await host.screenshot(path=str(output / 'zip-picker-preview.png'))
            assert await host.evaluate('id=>uploadProof.workers[id].ended', arg=old_worker)

            await expect(host.get_by_role('button', name='Ready', exact=True)).to_be_enabled()
            assert await host.get_by_role('button', name='Cancel selection').count() == 0
            picker_sha = hashlib.sha256(replacement).hexdigest()
            await host.wait_for_function('sha=>uploadProof.workers.filter(worker=>!worker.ended).at(-1).rom.sha===sha&&uploadProof.room.fingerprint.romSha256===sha', arg=picker_sha)
            await host.screenshot(path=str(output / 'zip-confirm-stay-narrow.png'))
            await host.evaluate('uploadProof.holdConfirm=true;uploadProof.confirmHeld=false;uploadProof.rejectClose=true')
            picker_worker = await host.evaluate('uploadProof.workers.filter(worker=>!worker.ended).at(-1).id')
            drop_zip = archive('nested/ZIP Drop Game.nes', FIXTURE.read_bytes())
            await host.locator('.rc-game-zone').evaluate("""(node,bytes)=>{
              const transfer=new DataTransfer();transfer.items.add(new File([new Uint8Array(bytes)],'outer-drop.zip',{type:'application/zip'}));
              node.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer}));
            }""", list(drop_zip))
            await host.wait_for_function('uploadProof.confirmHeld')
            await back.focus()
            await host.keyboard.press('Enter')
            await expect(dialog.get_by_role('button', name='Stay', exact=True)).to_be_focused()
            await host.keyboard.press('Tab')
            await expect(dialog.get_by_role('button', name='Close lobby', exact=True)).to_be_focused()
            await host.keyboard.press('Enter')
            await host.wait_for_function('uploadProof.closeHeld')
            await host.evaluate('uploadProof.releaseConfirm()')
            await host.wait_for_function('id=>uploadProof.workers[id].ended', arg=picker_worker)
            await host.evaluate('uploadProof.releaseClose()')
            await expect(dialog.get_by_role('button', name='Close lobby', exact=True)).to_be_enabled()
            await dialog.get_by_text('Could not leave. Retry or stay in the lobby.', exact=True).wait_for()
            await host.screenshot(path=str(output / 'zip-confirm-rejected-close.png'))
            await host.keyboard.press('Shift+Tab')
            await expect(dialog.get_by_role('button', name='Stay', exact=True)).to_be_focused()
            await host.keyboard.press('Enter')
            await expect(dialog).to_have_count(0)
            await expect(back).to_be_focused()
            await expect(host.locator('.rc-game-heading')).to_have_attribute('title', 'ZIP Drop Game', timeout=30000)
            await host.get_by_role('button', name='Change game').wait_for()
            await preview.wait_for()
            await expect(host.get_by_role('button', name='Ready', exact=True)).to_be_enabled()
            assert await host.get_by_role('button', name='Cancel selection').count() == 0
            drop_sha = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
            await host.wait_for_function('sha=>uploadProof.workers.filter(worker=>!worker.ended).at(-1).rom.sha===sha&&uploadProof.room.fingerprint.romSha256===sha', arg=drop_sha)
            await host.screenshot(path=str(output / 'zip-confirm-rejected-stay.png'))
            await host.set_viewport_size({'width':1280,'height':720})
            await host.screenshot(path=str(output / 'zip-drop-preview.png'))
            # Successful Close created a new invitation; join the current public row, not the expired preview.
            await guest.goto(URL)
            await guest.locator('.rc-listing').wait_for()
            await guest.locator('.rc-lobby-card').filter(has_text='Private Upload').click()
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
            await host.wait_for_function('uploadProof.workers.every(worker=>worker.ended)')

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
                  'selection_pending_guidance': pending_guidance, 'selection_uncertain_guidance': uncertain_guidance, 'selection_confirmation_timeout_and_retry': True, 'retry_pending_guidance': retry_guidance, 'retry_timeout_then_success': True, 'confirmation_headings': confirmation_headings,
                  'cancelled_selection_late_response_isolated': True, 'cancelled_selection_retry_sha': current_sha, 'zip_initial_confirmation_close_new_lobby': True, 'zip_active_retry_close_new_lobby': True, 'zip_late_old_success_failure_isolated': True, 'zip_confirmation_back_stay': True, 'zip_confirmation_rejected_close_stay': True,
                  'zip_confirmation_narrow_keyboard_focus': True, 'zip_post_extraction_upload_retry': True, 'zip_paired_play_hash': hashes[0], 'included_game_after_creation': True,
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
