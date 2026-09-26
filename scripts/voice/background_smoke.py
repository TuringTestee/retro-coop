"""Prove focus-independent voice through real tabs and independent browser processes."""
import argparse
import contextlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time
import wave

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
ENERGY = """async () => [...(await pcs.at(-1).getStats()).values()]
 .filter(s => s.type === 'inbound-rtp' && s.kind === 'audio')
 .reduce((sum, s) => sum + (s.totalAudioEnergy ?? 0), 0)"""


def write_tone(path):
    # Original generated sound, not microphone samples. Chromium loops this fake-device input.
    with wave.open(str(path), 'wb') as output:
        output.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
        output.writeframes(b''.join(struct.pack('<h', int(6000 * math.sin(2 * math.pi * 440 * i / 48000)
                                                        * (0.6 + 0.4 * math.sin(2 * math.pi * 3 * i / 48000))))
                                   for i in range(48000)))
    return path


def audio_arrives(receiver):
    before = receiver.evaluate(ENERGY)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        current = receiver.evaluate(ENERGY)
        if current > before + 0.00001:
            return current - before
        receiver.wait_for_timeout(100)
    stats = receiver.evaluate("async () => [...(await pcs.at(-1).getStats()).values()].filter(s=>s.type==='inbound-rtp'&&s.kind==='audio').map(s=>({packets:s.packetsReceived,bytes:s.bytesReceived,energy:s.totalAudioEnergy,samples:s.totalSamplesReceived}))")
    raise AssertionError(f'no new decoded audio energy arrived from background sender: {stats}')


def audio_stops(receiver):
    # Drain already queued packets, then observe a full second of stable decoded energy.
    deadline = time.monotonic() + 5
    last = receiver.evaluate(ENERGY)
    stable_since = time.monotonic()
    while time.monotonic() < deadline:
        receiver.wait_for_timeout(100)
        current = receiver.evaluate(ENERGY)
        if current - last > 0.000001:
            stable_since = time.monotonic()
        if time.monotonic() - stable_since >= 1:
            return
        last = current
    raise AssertionError('received audio energy continued after explicit microphone mute')


def run(playwright, url, mode, output, headed):
    errors = []
    with contextlib.ExitStack() as stack:
        tone = write_tone(Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='retro-voice-'))) / 'tone.wav')
        def launch():
            browser = playwright.chromium.launch(
                channel='chromium', headless=not headed,
                ignore_default_args=['--mute-audio', '--disable-background-timer-throttling',
                                     '--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding'],
                args=['--use-fake-device-for-media-stream', f'--use-file-for-fake-audio-capture={tone}'],
            )
            stack.callback(browser.close)
            context = browser.new_context(permissions=['microphone'], viewport={'width': 1280, 'height': 900})
            context.add_init_script(f'if (location.origin === {json.dumps(url)}) {{\n'
                                    + (ROOT / 'scripts/voice/fixtures.js').read_text() + '\n}')
            context.on('page', lambda page: page.on('pageerror', lambda error: errors.append(str(error))))
            return browser, context

        browser, context = launch()
        host = context.new_page()
        host.goto(url)
        host.get_by_role('button', name='Create game', exact=True).click()
        host.set_input_files('input[type=file]', str(ROOT / 'apps/client/dist/generated/diagnostic.nes'))
        host.get_by_role('button', name='Create room', exact=True).click()
        host.get_by_test_id('room-view').wait_for(state='attached')
        invitation = host.get_by_label('Room invitation', exact=True).input_value()
        if mode == 'same-browser-tabs':
            with host.expect_popup() as popup:
                host.evaluate("window.open('about:blank')")
            guest = popup.value
            guest.goto(invitation)
        else:
            _, other_context = launch()
            guest = other_context.new_page()
            guest.goto(invitation)
        for tab in [host, guest]:
            # Playwright enables focus emulation. Disable it so target activation produces real focus events.
            tab.context.new_cdp_session(tab).send('Emulation.setFocusEmulationEnabled', {'enabled': False})
        guest.get_by_role('button', name='Join room', exact=True).click()
        for tab in [host, guest]:
            tab.wait_for_function("pcs.at(-1)?.connectionState === 'connected'")
            tab.bring_to_front()
            tab.locator('details.voice-disclosure > summary').click()
            tab.get_by_label('Remote voice volume', exact=False).fill('10')
            tab.get_by_role('button', name='Enable voice', exact=True).click()
            tab.wait_for_function('captures.at(-1)?.getAudioTracks()[0].enabled')

        # The identical generated inputs can cancel each other through echo cancellation.
        # Keep the receiver explicitly muted while measuring the background sender.
        guest.get_by_role('button', name='Mute microphone', exact=True).click()

        # With separate processes, background the sender using an unrelated page in its own browser.
        focus_target = guest
        if mode == 'independent-processes':
            with host.expect_popup() as popup:
                host.evaluate("window.open('about:blank')")
            focus_target = popup.value
        def background_host():
            focus_target.bring_to_front()
            host.wait_for_function('!document.hasFocus()')

        host.bring_to_front()
        host.get_by_role('button', name='Mute microphone', exact=True).wait_for()
        background_host()
        assert host.evaluate('captures.at(-1).getAudioTracks()[0].enabled'), 'tab focus muted open microphone'
        background_energy = audio_arrives(guest)
        host.bring_to_front()
        host.get_by_role('button', name='Mute microphone', exact=True).click()
        background_host()
        assert not host.evaluate('captures.at(-1).getAudioTracks()[0].enabled')
        audio_stops(guest)
        host.bring_to_front()
        host.get_by_role('button', name='Unmute microphone', exact=True).click()
        background_host()
        unmuted_energy = audio_arrives(guest)
        host.screenshot(path=str(output / f'{mode}-background.png'))

        host.bring_to_front()
        host.get_by_label('Voice mode', exact=True).select_option('push')
        for key in ['Space', 'Enter']:
            host.get_by_role('button', name='Hold to talk', exact=True).focus()
            host.keyboard.down(key)
            host.wait_for_function('captures.at(-1).getAudioTracks()[0].enabled')
            background_host()
            host.wait_for_function('!captures.at(-1).getAudioTracks()[0].enabled')
            host.bring_to_front()
            # Repeating down without keyup generates a real repeat event through the browser.
            host.keyboard.down(key)
            host.wait_for_timeout(150)
            assert not host.evaluate('captures.at(-1).getAudioTracks()[0].enabled'), 'old held key resumed transmission'
            assert host.get_by_role('button', name='Mute microphone', exact=True).is_visible()
            host.keyboard.up(key)
            host.keyboard.down(key)
            host.wait_for_function('captures.at(-1).getAudioTracks()[0].enabled')
            host.keyboard.up(key)
            host.wait_for_function('!captures.at(-1).getAudioTracks()[0].enabled')
        host.get_by_label('Voice mode', exact=True).select_option('open')

        # The same session reaches shared play; focus changes preserve voice and frame progress.
        guest.bring_to_front()
        guest.get_by_role('button', name='Prepare to play', exact=True).click()
        host.bring_to_front()
        host.locator('[data-slot-id="slot-2"] [data-slot-region="status"]').get_by_text('Ready', exact=True).wait_for(timeout=30000)
        host.get_by_role('button', name='Start game', exact=True).click()
        for tab in [host, guest]:
            tab.locator('.voice-card').wait_for()
            tab.bring_to_front()
            tab.locator('.voice-card').get_by_role('button', name='Mute microphone' if tab == host else 'Unmute microphone', exact=True).wait_for()
        host.bring_to_front()
        frame = int(host.get_by_test_id('game-frame').inner_text().split()[0])
        background_host()
        playing_energy = audio_arrives(guest)
        host.wait_for_function("f => Number(document.querySelector('[data-testid=game-frame]').textContent.split(' ')[0]) >= f + 30", arg=frame)
        host.screenshot(path=str(output / f'{mode}-playing.png'))
        guest.get_by_role('button', name='Leave room', exact=True).click()
        guest.get_by_role('button', name='Confirm leave', exact=True).click()
        guest.wait_for_function("captures.every(s => s.getTracks().every(t => t.readyState === 'ended'))")
        assert host.evaluate("captures.at(-1).getTracks().every(t => t.readyState === 'live' && t.enabled)")
        host.get_by_role('button', name='Leave room', exact=True).click()
        host.get_by_role('button', name='Confirm leave', exact=True).click()
        host.wait_for_function("captures.every(s => s.getTracks().every(t => t.readyState === 'ended'))")
        assert not errors, errors
        return {'mode': mode, 'browser': browser.version, 'background_energy_delta': background_energy,
                'unmuted_energy_delta': unmuted_energy, 'playing_energy_delta': playing_energy,
                'mute_silence_observed': True, 'push_release_and_fresh_press': True,
                'background_shared_frames': 30, 'departing_member_stops_capture': True, 'other_member_leave_preserves_capture': True, 'host_leave_stops_capture': True, 'page_errors': errors}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--headed', action='store_true')
    parser.add_argument('--output', default='/tmp/retro-coop-background-voice')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    server = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                              env={**os.environ, 'TURN_URLS': '', 'TURN_SECRET': ''}, stdout=subprocess.PIPE, text=True)
    try:
        url = json.loads(server.stdout.readline())['url']
        with sync_playwright() as playwright:
            results = [run(playwright, url, mode, output, args.headed)
                       for mode in ['same-browser-tabs', 'independent-processes']]
        result = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  'headed': args.headed, 'seconds': round(time.monotonic() - started, 2), 'results': results}
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
    finally:
        server.terminate()
        server.wait(timeout=10)
