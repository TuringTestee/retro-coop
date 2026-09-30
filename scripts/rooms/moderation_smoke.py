"""Delay an actual confirmed removal across member replacement, then verify teardown."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--output', default='moderation.local.json')
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
output = Path(args.output)
started = time.monotonic()
errors = []
service = subprocess.Popen(
    ['node', 'scripts/rooms/browser-server.ts'], cwd=root,
    env={**os.environ, 'TURN_URLS': '', 'TURN_SECRET': ''},
    stdout=subprocess.PIPE, text=True,
)
try:
    url = json.loads(service.stdout.readline())['url']
    rom = (Path(os.environ.get('RETRO_COOP_STATIC_ROOT', root/'apps/client/dist')) / 'generated/diagnostic.nes').read_bytes()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chromium', ignore_default_args=['--mute-audio'],
                                    args=['--use-fake-device-for-media-stream'])
        def page(address):
            tab = browser.new_page(viewport={'width':1280, 'height':1000})
            tab.context.grant_permissions(['microphone'])
            tab.on('pageerror', lambda error: errors.append(str(error)))
            tab.add_init_script((root / 'scripts/voice/fixtures.js').read_text())
            tab.add_init_script('''const SendSocket=WebSocket;
              window.WebSocket=class extends SendSocket {
                constructor(...args){super(...args);this.addEventListener('message',({data})=>{const event=JSON.parse(data);if(event.type==='room')window.moderationRoom=event.room;})}
                send(raw){const command=JSON.parse(raw);
                  if(window.holdRemoval && command.type==='memberRemove'){
                    window.delayedMembership=command.membership;window.releaseRemoval=()=>super.send(raw);return;
                  }
                  return super.send(raw);
                }
              };''')
            tab.goto(address)
            return tab
        def joined(tab):
            tab.get_by_role('button', name='Join room', exact=True).click()
            tab.get_by_test_id('room-view').wait_for(state='attached')
            open_room(tab)
        def connected(tab):
            tab.wait_for_function("document.querySelector('[data-testid=connection-status]').textContent.includes('direct route.')")
        def open_room(tab):
            panel = tab.locator('.room-panel')
            panel.wait_for(state='visible')
            return panel
        def open_connection(tab):
            panel = open_room(tab)
            connection = panel.locator('details.session-settings')
            if not connection.evaluate('(node)=>node.open'):
                connection.get_by_text('Connection and session settings', exact=True).click()
            panel.get_by_test_id('room-view').wait_for(state='visible')
            return panel
        def voice(tab):
            panel = open_room(tab)
            panel.locator('details.voice-disclosure').evaluate('(node)=>node.open=true')
            panel.get_by_label('Remote voice volume', exact=False).fill('10')
            panel.get_by_role('button', name='Enable voice', exact=True).click()
            tab.wait_for_function("captures.length>0 && captures.at(-1).getAudioTracks().some(t=>t.enabled&&t.readyState==='live')")
        host = page(url)
        assert host.get_by_role('button', name='Unmute', exact=True).count() == 0
        host.get_by_role('button', name='Create game', exact=True).click()
        host.set_input_files('input[type=file]', {'name':'fixture.nes', 'mimeType':'application/octet-stream', 'buffer':rom})
        host.get_by_role('button', name='Create room', exact=True).click()
        host.get_by_test_id('room-view').wait_for(state='attached')
        unmute = host.locator('.panel').get_by_role('button', name='Unmute', exact=True, include_hidden=True)
        assert unmute.get_attribute('aria-pressed') == 'true'
        invitation = host.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite")
        first = page(invitation)
        joined(first)
        connected(host)
        open_room(host)
        host.evaluate('window.holdRemoval=true')
        host.locator('[data-slot-id=slot-2]').get_by_role('button', name='Remove member', exact=True).click()
        host.locator('.room-slots').get_by_role('button', name='Confirm removal', exact=True).click()
        host.wait_for_function("typeof releaseRemoval==='function'")
        open_room(first).get_by_role('button', name='Leave room', exact=True).click()
        first.get_by_test_id('room-view').wait_for(state='detached')
        replacement = page(invitation)
        joined(replacement)
        host.wait_for_function("moderationRoom?.slots[1].member?.id&&moderationRoom.slots[1].member.id!==delayedMembership")
        replacement_membership=host.evaluate('moderationRoom.slots[1].member.id')
        for tab in [host, replacement]:
            connected(tab)
            voice(tab)
        # Await the actual getStats promise; wait_for_function treats a Promise as truthy.
        for tab in [host, replacement]:
            deadline = time.monotonic() + 8
            while True:
                audible = tab.evaluate("""async()=>{const stats=await pcs.at(-1).getStats();
                  return [...stats.values()].some(s=>s.type==='inbound-rtp'&&s.kind==='audio'&&s.totalAudioEnergy>0)
                    && voiceAudio.some(audio=>!audio.paused&&!audio.muted&&audio.volume===0.1);}""")
                if audible: break
                assert time.monotonic() < deadline, 'No received audio energy with audible playback'
                time.sleep(.05)
        host.screenshot(path=str(output.with_suffix('.before.png')), full_page=True,
                        mask=[host.get_by_label('Room invitation', exact=True)])
        host.evaluate('releaseRemoval();window.holdRemoval=false')
        open_connection(host).get_by_test_id('room-status').filter(has_text='That room has changed').wait_for()
        assert replacement.get_by_test_id('room-view').count() == 1
        assert host.evaluate('moderationRoom.slots[1].member.id')==replacement_membership
        for tab in [host, replacement]:
            assert tab.evaluate("pcs.at(-1).connectionState==='connected' && captures.at(-1).getAudioTracks().some(t=>t.readyState==='live')")
        host.screenshot(path=str(output.with_suffix('.stale.png')), full_page=True,
                        mask=[host.get_by_label('Room invitation', exact=True)])
        writes = host.evaluate('timelineWrites')
        host.locator('[data-slot-id=slot-2]').get_by_role('button', name='Remove member', exact=True).click()
        host.locator('.room-slots').get_by_role('button', name='Confirm removal', exact=True).click()
        replacement.get_by_test_id('room-view').wait_for(state='detached')
        for tab in [host, replacement]:
            tab.wait_for_function("pcs.every(pc=>pc.connectionState==='closed')")
        replacement.wait_for_function("captures.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
        assert host.evaluate("captures.at(-1).getAudioTracks().some(t=>t.readyState==='live'&&t.enabled)")
        release = replacement.get_by_role('alert').filter(has_text='The host removed you from this room.')
        release.wait_for(state='visible')
        replacement.screenshot(path=str(output.with_suffix('.removed.png')), full_page=True)
        release.get_by_role('button', name='Resume local game', exact=True).click()
        release.wait_for(state='detached')
        replacement.get_by_role('button', name='Join room', exact=True).click()
        replacement.get_by_test_id('room-status').filter(has_text='closed, unavailable').wait_for()
        assert replacement.get_by_test_id('room-view').count() == 0
        # Removing one membership does not ban the earlier guest who left voluntarily.
        first.goto(invitation)
        joined(first)
        connected(host)
        assert host.evaluate('timelineWrites') == writes
        assert host.evaluate("captures.length===1&&captures[0].getAudioTracks().some(t=>t.readyState==='live'&&t.enabled)")
        assert not errors, errors
        result = {'browser':browser.version, 'stale_confirmation_preserves_replacement':True,
                  'removed_pair_closed_and_removed_microphone_ended':True,'host_microphone_survives_member_removal':True,
                  'removed_guest_sees_release_and_resumes_local_game':True,
                  'removed_session_cannot_rejoin':True, 'former_guest_can_rejoin':True,
                  'removed_member_voice_requires_new_opt_in':True, 'host_worker_timeline_unchanged':writes,
                  'game_muted_in_app':True, 'remote_voice_volume_ten_percent_and_audio_received':True,
                  'page_errors':errors, 'seconds':round(time.monotonic()-started,2)}
        output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result))
        browser.close()
finally:
    service.terminate()
    service.wait(timeout=10)
