"""Exercise private operator confirmation and public peer/voice removal feedback."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--output', default='operator.local.json')
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
output = Path(args.output)
started = time.monotonic()
errors = []
with tempfile.TemporaryDirectory(prefix='retro-operator-browser-') as directory:
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=root,
        env={**os.environ, 'TURN_URLS':'', 'TURN_SECRET':'', 'COORDINATOR_OPERATOR_DIR':directory},
        stdout=subprocess.PIPE, text=True)
    def request(command):
        result = subprocess.run(['node', '--input-type=module', '-e',
            "import {operatorRequest} from './apps/coordinator/src/operator.ts';const a=JSON.parse(process.argv[1]);console.log(JSON.stringify(await operatorRequest(a.directory,a.command)));",
            json.dumps({'directory':directory, 'command':command})], cwd=root, capture_output=True, text=True, check=True, timeout=5)
        return json.loads(result.stdout)
    def confirm(action, target, seconds=None):
        result = subprocess.run(['node', 'apps/coordinator/src/operator-cli.ts', directory, action, target] + ([str(seconds)] if seconds else []),
            input='CONFIRM\n', cwd=root, capture_output=True, text=True, check=True, timeout=5)
        assert 'Type CONFIRM' in result.stdout and 'Done.' in result.stdout
        return result.stdout
    try:
        url = json.loads(service.stdout.readline())['url']
        rom = (root / 'apps/client/dist/generated/diagnostic.nes').read_bytes()
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chromium', ignore_default_args=['--mute-audio'], args=['--use-fake-device-for-media-stream'])
            def page(address):
                tab = browser.new_page(viewport={'width':1280,'height':1000})
                tab.context.grant_permissions(['microphone'])
                tab.on('pageerror', lambda error: errors.append(str(error)))
                tab.add_init_script((root/'scripts/voice/fixtures.js').read_text())
                tab.goto(address)
                return tab
            def pair():
                host = page(url)
                assert host.get_by_role('button', name='Unmute', exact=True).get_attribute('aria-pressed') == 'true'
                host.set_input_files('input[type=file]', {'name':'fixture.nes','mimeType':'application/octet-stream','buffer':rom})
                host.get_by_test_id('room-view').wait_for()
                guest = page(host.get_by_label('Room invitation', exact=True).input_value())
                guest.get_by_role('button', name='Retry join / Join', exact=True).click()
                guest.get_by_test_id('room-view').wait_for()
                for tab in [host,guest]:
                    tab.locator('details.voice-disclosure').evaluate('(node)=>node.open=true')
                    tab.wait_for_function("document.querySelector('[data-testid=connection-status]').textContent.includes('Route: direct')")
                    tab.locator('.room-panel').get_by_label('Remote voice volume', exact=False).fill('0')
                    tab.get_by_role('button', name='Enable voice', exact=True).click()
                    tab.wait_for_function("captures.length>0 && captures.at(-1).getAudioTracks().some(t=>t.enabled&&t.readyState==='live')")
                for tab in [host,guest]:
                    tab.wait_for_function("async()=>[...((await pcs.at(-1).getStats()).values())].some(s=>s.type==='inbound-rtp'&&s.kind==='audio'&&s.totalAudioEnergy>0)")
                return host,guest
            def stopped(tab, message):
                tab.get_by_test_id('room-view').wait_for(state='detached')
                tab.get_by_test_id('room-status').filter(has_text=message).wait_for()
                tab.wait_for_function("pcs.every(pc=>pc.connectionState==='closed') && captures.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
            host,guest = pair()
            writes = host.evaluate('timelineWrites')
            host.screenshot(path=str(output.with_suffix('.before.png')), full_page=True, mask=[host.get_by_label('Room invitation', exact=True)])
            room = request({'type':'list'})['rooms'][0]
            removal = confirm('remove-room',room['id'])
            for tab in [host,guest]: stopped(tab,'An operator closed this room')
            assert host.evaluate('timelineWrites') == writes
            assert request({'type':'list'})['rooms'] == []
            host.screenshot(path=str(output.with_suffix('.removed.png')), full_page=True)
            host.close();guest.close()
            host,guest = pair()
            writes = host.evaluate('timelineWrites')
            subject = request({'type':'list'})['subjects'][0]
            assert subject['address'] == '127.0.0.1' and subject['connections'] == 2
            block = confirm('block-address',subject['id'],10)
            for tab in [host,guest]: stopped(tab,'Access is temporarily restricted')
            assert host.evaluate('timelineWrites') == writes
            host.screenshot(path=str(output.with_suffix('.blocked.png')), full_page=True)
            host.get_by_role('button', name='Retry directory', exact=True).click()
            host.locator('.directory-panel [role=status]').filter(has_text='Access is temporarily restricted').wait_for()
            host.get_by_test_id('room-status').filter(has_text='Access is temporarily restricted').wait_for()
            assert host.evaluate('timelineWrites') == writes
            fresh = page(url)
            fresh.get_by_test_id('room-status').filter(has_text='Access is temporarily restricted').wait_for()
            fresh.reload()
            fresh.get_by_test_id('room-status').filter(has_text='Access is temporarily restricted').wait_for()
            fresh.screenshot(path=str(output.with_suffix('.retry.png')), full_page=True)
            expiry_deadline = time.monotonic() + 15
            while any(s.get('blockedUntil') for s in request({'type':'list'})['subjects']):
                assert time.monotonic() < expiry_deadline, 'temporary block did not expire'
                time.sleep(0.05)
            fresh.get_by_role('button', name='Retry directory', exact=True).click()
            fresh.locator('.directory-panel [role=status]').filter(has_text='No public rooms yet').wait_for()
            fresh.get_by_test_id('room-status').filter(has_text='Access restored').wait_for()
            fresh.get_by_test_id('connection-status').filter(has_text='No peer connection').wait_for()
            fresh.set_input_files('input[type=file]', {'name':'fixture.nes','mimeType':'application/octet-stream','buffer':rom})
            fresh.get_by_test_id('room-view').wait_for()
            fresh.screenshot(path=str(output.with_suffix('.expired.png')), full_page=True, mask=[fresh.get_by_label('Room invitation', exact=True)])
            fresh.close()
            assert errors == []
            result = {'result':'pass','seconds':round(time.monotonic()-started,2),'browser':browser.version,
                'private_cli_confirmation':[removal,block],'room_removed_and_directory_cleared':True,
                'both_peer_connections_and_microphones_stopped':True,'no_local_reload_or_import':True,
                'explicit_operator_and_admission_feedback':True,'retry_fresh_reload_restriction_feedback':True,
                'expired_block_allows_fresh_session_and_room':True,'page_errors':errors}
            output.write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(result))
            browser.close()
    finally:
        service.terminate()
        try: service.wait(timeout=5)
        except subprocess.TimeoutExpired: service.kill();service.wait()
