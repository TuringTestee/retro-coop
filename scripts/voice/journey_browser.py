"""Qualify decoded voice, mute and recovery during real two-player NES play.

Use --mode tabs for two pages sharing a browser context, or processes for two
independent Chromium processes. Fake devices prove media transport/decoding;
modeled playback/device failures do not establish physical-device quality.
Build with PUBLIC_CATALOG_GAMES=super-tilt-bro-pal before starting the gateway.
"""
import argparse
import contextlib
import hashlib
import json
import math
import struct
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
p = argparse.ArgumentParser(description=__doc__)
entry = p.add_mutually_exclusive_group(required=True)
entry.add_argument('--url')
entry.add_argument('--serve', action='store_true', help='Start the existing local browser gateway')
p.add_argument('--mode', choices=['tabs', 'processes'], default='tabs')
p.add_argument('--output', required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[2]
out = Path(a.output)
if (out / 'result.json').exists():
    p.error('--output needs a fresh directory')
out.mkdir(parents=True, exist_ok=True)
started = time.monotonic()
errors = []
ENERGY = "async()=>{let sum=0;for(const pc of pcs.filter(p=>p.connectionState==='connected'))for(const s of(await pc.getStats()).values())if(s.type==='inbound-rtp'&&s.kind==='audio')sum+=s.totalAudioEnergy??0;return sum;}"

def energy(page, active, sender=None):
    last = page.evaluate(ENERGY)
    start = last
    deadline = time.monotonic() + 8
    stable = time.monotonic()
    while time.monotonic() < deadline:
        page.wait_for_timeout(100)
        now = page.evaluate(ENERGY)
        if active and now > start + 1e-05:
            return now - start
        if now - last > 1e-06:
            stable = time.monotonic()
        if not active and time.monotonic() - stable > 1:
            return now - start
        last = now
    inspect = """async () => ({
      focus: document.hasFocus(), hidden: document.hidden,
      capture: captures.at(-1)?.getAudioTracks().map(track => ({
        enabled:track.enabled, muted:track.muted, state:track.readyState,
        settings:track.getSettings()
      })),
      audio:voiceAudio.map(audio=>({paused:audio.paused,muted:audio.muted,volume:audio.volume})),
      peers: await Promise.all(pcs.map(async pc=>({
        connection:pc.connectionState,
        senders:pc.getSenders().map(sender=>({id:sender.track?.id, enabled:sender.track?.enabled,state:sender.track?.readyState})),
        transceivers:pc.getTransceivers().map(t=>({direction:t.direction,current:t.currentDirection})),
        stats:[...(await pc.getStats()).values()].filter(s=>
          ['inbound-rtp','outbound-rtp','media-source'].includes(s.type) && s.kind==='audio')
      })))
    })"""
    diagnostics = {'receiver':page.evaluate(inspect)}
    if sender:
        diagnostics['sender'] = sender.evaluate(inspect)
    raise AssertionError(('audio active' if active else 'audio silent', start, last, diagnostics))

def voice(page):
    page.get_by_role('button', name='Voice', exact=True).click()

def mic(page, on):
    # This helper toggles explicit mute while the microphone is in open mode.
    page.get_by_role('button', name='Unmute microphone' if on else 'Mute microphone', exact=True).click()
    page.wait_for_function('enabled => captures.at(-1).getAudioTracks()[0].enabled === enabled', arg=on)

def leave(page):
    page.get_by_role('button', name='Back to Main Page', exact=True).click()
    dialog = page.get_by_role('alertdialog')
    dialog.wait_for()
    dialog.get_by_role('button', name='Close lobby' if page.get_by_role('heading', name='Close this lobby?').count() else 'Leave lobby', exact=True).click()
    page.locator('.rc-listing').wait_for()


def game_progress(page):
    before = int(page.locator('canvas').get_attribute('data-frame-count'))
    page.wait_for_function('before => Number(document.querySelector("canvas").dataset.frameCount) > before', arg=before)


def chat(sender, receiver, text):
    sender.get_by_label('Message everyone').fill(text)
    sender.get_by_role('button', name='Send', exact=True).click()
    receiver.get_by_text(text, exact=False).wait_for()


def stop_service(service):
    service.terminate()
    try:
        service.wait(timeout=5)
    except subprocess.TimeoutExpired:
        service.kill()
        service.wait()


def microphone_input(path):
    samples = [struct.pack('<h', int(6000 * math.sin(2 * math.pi * 440 * index / 48000))) for index in range(48000)]
    with wave.open(str(path), 'wb') as output:
        output.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
        output.writeframes(b''.join(samples))
    return path


with sync_playwright() as pw, contextlib.ExitStack() as s:
    if a.serve:
        server_log = s.enter_context((out / 'server.log').open('w'))
        service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=root,
                                   stdout=subprocess.PIPE, stderr=server_log, text=True)
        s.callback(stop_service, service)
        line = service.stdout.readline()
        if not line:
            raise RuntimeError('The local browser gateway did not start; inspect server.log')
        a.url = json.loads(line)['url']
    parsed_url = urlsplit(a.url)
    origin = f'{parsed_url.scheme}://{parsed_url.netloc}'
    tone = microphone_input(Path(s.enter_context(tempfile.TemporaryDirectory())) / 'voice.wav')

    def launch():
        b = pw.chromium.launch(channel='chromium', ignore_default_args=['--mute-audio'], args=['--use-fake-device-for-media-stream', f'--use-file-for-fake-audio-capture={tone}'])
        s.callback(b.close)
        return b
    b = launch()

    def page(browser):
        c = browser.new_context(permissions=['microphone', 'clipboard-read', 'clipboard-write'], viewport={'width': 1366, 'height': 768})
        s.callback(c.close)
        c.add_init_script(f'if (location.origin === {json.dumps(origin)}) {{\n'
                          + (root / 'scripts/voice/fixtures.js').read_text() + '\n}')
        c.on('page', lambda tab: tab.on('pageerror', lambda error: errors.append(str(error))))
        t = c.new_page()
        t.set_default_timeout(15000)
        t.goto(a.url)
        return t
    host = page(b)
    guest = host.context.new_page() if a.mode == 'tabs' else page(launch())
    guest.set_default_timeout(15000)
    guest.goto(a.url)
    host.get_by_role('button', name='Host a new game').click()
    host.get_by_role('button', name='Copy invite').click()
    invite = host.evaluate('navigator.clipboard.readText()')
    guest.goto(invite)
    guest.get_by_role('button', name='Join lobby', exact=True).click()
    host.locator('input[aria-label="NES cartridge file"]').set_input_files(str(root / 'apps/client/src/assets/super-tilt-bro-e.nes'))
    for t in [host, guest]:
        try:
            t.get_by_role('button', name='Ready', exact=True).wait_for(timeout=30000)
        except Exception:
            t.screenshot(path=str(out / 'load-failed.png'))
            print(t.locator('body').inner_text(), flush=True)
            raise
        t.get_by_role('button', name='Ready', exact=True).click()
    host.get_by_role('button', name='Start →', exact=True).click()
    for t in [host, guest]:
        t.wait_for_function('Number(document.querySelector("canvas").dataset.frameCount)>10', timeout=30000)
    frames = [int(t.locator('canvas').get_attribute('data-frame-count')) for t in [host, guest]]
    for t in [host, guest]:
        t.wait_for_function('captures.length===1&&captures[0].getAudioTracks()[0].readyState==="live"')
        assert not t.evaluate('captures[0].getAudioTracks()[0].enabled')
        t.get_by_role('button', name='Sound', exact=True).click()
        t.get_by_role('button', name='Mute game', exact=True).click()
        voice(t)
        # Keep incoming voice audible: zero element volume also suppresses
        # the browser's received-energy measurement.
        assert t.evaluate('voiceAudio.every(audio=>audio.volume===1)')
        t.screenshot(path=str(out / ('host-voice.png' if t == host else 'guest-voice.png')))
        t.get_by_label('Voice mode').select_option('open')
    mic(guest, False)
    result = {'mode': a.mode, 'browser': b.version,
              'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
              'tone_sha256':hashlib.sha256(tone.read_bytes()).hexdigest(),
              'capture_settings': {name:tab.evaluate('captures.at(-1).getAudioTracks()[0].getSettings()')
                                   for name,tab in (('host',host),('guest',guest))},
              'url': a.url, 'host_audio': energy(guest, True, sender=host)}
    for t in [host, guest]:
        t.context.new_cdp_session(t).send('Emulation.setFocusEmulationEnabled', {'enabled': False})
    target = guest
    if a.mode == 'processes':
        target = host.context.new_page()
        target.goto(a.url)
    host.bring_to_front()
    target.bring_to_front()
    host.wait_for_function('!document.hasFocus()')
    assert host.evaluate('captures.at(-1).getAudioTracks()[0].enabled')
    result['background_audio'] = energy(guest, True, sender=host)
    host.bring_to_front()
    mic(host, False)
    energy(guest, False)
    mic(guest, True)
    result['guest_audio'] = energy(host, True, sender=guest)
    mic(guest, False)
    mic(host, True)
    host.get_by_label('Voice mode').select_option('push')
    host.get_by_role('button', name='Back to Main Page').focus()
    host.keyboard.down('v')
    host.wait_for_function('captures.at(-1).getAudioTracks()[0].enabled')
    result['ptt_audio'] = energy(guest, True, sender=host)
    host.keyboard.up('v')
    energy(guest, False)
    host.keyboard.down('v')
    host.wait_for_function('captures.at(-1).getAudioTracks()[0].enabled')
    target.bring_to_front()
    host.wait_for_function('!document.hasFocus() && !captures.at(-1).getAudioTracks()[0].enabled')
    host.bring_to_front()
    assert not host.evaluate('captures.at(-1).getAudioTracks()[0].enabled')
    host.keyboard.up('v')
    result['focus_releases_push_to_talk'] = True
    chat(host, guest, 'voice keeps text working')
    host.get_by_label('Message everyone').focus()
    host.keyboard.down('v')
    host.wait_for_timeout(150)
    assert not host.evaluate('captures.at(-1).getAudioTracks()[0].enabled')
    host.keyboard.up('v')
    host.get_by_label('Voice mode').select_option('open')
    host.screenshot(path=str(out / 'voice.png'))
    host.get_by_role('button', name='Disable microphone', exact=True).click()
    host.context.clear_permissions()
    host.context.grant_permissions([])
    assert host.evaluate("async()=>(await navigator.permissions.query({name:'microphone'})).state") == 'denied'
    host.get_by_role('button', name='Enable voice', exact=True).click()
    host.get_by_text('Microphone access was denied.', exact=False).wait_for()
    host.screenshot(path=str(out / 'permission.png'))
    chat(host, guest, 'Text works while microphone permission is denied')
    for t in (host, guest):
        game_progress(t)
    host.context.grant_permissions(['microphone'])
    host.get_by_role('button', name='Try microphone again', exact=True).click()
    host.wait_for_function('captures.at(-1).getAudioTracks()[0].readyState==="live"')
    result['permission_retry'] = energy(guest, True, sender=host)
    host.get_by_role('button', name='Devices', exact=True).click()
    devices = host.get_by_role('combobox', name='Microphone')
    devices.wait_for()
    values = devices.locator('option').evaluate_all("o=>o.map(x=>x.value).filter(v=>v!=='default')")
    assert values
    devices.select_option(values[0])
    host.get_by_role('button', name='Unmute microphone', exact=True).wait_for()
    mic(host, True)
    result['device_replacement'] = energy(guest, True, sender=host)
    host.evaluate('modelMicrophoneRemoval(captures.at(-1).getAudioTracks()[0])')
    host.get_by_text('Microphone disconnected.', exact=False).wait_for()
    for t in (host, guest):
        game_progress(t)
    host.get_by_role('button', name='Try microphone again', exact=True).click()
    result['device_retry'] = energy(guest, True, sender=host)
    for t, n in zip([host, guest], frames):
        assert int(t.locator('canvas').get_attribute('data-frame-count')) > n, 'Voice recovery interrupted gameplay'
    result['game_continuity'] = True
    host.set_viewport_size({'width': 320, 'height': 700})
    host.get_by_role('combobox', name='Voice setting', exact=True).select_option('sound')
    host.evaluate('window.blockPlayback=true')
    host.get_by_role('button', name='Mute others', exact=True).click()
    host.get_by_role('button', name='Unmute others', exact=True).click()
    host.get_by_text('Remote voice playback was blocked.', exact=True).wait_for()
    chat(host, guest, 'Text works while voice playback is blocked')
    host.screenshot(path=str(out / 'compact-playback-recovery.png'))
    peer_count = host.evaluate('pcs.length')
    capture_count = host.evaluate('captures.length')
    for t in (host, guest):
        game_progress(t)
    result['compact_playback_retry_available'] = host.get_by_role('button', name='Enable voice sound', exact=True).count() > 0
    assert result['compact_playback_retry_available'], 'Compact voice has no playback retry'
    host.evaluate('window.blockPlayback=false')
    host.get_by_role('button', name='Enable voice sound', exact=True).click()
    host.get_by_text('Remote voice playback was blocked.', exact=True).wait_for(state='detached')
    assert host.evaluate('voiceAudio.at(-1).paused===false')
    assert host.evaluate('pcs.length') == peer_count
    assert host.evaluate('captures.length') == capture_count
    result['compact_playback_recovered'] = True
    host.screenshot(path=str(out / 'compact-playback-restored.png'))
    host.get_by_role('combobox', name='Voice setting', exact=True).select_option('mic')
    host.get_by_role('button', name='Disable voice', exact=True).click()
    host.evaluate('window.rejectAttachment=true')
    host.get_by_role('button', name='Enable voice', exact=True).click()
    host.get_by_role('button', name='Retry microphone', exact=True).wait_for()
    for t in (host, guest):
        game_progress(t)
    capture_count = host.evaluate('captures.length')
    host.evaluate('window.rejectAttachment=false')
    host.get_by_role('button', name='Retry microphone', exact=True).click()
    host.get_by_role('button', name='Retry microphone', exact=True).wait_for(state='detached')
    assert host.evaluate('captures.length') == capture_count
    assert host.evaluate('pcs.length') == peer_count
    result['compact_attachment_retry'] = energy(guest, True, sender=host)
    for t in (host, guest):
        game_progress(t)
    guest_captures = guest.evaluate('captures.length')
    leave(guest)
    guest.wait_for_function('captures.every(s=>s.getTracks().every(t=>t.readyState==="ended"))')
    guest.goto(invite)
    guest.get_by_role('button', name='Join lobby', exact=True).click()
    guest.wait_for_function('before => captures.length > before && captures.at(-1).getAudioTracks()[0].readyState === "live"', arg=guest_captures)
    assert not guest.evaluate('captures.at(-1).getAudioTracks()[0].enabled'), 'Rejoin must start with a fresh push-to-talk press.'
    voice(guest)
    guest.get_by_label('Voice mode').select_option('open')
    host.set_viewport_size({'width':1366, 'height':768})
    mic(host, False)
    result['rejoin_audio'] = energy(host, True, sender=guest)
    guest.screenshot(path=str(out / 'rejoined-voice.png'))
    leave(guest)
    guest.wait_for_function('captures.every(s=>s.getTracks().every(t=>t.readyState==="ended"))')
    leave(host)
    host.wait_for_function('captures.every(s=>s.getTracks().every(t=>t.readyState==="ended"))')
    result['leave_stops_capture'] = True
    assert not errors, errors
    result['page_errors'] = errors
    result['elapsed_seconds'] = round(time.monotonic() - started, 3)
    result['limitations'] = 'Generated fake microphone input; modeled device-ended callback and playback rejection. No physical unplug, acoustic-quality or independent-network claim.'
    (out / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
