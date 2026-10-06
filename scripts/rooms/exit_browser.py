#!/usr/bin/env python3
"""Prove that Main Page exits stop an active lobby, game, voice, and input."""

import json
import os
import subprocess
from pathlib import Path

from ui_helpers import choose_section, choose_audio
from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(os.environ.get('RETRO_COOP_STATIC_ROOT', ROOT / 'apps/client/dist'))
ROM = ROOT / 'spikes/d02/fixture.local.nes'
SCREENSHOTS = Path(os.environ['RETRO_EXIT_SCREENSHOT_DIR']) if 'RETRO_EXIT_SCREENSHOT_DIR' in os.environ else None


def instrument(page):
    page.add_init_script("""(() => {
      window.exitProof = {terminated: 0, posted: 0, captures: [], audioSources: []};
      const capture = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
      navigator.mediaDevices.getUserMedia = async (...args) => {
        const stream = await capture(...args);
        exitProof.captures.push(stream);
        return stream;
      };
      const createSource = AudioContext.prototype.createBufferSource;
      AudioContext.prototype.createBufferSource = function(...args) {
        const source = createSource.apply(this, args);
        const record = {stopped: false, ended: false};
        exitProof.audioSources.push(record);
        source.addEventListener('ended', () => { record.ended = true; });
        const stop = source.stop.bind(source);
        source.stop = (...args) => { record.stopped = true; return stop(...args); };
        return source;
      };
      const send = WebSocket.prototype.send;
      WebSocket.prototype.send = function(data) {
        if ((window.failClose && JSON.parse(data).type === 'close') ||
            (window.failLeave && JSON.parse(data).type === 'leave')) {
          throw Error('Injected exit failure');
        }
        return send.call(this, data);
      };
      const terminate = Worker.prototype.terminate;
      const post = Worker.prototype.postMessage;
      Worker.prototype.postMessage = function(...args) {
        exitProof.posted++;
        return post.apply(this, args);
      };
      Worker.prototype.terminate = function() {
        exitProof.terminated++;
        return terminate.call(this);
      };
    })()""")


def create_lobby(page, url, load_game=False):
    page.goto(url)
    page.get_by_role('button', name='Host a new game').click()
    page.get_by_role('button', name='Load NES game').wait_for(timeout=15000)
    if load_game:
        page.locator('input[aria-label="NES cartridge file"]').set_input_files(ROM)
        page.get_by_role('button', name='Change game').wait_for(timeout=30000)
    return page


def main():
    if SCREENSHOTS:
        SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                               env={**os.environ, 'COORDINATOR_EMPTY_OFFERS': 'super-tilt-bro-pal'},
                               stdout=subprocess.PIPE, text=True)
    try:
        url = json.loads(service.stdout.readline())['url']
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=[
                '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'])
            context = browser.new_context(permissions=['clipboard-read', 'clipboard-write', 'microphone'])
            host = context.new_page()
            instrument(host)
            create_lobby(host, url, load_game=True)
            host.get_by_role('button', name='Copy invite').click()
            invite = host.evaluate('navigator.clipboard.readText()')

            guest = browser.new_page()
            instrument(guest)
            guest.goto(invite)
            guest.get_by_role('button', name='Join lobby').click()
            expect(guest.get_by_role('button', name='Prepare', exact=True)).to_be_enabled(timeout=30000)
            expect(host.get_by_role('button', name='Prepare', exact=True)).to_be_enabled(timeout=30000)
            host.get_by_role('button', name='Prepare', exact=True).click()
            guest.get_by_role('button', name='Prepare', exact=True).click()
            expect(host.get_by_role('button', name='Start →')).to_be_enabled(timeout=30000)
            host.get_by_role('button', name='Start →').click()
            host.wait_for_function("Number(document.querySelector('canvas')?.dataset.frameCount)>30",
                                   timeout=30000)
            choose_audio(host, 'Game sound')
            host.get_by_role('button', name='Mute game').click()
            host.get_by_role('button', name='Unmute game').click()
            host.wait_for_function('exitProof.audioSources.length>0', timeout=15000)
            choose_audio(host, 'Voice')
            host.wait_for_function('exitProof.captures.some(stream=>stream.getTracks().some(track=>track.readyState==="live"))',
                                   timeout=15000)

            host.get_by_role('button', name='Back to Main Page').click()
            host.get_by_role('alertdialog', name='Close this lobby?').wait_for()
            host.get_by_role('button', name='Stay', exact=True).click()
            assert host.locator('[data-page="playing"]').count() == 1
            host.get_by_role('button', name='Back to Main Page').click()
            host.evaluate('window.failClose=true')
            host.get_by_role('button', name='Close lobby').click()
            host.get_by_role('alertdialog').get_by_text('Could not leave. Retry or stay in the lobby.').wait_for()
            assert host.locator('[data-page="playing"]').count() == 1
            assert host.evaluate('exitProof.terminated') == 0
            assert host.evaluate('exitProof.captures.some(stream=>stream.getTracks().some(track=>track.readyState==="live"))')
            if SCREENSHOTS:
                host.screenshot(path=str(SCREENSHOTS / 'host-close-retry.png'))

            guest.get_by_role('button', name='Back to Main Page').click()
            guest.evaluate('window.failLeave=true')
            guest.get_by_role('button', name='Leave lobby').click()
            guest.get_by_role('alertdialog').get_by_text('Could not leave. Retry or stay in the lobby.').wait_for()
            assert guest.locator('[data-page="playing"]').count() == 1
            guest.evaluate('window.failLeave=false')
            guest.get_by_role('button', name='Leave lobby').click()
            guest.locator('.rc-listing').wait_for(timeout=15000)
            assert guest.get_by_role('button', name='Resume').count() == 0

            host.evaluate('window.failClose=false')
            host.get_by_role('button', name='Close lobby').click()
            host.locator('.rc-listing').wait_for(timeout=15000)
            host.wait_for_function('exitProof.terminated >= 1', timeout=15000)
            host.wait_for_function("document.querySelector('canvas')?.dataset.frameCount === '0'")
            host.wait_for_function('exitProof.captures.every(stream=>stream.getTracks().every(track=>track.readyState==="ended"))')
            host.wait_for_function('exitProof.audioSources.every(source=>source.stopped||source.ended)')
            posted = host.evaluate('exitProof.posted')
            host.locator('canvas').evaluate('canvas=>canvas.focus()')
            host.keyboard.press('ArrowUp')
            assert host.evaluate('exitProof.posted') == posted
            assert host.locator('canvas').evaluate("""canvas=>[
              ...canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data]
                .every(value=>value===0)""")
            if SCREENSHOTS:
                host.screenshot(path=str(SCREENSHOTS / 'main-after-exit.png'))

            back = context.new_page()
            create_lobby(back, url)
            back.go_back()
            back.get_by_role('alertdialog', name='Close this lobby?').wait_for()
            back.get_by_role('button', name='Close lobby').click()
            back.locator('.rc-listing').wait_for(timeout=15000)
            print(json.dumps({'failed_host_close_keeps_game_and_voice': True,
                              'failed_member_leave_keeps_game': True,
                              'successful_exit_stops_worker_audio_voice_input_and_frame': True,
                              'browser_back_closes_lobby': True}))
            browser.close()
    finally:
        service.terminate()
        service.wait(timeout=10)


if __name__ == '__main__':
    main()
