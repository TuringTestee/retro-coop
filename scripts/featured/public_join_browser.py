"""Prove included, custom public, and password protected rooms through independent browser sessions."""
import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[2]
started = time.monotonic()
service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=root,
    env={**os.environ, 'COORDINATOR_EMPTY_OFFERS': 'super-tilt-bro-pal,from-below-1.0'}, stdout=subprocess.PIPE, text=True)
try:
    url = json.loads(service.stdout.readline())['url']
    diagnostic = (root / 'apps/client/dist/generated/diagnostic.nes').read_bytes()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(ignore_default_args=['--mute-audio'])
        errors, wire = [], []
        def page(address=url):
            tab = browser.new_page(viewport={'width': 1280, 'height': 800})
            tab.on('pageerror', lambda error: errors.append(str(error)))
            tab.on('websocket', lambda socket: socket.on('framesent', lambda raw: wire.append(raw)))
            tab.add_init_script(path=root / 'scripts/gameplay/fixture.js')
            tab.goto(address)
            return tab
        def code(tab):
            return tab.locator('#room-heading').inner_text().split(' · ')[-1]
        def join_code(tab, value):
            tab.get_by_role('searchbox', name='Search room, game, host, or code').fill(value)
            row = tab.locator('.room-list li').filter(has_text=value)
            row.get_by_role('button', name='Join', exact=True).click()
            return row
        def shared(host, guest):
            guest.get_by_role('button', name='Ready', exact=True).click()
            try:
                host.wait_for_function("proof.room?.game.ready.includes(proof.room.slots[1].member?.id)", timeout=30000, polling=50)
            except Exception:
                print(json.dumps({'host':host.evaluate('({room:proof.room,text:document.body.innerText})'),'guest':guest.evaluate('({room:proof.room,text:document.body.innerText})')}),flush=True)
                raise
            host.get_by_role('button', name='Ready', exact=True).click()
            host.get_by_role('button', name='Start game', exact=True).click()
            for tab in (host, guest):
                try:
                    tab.wait_for_function("proof.room?.established && proof.room?.game?.status==='playing'", timeout=30000, polling=50)
                except Exception:
                    print(json.dumps({'host': host.evaluate('({room:proof.room,game:proof.room?.game,status:document.querySelector("[data-testid=room-status]")?.textContent})'), 'guest': guest.evaluate('({room:proof.room,game:proof.room?.game,status:document.querySelector("[data-testid=room-status]")?.textContent})')}), flush=True)
                    raise
            for tab in (host, guest):
                tab.evaluate('releaseFrames()')
            for tab in (host, guest):
                tab.wait_for_function('proof.frameCount>=120 && proof.hashes.some(hash=>hash.frame===120)', timeout=30000, polling=50)
            hashes = [tab.evaluate('proof.hashes.find(hash=>hash.frame===120)') for tab in (host, guest)]
            assert hashes[0] and hashes[0] == hashes[1]
            return {'frames': [tab.evaluate('proof.frameCount') for tab in (host, guest)], 'matching_hash': hashes[0]}
        host = page()
        offer = host.locator('.room-list li').filter(has_text='Super Tilt Bro').filter(has_text='5 places open').first
        offer.get_by_role('button', name='Join as host').click()
        host.get_by_role('button', name='Start game', exact=True).wait_for()
        included_code = code(host)
        friend = page()
        row = friend.locator('.room-list li').filter(has_text=included_code)
        assert '4 places open' in row.inner_text()
        assert 'P1/P2 controllers · included' in row.inner_text()
        friend.screenshot(path=str(args.output / 'included-directory.png'))
        file_choosers = []
        friend.on('filechooser', lambda chooser: file_choosers.append(chooser))
        row.get_by_role('button', name='Join', exact=True).click()
        included = shared(host, friend)
        assert not file_choosers
        assert friend.evaluate('proof.room.catalogId') == 'super-tilt-bro-pal'
        friend.screenshot(path=str(args.output / 'included-playing.png'))
        custom_host = page()
        custom_host.get_by_role('button', name='Create game', exact=True).click()
        custom_host.set_input_files('input[type=file]', {'name': 'PRIVATE-PUBLIC-HOST.nes', 'mimeType': 'application/octet-stream', 'buffer': diagnostic})
        custom_host.get_by_role('button', name='Create room', exact=True).click()
        custom_host.get_by_role('button', name='Start game', exact=True).wait_for()
        custom_guest = page()
        join_code(custom_guest, code(custom_host))
        custom_guest.get_by_role('button', name='Ready', exact=True).wait_for()
        assert custom_guest.get_by_role('button', name='Choose matching NES file').count() == 0
        custom_guest.screenshot(path=str(args.output / 'custom-ready.png'))
        custom = shared(custom_host, custom_guest)
        protected_host = page()
        protected_host.get_by_role('button', name='Create game', exact=True).click()
        protected_host.get_by_label('Room access').select_option('protected')
        protected_host.get_by_label('Room password').fill('featured-room-password')
        protected_host.set_input_files('input[type=file]', {'name': 'PRIVATE-PROTECTED-HOST.nes', 'mimeType': 'application/octet-stream', 'buffer': diagnostic})
        protected_host.get_by_role('button', name='Create room', exact=True).click()
        protected_host.get_by_role('button', name='Start game', exact=True).wait_for()
        invitation = protected_host.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite")
        listing = page()
        listing.get_by_role('searchbox').fill(protected_host.locator('#room-heading').inner_text().split(' · ')[0])
        protected_row = listing.locator('.room-list li').filter(has_text=protected_host.locator('#room-heading').inner_text())
        protected_row.get_by_text('Password required', exact=False).wait_for()
        invited = page(invitation)
        invited.get_by_role('button', name='Join room', exact=True).click()
        invited.get_by_label('Room password').fill('featured-room-password')
        invited.get_by_role('dialog').get_by_role('button', name='Join room', exact=True).click()
        invited.get_by_role('button', name='Ready', exact=True).wait_for()
        assert invited.get_by_role('button', name='Choose matching NES file').count() == 0
        protected = shared(protected_host, invited)
        assert not errors, errors
        wire_text = '\n'.join(wire)
        assert 'PRIVATE-' not in wire_text
        assert len(diagnostic) > max(map(len, wire), default=0)
        result = {'result': 'pass', 'included': included, 'included_join_opened_no_file_picker': True, 'custom_public': custom, 'protected_invite': protected, 'filenames_absent_from_wire': True, 'diagnostic_sha256': hashlib.sha256(diagnostic).hexdigest(), 'browser': browser.version, 'seconds': round(time.monotonic() - started, 2), 'page_errors': errors}
        (args.output / 'public-built-in-join.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
        browser.close()
finally:
    service.terminate()
    service.wait(timeout=5)
