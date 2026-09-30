"""Verify public discovery, exact room identity, privacy, and stale recovery in browsers."""
import argparse
import os
import json
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--chrome', action='store_true')
parser.add_argument('--output', default='directory.local.json')
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
output = Path(args.output)
started = time.monotonic()
service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=root, stdout=subprocess.PIPE, text=True)
try:
    url = json.loads(service.stdout.readline())['url']
    rom = (Path(os.environ.get('RETRO_COOP_STATIC_ROOT', root/'apps/client/dist')) / 'generated/diagnostic.nes').read_bytes()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(ignore_default_args=['--mute-audio'], **({'channel': 'chrome'} if args.chrome else {}))
        errors, received, sent = [], [], []
        def page():
            tab = browser.new_page(viewport={'width': 1280, 'height': 800})
            tab.on('pageerror', lambda error: errors.append(str(error)))
            tab.on('websocket', lambda socket: socket.on('framereceived', lambda raw: received.append(json.loads(raw))))
            tab.on('websocket', lambda socket: socket.on('framesent', lambda raw: sent.append(json.loads(raw))))
            tab.add_init_script('window.directorySockets=[];const OriginalSocket=WebSocket;window.WebSocket=class extends OriginalSocket{constructor(...args){super(...args);directorySockets.push(this)}}')
            tab.goto(url)
            tab.locator('[data-directory-status=live]').wait_for()
            return tab
        def session_settings(tab):
            options = tab.locator('details.session-settings')
            if not options.evaluate('(node)=>node.open'):
                options.locator(':scope > summary').click()
            return options
        viewer = page()
        viewer.get_by_text('No public rooms right now.', exact=True).wait_for()
        chooser = viewer.get_by_role('button', name='Create game', exact=True)
        chooser.focus()
        assert chooser.evaluate('(node)=>node===document.activeElement')
        hosts = [page(), page()]
        codes, room_ids = [], []
        for host in hosts:
            host.get_by_role('button', name='Create game', exact=True).click()
            host.set_input_files('input[type=file]', {'name': 'PRIVATE-DIRECTORY-GAME.nes', 'mimeType': 'application/octet-stream', 'buffer': rom})
            host.get_by_role('button', name='Create room', exact=True).click()
            host.get_by_role('button', name='Start game', exact=True).wait_for()
            settings = session_settings(host)
            settings.get_by_label('Room name', exact=True).fill('Duplicate Arcade')
            settings.get_by_role('button', name='Save room name', exact=True).click()
            host.get_by_role('heading', name='Duplicate Arcade', exact=False).wait_for()
            viewer.wait_for_function("count => document.querySelectorAll('.room-list li').length === count", arg=len(codes)+1)
            rooms = next(event['rooms'] for event in reversed(received) if event.get('type') == 'directory')
            current = next(room for room in rooms if room['label'] == 'Duplicate Arcade' and room['id'] not in room_ids)
            codes.append(current['code'])
            room_ids.append(current['id'])
        assert len(set(codes)) == 2
        search = viewer.get_by_role('searchbox', name='Search room, game, host, or code')
        search.fill('duplicate')
        viewer.wait_for_function("document.querySelectorAll('.room-list li').length===2")
        search.fill(codes[0].lower())
        target = viewer.locator(f'.room-list li[data-room-id="{room_ids[0]}"]')
        assert target.count() == 1
        join = target.get_by_role('button', name='Join', exact=True)
        join.focus()
        settings = session_settings(hosts[0])
        settings.get_by_label('Room name', exact=True).fill('Renamed Arcade')
        settings.get_by_role('button', name='Save room name', exact=True).click()
        viewer.get_by_text('Renamed Arcade', exact=True).wait_for()
        assert join.evaluate('(node)=>node===document.activeElement')
        observer = page()
        observer.get_by_role('searchbox', name='Search room, game, host, or code').fill(codes[0])
        observer.locator(f'.room-list li[data-room-id="{room_ids[0]}"]').get_by_role('button', name='Join').wait_for()
        join.click()
        viewer.get_by_role('button', name='Leave room', exact=True).wait_for()
        assert viewer.locator('canvas').get_attribute('data-frame-count') == '0'
        assert 'You' in viewer.locator('[data-slot-id=slot-2] [data-slot-region=identity]').inner_text()
        observed = observer.locator(f'.room-list li[data-room-id="{room_ids[0]}"]')
        observed.get_by_text('3 places open', exact=True).wait_for()
        assert observed.get_by_role('button', name='Join', exact=True).count() == 1
        assert "Host's game file" in observed.inner_text() and 'download' in observed.inner_text()
        viewer.get_by_role('button', name='Ready', exact=True).wait_for(timeout=30000)
        viewer.locator('[data-slot-id=slot-2] [data-slot-region=status]').get_by_text('Not ready',exact=True).wait_for()
        # All five physical slots admit members; only the sixth visitor is excluded.
        invite = f"{url}/#invite={hosts[0].get_by_test_id('room-view').get_attribute('data-invite')}"
        extra = []
        for _ in range(3):
            member = page();member.goto(invite)
            member.get_by_role('button', name='Join room', exact=True).click()
            member.get_by_test_id('room-view').wait_for(state='attached')
            assert member.get_by_test_id('room-slot').count() == 5
            extra.append(member)
        observed.get_by_text('Full', exact=True).wait_for()
        assert observed.get_by_role('button', name='Join', exact=True).count() == 0
        for member in extra:
            member.get_by_role('button', name='Leave room', exact=True).click()
            member.get_by_test_id('room-view').wait_for(state='detached')
            member.close()
        viewer.get_by_role('button', name='Leave room', exact=True).click()
        viewer.locator('.room-panel').wait_for(state='detached')
        observer.get_by_role('button', name='Join', exact=True).wait_for()
        settings.get_by_role('button', name='Protect room', exact=True).click()
        settings.get_by_label('New room password', exact=True).fill('arcade passphrase')
        settings.get_by_role('button', name='Protect room', exact=True).last.click()
        observed.get_by_text('Password required', exact=False).wait_for()
        observed.get_by_role('button', name='Join', exact=True).click()
        observer.get_by_role('dialog', name='Join Renamed Arcade').get_by_label('Room password').wait_for()
        observer.get_by_role('dialog', name='Join Renamed Arcade').get_by_role('button', name='Back').click()
        assert observed.get_by_role('button', name='Join', exact=True).evaluate('(node)=>node===document.activeElement')
        observer.get_by_role('searchbox').fill('')
        assert observer.get_by_role('searchbox').input_value() == ''
        observer.screenshot(path=str(output.with_suffix('.live.png')))
        offline = page()
        offline.locator('.room-list li').first.wait_for()
        offline.evaluate('directorySockets.forEach(socket=>socket.close())')
        offline.get_by_role('button', name='Retry', exact=True).wait_for()
        assert offline.get_by_role('button', name='Retry', exact=True).count() == 1
        assert offline.get_by_test_id('room-notice').count() == 0
        assert offline.locator('.directory-title [role=status]').inner_text() == ''
        assert offline.locator('.room-list li').count() >= 1
        assert offline.locator('.room-list li button').count() == 0
        offline.screenshot(path=str(output.with_suffix('.stale.png')))
        offline.get_by_role('button', name='Retry', exact=True).click()
        offline.locator('[data-directory-status=live]').wait_for()
        assert not errors, errors
        public = [event['rooms'] for event in received if event.get('type') == 'directory']
        public += [event['data']['directory'] for event in received if event.get('type') == 'result' and event.get('ok') and 'directory' in event['data']]
        assert public
        allowed = {'id', 'label', 'host', 'visibility', 'code', 'status', 'occupancy', 'catalogId', 'romBytes', 'openSlots'}
        assert all(set(room) <= allowed and room['visibility'] in {'public', 'protected'} for snapshot in public for room in snapshot)
        assert any(room['visibility'] == 'protected' and room['id'] == room_ids[0] for snapshot in public for room in snapshot)
        assert not any('arcade passphrase' in json.dumps(frame) for frame in received)
        assert not any('PRIVATE-DIRECTORY' in json.dumps(frame) for frame in sent)
        result = {'result': 'pass', 'duplicate_codes': codes, 'search_and_live_focus': True, 'reserved_member_leaves_three_joinable_slots': True, 'five_members_fill_capacity_without_sixth_join': True, 'exact_guest_file': True, 'protected_room_search': True, 'stale_rows_have_no_actions_and_retry': True, 'metadata_only': True, 'private_filenames_not_sent': True, 'page_errors': errors, 'elapsedSeconds': round(time.monotonic() - started, 2)}
        output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        browser.close()
finally:
    service.terminate()
    service.wait(timeout=5)
