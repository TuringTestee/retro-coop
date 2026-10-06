#!/usr/bin/env python3
"""A late observer with no peer link must not pause the host's live game."""

import argparse
from hashlib import sha256
import json
import re
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                               stdout=subprocess.PIPE, text=True)
    try:
        assert service.stdout
        url = json.loads(service.stdout.readline())['url']
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            errors = []

            def page(block_peer=False):
                tab = browser.new_page(viewport={'width': 1280, 'height': 800})
                tab.set_default_timeout(15_000)
                tab.on('pageerror', lambda error: errors.append(str(error)))
                if block_peer:
                    tab.add_init_script("window.RTCPeerConnection=class{constructor(){throw Error('Peer unavailable for observer isolation proof')}}")
                tab.add_init_script(path=ROOT / 'scripts/gameplay/fixture.js')
                tab.goto(url)
                tab.locator('.rc-listing').wait_for()
                return tab

            diagnostic = (ROOT / 'spikes/d02/fixture.local.nes').read_bytes()
            host = page()
            host.get_by_role('button', name='Host a new game').click()
            host.get_by_role('button', name='Load NES game').wait_for()
            slot = host.locator('[data-slot-id="slot-2"] .slot-row')
            slot.click()
            host.locator('[data-slot-id="slot-2"] .slot-menu').get_by_role('menuitem', name='Close slot').click()
            host.wait_for_function("proof.room?.slots.find(slot=>slot.id==='slot-2')?.open===false", polling=50)
            host.set_input_files('input[aria-label="NES cartridge file"]', {
                'name': 'release-host.nes', 'mimeType': 'application/octet-stream',
                'buffer': diagnostic})
            host.get_by_role('button', name='Prepare', exact=True).click(timeout=30_000)
            host.get_by_role('button', name='Start →').click(timeout=30_000)
            host.evaluate('releaseFrames()')
            host.wait_for_function('proof.frameCount>=30', timeout=30_000, polling=50)
            room_id = host.evaluate('proof.room.id')

            guest = page(block_peer=True)
            guest.locator('.rc-lobby-card').first.click()
            guest.wait_for_function("proof.room?.slots.find(s=>s.member?.id===proof.room.chatMembership)?.role==='observer'",
                                    timeout=30_000, polling=50)
            guest.wait_for_function("proof.room?.slots.find(s=>s.member?.id===proof.room.chatMembership)?.member.acquisition==='loaded'",
                                    timeout=30_000, polling=50)
            assert guest.get_by_role('button', name='Prepare', exact=True).count() == 0
            assert guest.get_by_role('button', name='Pause', exact=True).count() == 0
            auth = guest.evaluate("""() => ({roomId:proof.room.id,membership:proof.room.chatMembership,
                token:sessionStorage.getItem('retro-coop-guest')})""")
            assert auth['roomId'] == room_id
            request = Request(f"{url}/coordinator/rooms/{room_id}/rom",
                              headers={'Origin': url, 'Authorization': f"Bearer {auth['token']}",
                                       'X-Room-Membership': auth['membership']})
            with urlopen(request, timeout=5) as response:
                received = response.read()
                download = {'status': response.status, 'bytes': len(received),
                            'sha256': sha256(received).hexdigest()}
            assert download == {'status': 200, 'bytes': len(diagnostic),
                                'sha256': sha256(diagnostic).hexdigest()}, download
            before = host.evaluate('proof.frameCount')
            host.wait_for_function('count=>proof.frameCount>=count+30', arg=before,
                                   timeout=15_000, polling=50)
            assert host.locator('[data-page="playing"]').count() == 1
            guest_slot_id = guest.evaluate("""() => proof.room.slots.find(
                slot => slot.member?.id === proof.room.chatMembership)?.id""")
            assert guest_slot_id, 'The guest has no visible lobby slot.'
            guest_slot = guest.locator(f'.rc-players [data-slot-id="{guest_slot_id}"] .slot-row')
            assert guest_slot.is_visible(), 'The observer row disappeared during play.'
            assert guest.locator('.rc-players [data-testid="room-slot"]').count() == 5
            guest.screenshot(path=str(args.output / 'loaded-observer-connection-failed.png'))
            host.locator(f'[data-slot-id="{guest_slot_id}"] .slot-row').click()
            host.locator(f'[data-slot-id="{guest_slot_id}"] .slot-menu').get_by_role('menuitem', name=re.compile('Kick')).click()
            prompt = host.get_by_role('alertdialog', name=re.compile('Kick'))
            assert 'cannot rejoin' in prompt.inner_text()
            host.screenshot(path=str(args.output / 'kick-consequence.png'))
            prompt.get_by_role('button', name='Kick player').click()
            guest.locator('.rc-listing').wait_for()
            assert guest.locator('canvas').get_attribute('data-frame-count') == '0'
            guest.locator('.rc-lobby-card').first.click()
            guest.get_by_text('This lobby is closed, unavailable, or the invitation has expired.').wait_for()
            assert guest.locator('[data-page="playing"]').count() == 0
            assert not errors, errors
            result = {'result': 'pass', 'source': subprocess.check_output(
                ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'browser': browser.version, 'gateway_download': download,
                'journey': 'host keeps playing after late observer loses peer; kick consequence is shown; removed guest cannot rejoin',
                'errors': errors}
            (args.output / 'observer-isolation.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result, indent=2))
            browser.close()
    finally:
        service.terminate()
        try:
            service.wait(timeout=5)
        except subprocess.TimeoutExpired:
            service.kill()
            service.wait()


if __name__ == '__main__':
    main()
