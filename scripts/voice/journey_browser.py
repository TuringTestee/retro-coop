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
import re
import struct
import sys
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
sys.path.insert(0, str(root / 'scripts/rooms'))
from ui_helpers import choose_panel, choose_section
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


def recovery_bounds(page):
    # CSS changes before React receives the media event; measure the settled variant.
    result = page.wait_for_function("""() => {
      const node=document.querySelector('.rc-voice-recovery');
      const error=node?.querySelector('p'),button=node?.querySelector('button');
      if(!node?.isConnected||!error||!button)return false;
      const settings=node.closest('section'),selector=settings?.querySelector('.rc-settings-select');
      const voice=node.closest('.rc-voice-settings');
      if(!selector||!voice)return false;
      const compact=getComputedStyle(selector).display!=='none';
      if(voice.classList.contains('rc-voice-compact')!==compact)return false;
      const rect = item => {const r=item.getBoundingClientRect();return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height}};
      const range=document.createRange();range.selectNodeContents(error);
      return {container:rect(node.closest('.rc-tool-body')),error:rect(error),button:rect(button),
              text:[...range.getClientRects()].map(r=>({left:r.left,top:r.top,right:r.right,bottom:r.bottom})),
              viewport:{right:innerWidth,bottom:innerHeight}};
    }""").json_value()
    box = result['container']
    for rect in [result['error'], result['button'], *result['text']]:
        assert rect['left'] >= box['left'] - 1 and rect['top'] >= box['top'] - 1, result
        assert rect['right'] <= min(box['right'], result['viewport']['right']) + 1, result
        assert rect['bottom'] <= min(box['bottom'], result['viewport']['bottom']) + 1, result
    return result


def voice(page):
    choose_section(page, 'Voice')

def mic_control(page, on):
    voice(page)
    selector = page.get_by_role('combobox', name='Voice setting', exact=True)
    if selector.is_visible():
        selector.select_option('mic')
    return page.get_by_role('button', name=('Unmute ' if on else 'Mute ') + ('mic' if selector.is_visible() else 'microphone'), exact=True)

def mic(page, on):
    # This helper toggles explicit mute while the microphone is in open mode.
    mic_control(page, on).click()
    page.wait_for_function('enabled => captures.at(-1).getAudioTracks()[0].enabled === enabled', arg=on)

def leave(page):
    page.get_by_role('button', name='Back to Main Page', exact=True).click()
    dialog = page.get_by_role('alertdialog')
    dialog.wait_for()
    dialog.get_by_role('button', name='Close lobby' if page.get_by_role('heading', name='Close this lobby?').count() else 'Leave lobby', exact=True).click()
    page.locator('.rc-listing').wait_for()


def prepare_players(host, guest):
    """Observe shared prerequisites and each Ready acknowledgment before Start."""
    deadline = time.monotonic() + 30
    recoveries = []
    def remaining_ms():
        remaining = int((deadline - time.monotonic()) * 1000)
        assert remaining > 0, 'Players did not become Ready within the shared setup deadline'
        return remaining
    try:
        while time.monotonic() < deadline:
            for name, tab in [('host', host), ('guest', guest)]:
                tab.wait_for_function("""() => {
                  const room=window.lobbyState;
                  return room?.fingerprint && room.matches &&
                    room.slots.filter(slot=>slot.member&&slot.role!=='observer')
                      .every(slot=>slot.member.connected&&slot.member.acquisition==='loaded') &&
                    room.peers.every(peer=>peer.status==='connected');
                }""", timeout=remaining_ms())
                if tab.get_by_role('button', name='Cancel Ready', exact=True).count():
                    continue
                action = tab.get_by_role('button', name=re.compile(r'^(Ready|Try Ready again)$'))
                if action.inner_text() == 'Try Ready again':
                    recoveries.append({'visitor': name, 'action': 'Try Ready again'})
                before = tab.evaluate('readyAttempts.length')
                action.click(timeout=remaining_ms())
                result = tab.wait_for_function("""before => {
                  const attempt=readyAttempts[before];
                  return attempt?.result;
                }""", arg=before, timeout=remaining_ms()).json_value()
                if not result['ok']:
                    assert result['error'] in ['game_prerequisites', 'room_changed', 'stale_controllers'], result
                    recoveries.append({'visitor': name, 'error': result['error']})
            if host.get_by_role('button', name='Start →', exact=True).count():
                return recoveries
        raise AssertionError('Players did not become Ready within the shared setup deadline')
    except Exception:
        for name, tab in [('host', host), ('guest', guest)]:
            (out / f'{name}-ready-failed.json').write_text(json.dumps({
                'body': tab.locator('body').inner_text(),
                'room': tab.evaluate('lobbyState'),
                'attempts': tab.evaluate('readyAttempts'),
                'peers': tab.evaluate('pcs.map(pc=>({connection:pc.connectionState,ice:pc.iceConnectionState}))')
            }, indent=2))
            tab.screenshot(path=str(out / f'{name}-ready-failed.png'))
        raise


def game_progress(page):
    before = int(page.locator('canvas').get_attribute('data-frame-count'))
    page.wait_for_function('before => Number(document.querySelector("canvas").dataset.frameCount) > before', arg=before)


def chat(sender, receiver, text):
    previous = {}
    for page in (sender, receiver):
        navigation = page.get_by_role('navigation', name='Lobby sections')
        if navigation.is_visible():
            previous[page] = navigation.locator('[aria-current=page]').inner_text()
        choose_panel(page, 'Chat')
    sender.get_by_label('Message everyone').fill(text)
    sender.get_by_role('button', name='Send', exact=True).click()
    receiver.get_by_text(text, exact=False).wait_for()
    for page, panel in previous.items():
        choose_panel(page, panel)


def stop_service(service):
    service.terminate()
    try:
        service.wait(timeout=5)
    except subprocess.TimeoutExpired:
        service.kill()
        service.wait()


def microphone_input(path, frequency):
    samples = [struct.pack('<h', int(6000 * math.sin(2 * math.pi * frequency * index / 48000))) for index in range(48000)]
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
    input_dir = Path(s.enter_context(tempfile.TemporaryDirectory()))
    microphone_inputs = []

    def launch():
        # Independent visitors need independent stimuli: identical input and
        # received playback can legitimately be removed as echo.
        frequency = 440 + 137 * len(microphone_inputs)
        tone = microphone_input(input_dir / f'voice-{len(microphone_inputs)}.wav', frequency)
        microphone_inputs.append({'frequency_hz': frequency, 'sha256': hashlib.sha256(tone.read_bytes()).hexdigest()})
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
    ready_recoveries = prepare_players(host, guest)
    host.get_by_role('button', name='Start →', exact=True).click()
    for t in [host, guest]:
        t.wait_for_function('Number(document.querySelector("canvas").dataset.frameCount)>10', timeout=30000)
    frames = [int(t.locator('canvas').get_attribute('data-frame-count')) for t in [host, guest]]
    for t in [host, guest]:
        t.wait_for_function('captures.length===1&&captures[0].getAudioTracks()[0].readyState==="live"')
        assert not t.evaluate('captures[0].getAudioTracks()[0].enabled')
        choose_section(t, 'Sound')
        t.get_by_role('button', name='Mute game', exact=True).click()
        voice(t)
        # Keep incoming voice audible: zero element volume also suppresses
        # the browser's received-energy measurement.
        assert t.evaluate('voiceAudio.every(audio=>audio.volume===1)')
        t.screenshot(path=str(out / ('host-voice.png' if t == host else 'guest-voice.png')))
        t.get_by_label('Voice mode').select_option('open')
    mic(guest, False)
    result = {'mode': a.mode, 'ready_recoveries': ready_recoveries, 'browser': b.version,
              'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
              'microphone_inputs':microphone_inputs,
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
    host.get_by_role('button', name=re.compile(r'^Disable (microphone|voice)$')).click()
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
    # Revoking an origin permission also ends the other capture in shared tabs.
    # Recover that actual state through its visible action before later two-way proof.
    if guest.evaluate('captures.at(-1).getAudioTracks()[0].readyState === "ended"'):
        guest.get_by_role('button', name='Try microphone again', exact=True).click()
        guest.wait_for_function('captures.at(-1).getAudioTracks()[0].readyState === "live"')
        mic(guest, False)
        result['other_capture_permission_retry'] = True
    voice(host)
    selector = host.get_by_role('combobox', name='Voice setting', exact=True)
    if selector.is_visible():
        selector.select_option('devices')
    else:
        host.get_by_role('button', name='Devices', exact=True).click()
    devices = host.get_by_role('combobox', name='Microphone')
    devices.wait_for()
    values = devices.locator('option').evaluate_all("o=>o.map(x=>x.value).filter(v=>v!=='default')")
    assert values
    devices.select_option(values[0])
    mic_control(host, True).wait_for()
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
    voice(host)
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
    result['compact_playback_bounds'] = recovery_bounds(host)
    host.evaluate('window.blockPlayback=false')
    host.get_by_role('button', name='Enable voice sound', exact=True).click()
    host.get_by_text('Remote voice playback was blocked.', exact=True).wait_for(state='detached')
    assert host.evaluate('voiceAudio.at(-1).paused===false')
    mic(guest, True)
    result['compact_playback_retry_audio'] = energy(host, True, sender=guest)
    mic(guest, False)
    assert host.evaluate('pcs.length') == peer_count
    assert host.evaluate('captures.length') == capture_count
    result['compact_playback_recovered'] = True
    host.screenshot(path=str(out / 'compact-playback-restored.png'))
    host.get_by_role('combobox', name='Voice setting', exact=True).select_option('mic')
    host.get_by_role('button', name='Disable voice', exact=True).click()
    host.evaluate('window.blockPlayback=true;window.rejectAttachment=true')
    host.get_by_role('button', name='Enable voice', exact=True).click()
    # Both errors must select one matching message/action, in both layouts.
    host.get_by_text('Remote voice playback was blocked.', exact=True).wait_for()
    for width in (1366, 320):
        host.set_viewport_size({'width': width, 'height': 700})
        voice(host)
        host.get_by_role('button', name='Enable voice sound', exact=True).wait_for()
        assert ' '.join(host.locator('.rc-voice-recovery').inner_text().split()) == 'Remote voice playback was blocked. Enable voice sound'
        recovery_bounds(host)
    result['overlapping_recovery_matches_both_layouts'] = True
    host.screenshot(path=str(out / 'overlapping-playback-recovery.png'))
    host.evaluate('window.blockPlayback=false')
    host.get_by_role('button', name='Enable voice sound', exact=True).click()
    host.get_by_role('button', name='Retry microphone', exact=True).wait_for()
    assert 'A peer microphone connection failed.' in host.locator('.rc-voice-recovery').inner_text()
    host.screenshot(path=str(out / 'overlapping-microphone-recovery.png'))
    result['compact_attachment_bounds'] = recovery_bounds(host)
    for t in (host, guest):
        game_progress(t)
    capture_count = host.evaluate('captures.length')
    host.evaluate('window.rejectAttachment=false')
    host.get_by_role('button', name='Retry microphone', exact=True).click()
    host.get_by_role('button', name='Retry microphone', exact=True).wait_for(state='detached')
    assert host.evaluate('captures.length') == capture_count
    assert host.evaluate('pcs.length') == peer_count
    result['compact_attachment_retry'] = energy(guest, True, sender=host)
    host.evaluate('modelMicrophoneRemoval(captures.at(-1).getAudioTracks()[0]);window.blockPlayback=true')
    host.get_by_role('combobox', name='Voice setting', exact=True).select_option('sound')
    host.get_by_role('button', name='Mute others', exact=True).click()
    host.get_by_role('button', name='Unmute others', exact=True).click()
    host.get_by_text('Remote voice playback was blocked.', exact=True).wait_for()
    host.evaluate('window.blockPlayback=false')
    host.get_by_role('button', name='Enable voice sound', exact=True).click()
    host.get_by_role('button', name='Try microphone again', exact=True).wait_for()
    assert 'Microphone disconnected.' in host.locator('.rc-voice-recovery').inner_text()
    host.get_by_role('combobox', name='Voice setting', exact=True).select_option('devices')
    assert host.get_by_role('button', name='Try microphone again', exact=True).count() == 1
    host.get_by_role('combobox', name='Voice setting', exact=True).select_option('mic')
    assert host.get_by_role('button', name='Try microphone again', exact=True).count() == 1
    host.get_by_role('button', name='Try microphone again', exact=True).click()
    result['overlapping_device_ended_retry'] = energy(guest, True, sender=host)

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
