"""Delay an actual confirmed removal across guest replacement, then verify teardown."""
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
    rom = (root / 'apps/client/dist/generated/diagnostic.nes').read_bytes()
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
                send(raw){const command=JSON.parse(raw);
                  if(window.holdKick && command.type==='kick'){
                    window.releaseKick=()=>super.send(raw);return;
                  }
                  return super.send(raw);
                }
              };''')
            tab.goto(address)
            return tab
        def joined(tab):
            tab.get_by_role('button', name='Retry join / Join', exact=True).click()
            tab.get_by_test_id('room-view').wait_for()
        def connected(tab):
            tab.wait_for_function("document.querySelector('[data-testid=connection-status]').textContent.includes('Route: direct')")
        def voice(tab):
            tab.locator('details.voice-disclosure').evaluate('(node)=>node.open=true')
            tab.locator('.room-panel').get_by_label('Remote voice volume', exact=False).fill('0')
            tab.get_by_role('button', name='Enable voice', exact=True).click()
            tab.wait_for_function("captures.length>0 && captures.at(-1).getAudioTracks().some(t=>t.enabled&&t.readyState==='live')")
        host = page(url)
        assert host.get_by_role('button', name='Unmute', exact=True).get_attribute('aria-pressed') == 'true'
        host.set_input_files('input[type=file]', {'name':'fixture.nes', 'mimeType':'application/octet-stream', 'buffer':rom})
        host.get_by_test_id('room-view').wait_for()
        invitation = host.get_by_label('Room invitation', exact=True).input_value()
        first = page(invitation)
        joined(first)
        connected(host)
        host.get_by_text('Session settings', exact=True).click()
        host.on('dialog', lambda dialog: dialog.accept())
        host.evaluate('window.holdKick=true')
        host.get_by_role('button', name='Remove guest', exact=True).click()
        host.wait_for_function("typeof releaseKick==='function'")
        first.get_by_role('button', name='Cancel join', exact=True).click()
        first.get_by_test_id('room-view').wait_for(state='detached')
        replacement = page(invitation)
        joined(replacement)
        for tab in [host, replacement]:
            connected(tab)
            voice(tab)
        for tab in [host, replacement]:
            tab.wait_for_function("async()=>{const stats=await pcs.at(-1).getStats();return [...stats.values()].some(s=>s.type==='inbound-rtp'&&s.kind==='audio'&&s.totalAudioEnergy>0)}")
        host.screenshot(path=str(output.with_suffix('.before.png')), full_page=True,
                        mask=[host.get_by_label('Room invitation', exact=True)])
        host.evaluate('releaseKick();window.holdKick=false')
        host.get_by_test_id('room-status').filter(has_text='That guest has left or rejoined').wait_for()
        assert replacement.get_by_test_id('room-view').count() == 1
        for tab in [host, replacement]:
            assert tab.evaluate("pcs.at(-1).connectionState==='connected' && captures.at(-1).getAudioTracks().some(t=>t.readyState==='live')")
        host.screenshot(path=str(output.with_suffix('.stale.png')), full_page=True,
                        mask=[host.get_by_label('Room invitation', exact=True)])
        writes = host.evaluate('timelineWrites')
        host.get_by_role('button', name='Remove guest', exact=True).click()
        replacement.get_by_test_id('room-view').wait_for(state='detached')
        for tab in [host, replacement]:
            tab.wait_for_function("pcs.every(pc=>pc.connectionState==='closed') && captures.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
        replacement.get_by_role('button', name='Retry join / Join', exact=True).click()
        replacement.get_by_test_id('room-status').filter(has_text='closed, unavailable').wait_for()
        assert replacement.get_by_test_id('room-view').count() == 0
        # Removing one membership does not ban the earlier guest who left voluntarily.
        joined(first)
        connected(host)
        assert host.evaluate('timelineWrites') == writes
        assert host.evaluate("captures.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
        assert not errors, errors
        result = {'browser':browser.version, 'stale_confirmation_preserves_replacement':True,
                  'current_removal_closes_both_peers_and_microphones':True,
                  'removed_session_cannot_rejoin':True, 'former_guest_can_rejoin':True,
                  'voice_requires_new_opt_in':True, 'host_worker_timeline_unchanged':writes,
                  'game_muted_in_app':True, 'remote_voice_volume_zero_in_app':True,
                  'page_errors':errors, 'seconds':round(time.monotonic()-started,2)}
        output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result))
        browser.close()
finally:
    service.terminate()
    service.wait(timeout=10)
