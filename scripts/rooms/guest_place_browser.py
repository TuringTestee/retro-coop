"""Prove Guest-place admission recovery through the public browser entry point."""
import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--output', default='/tmp/guest-place.json')
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
output = Path(args.output)
output.parent.mkdir(parents=True, exist_ok=True)
rom = (root / 'apps/client/dist/generated/diagnostic.nes').read_bytes()
started = time.monotonic()
def stage(name):
    print(f'guest-place: {name} at {time.monotonic() - started:.2f}s', flush=True)

service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=root, stdout=subprocess.PIPE, text=True)
try:
    url = json.loads(service.stdout.readline())['url']
    stage('server ready')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        errors = []
        host = browser.new_page(viewport={'width': 1280, 'height': 800})
        guest = browser.new_page(viewport={'width': 1280, 'height': 800})
        for tab in [host, guest]:
            tab.on('pageerror', lambda error: errors.append(str(error)))
            tab.set_default_timeout(8000)
        host.add_init_script('''
          window.placeProbe={dropRoom:false,dropAck:false,requestId:null,blocked:[],sockets:[]};
          const Native=WebSocket;
          window.WebSocket=class extends Native {
            constructor(...args){super(...args);placeProbe.sockets.push(this)}
            send(raw){const command=JSON.parse(raw);if(command.type==='guestPlace')placeProbe.requestId=command.requestId;return super.send(raw)}
            set onmessage(handler){super.onmessage=event=>{
              const message=JSON.parse(event.data);
              if(placeProbe.dropRoom&&message.type==='room'&&message.room.guestPlace==='closed'){
                placeProbe.blocked.push('room');return;
              }
              if(placeProbe.dropAck&&message.type==='result'&&message.requestId===placeProbe.requestId){
                placeProbe.blocked.push('result');return;
              }
              handler(event);
            }}
          };
        ''')
        guest.add_init_script('''
          window.invitationSockets=[];const Native=WebSocket;
          window.WebSocket=class extends Native {
            constructor(...args){super(...args);invitationSockets.push(this)}
          };
        ''')
        host.goto(url)
        host.get_by_role('button', name='Create game', exact=True).click()
        host.set_input_files('input[type=file]', {'name': 'guest-place.nes', 'mimeType': 'application/octet-stream', 'buffer': rom})
        host.get_by_role('button', name='Create room', exact=True).click()
        host.get_by_role('button', name='Close place', exact=True).wait_for(timeout=20000)
        stage('host room ready')
        invite = host.get_by_label('Room invitation', exact=True).input_value()
        code = host.locator('#room-heading').inner_text().split('·')[-1].strip()

        # Coordinator applies Close, but this browser misses both its room broadcast and result.
        host.evaluate('placeProbe.dropRoom=true;placeProbe.dropAck=true')
        host.get_by_role('button', name='Close place', exact=True).click()
        host.wait_for_function("placeProbe.blocked.includes('room')&&placeProbe.blocked.includes('result')")
        host.get_by_role('button', name='Retry Close', exact=True).wait_for(timeout=12000)
        assert host.get_by_text('Guest place: Open', exact=True).count() == 1
        host.screenshot(path=str(output.with_suffix('.lost-response.png')))
        stage('lost room and acknowledgement observed')
        host.evaluate('placeProbe.dropRoom=false;placeProbe.dropAck=false')
        host.get_by_role('button', name='Retry Close', exact=True).click()
        host.get_by_text('Guest place: Closed', exact=True).wait_for()
        assert host.get_by_role('button', name='Retry Close', exact=True).count() == 0

        guest.goto(url)
        guest.get_by_role('searchbox').fill(code)
        row = guest.locator('.room-list li').filter(has_text=code)
        row.get_by_text('Guest place closed').wait_for()
        assert row.get_by_role('button', name='Join', exact=True).count() == 0
        guest.goto(invite)
        guest.locator('.room-panel.invitation').get_by_text('Guest place closed').first.wait_for()
        assert guest.get_by_role('button', name='Join room', exact=True).count() == 0

        expect(host.get_by_role('button', name='Open place', exact=True)).to_be_enabled(timeout=8000)
        host.get_by_role('button', name='Open place', exact=True).click()
        guest.get_by_role('button', name='Join room', exact=True).wait_for()
        expect(host.get_by_role('button', name='Close place', exact=True)).to_be_enabled(timeout=8000)
        # A successful Close broadcast arrives but its acknowledgement is lost.
        host.evaluate('placeProbe.dropAck=true')
        host.get_by_role('button', name='Close place', exact=True).click()
        host.get_by_text('Guest place: Closed', exact=True).wait_for()
        guest.locator('.room-panel.invitation').get_by_text('Guest place closed').first.wait_for()
        host.wait_for_function("placeProbe.blocked.filter(item=>item==='result').length>=2")
        host.wait_for_function("document.querySelector('[data-testid=room-status]')?.textContent?.includes('did not respond')", timeout=12000)
        assert host.get_by_role('button', name='Retry Close', exact=True).count() == 0
        assert host.get_by_text('Guest place: Closed', exact=True).count() == 1
        host.screenshot(path=str(output.with_suffix('.applied-close.png')))
        stage('lost acknowledgement observed')
        host.evaluate('placeProbe.dropAck=false')

        guest.evaluate('invitationSockets.at(-1).close()')
        guest.get_by_role('button', name='Reconnect rooms', exact=True).wait_for()
        expect(host.get_by_role('button', name='Open place', exact=True)).to_be_enabled(timeout=12000)
        host.get_by_role('button', name='Open place', exact=True).click()
        assert guest.get_by_role('button', name='Join room', exact=True).count() == 0
        guest.get_by_role('button', name='Reconnect rooms', exact=True).click()
        guest.get_by_role('button', name='Join room', exact=True).wait_for(timeout=12000)
        guest.screenshot(path=str(output.with_suffix('.reconnected-invite.png')))
        stage('invitation reconnected')

        dismissed = browser.new_page(viewport={'width': 1280, 'height': 800})
        dismissed.on('pageerror', lambda error: errors.append(str(error)))
        dismissed.set_default_timeout(8000)
        dismissed.add_init_script('''window.dismissedSockets=[];const Native=WebSocket;
          window.WebSocket=class extends Native{constructor(...args){super(...args);dismissedSockets.push(this)}}''')
        dismissed.goto(invite)
        dismissed.get_by_role('button', name='Join room', exact=True).wait_for()
        dismissed.get_by_role('button', name='View public rooms', exact=True).click()
        dismissed.get_by_role('heading', name='Public rooms', exact=True).wait_for()
        dismissed.locator('.directory-title [role=status]').filter(has_text='Live').wait_for()
        stage('invitation dismissed')
        # Older invitation sockets can outlive the route switch briefly. Close every
        # open socket owned by this tab after the replacement client connects.
        # A previous client's Live label may remain for one render during the switch.
        dismissed.wait_for_function('dismissedSockets.some(socket => socket.readyState === WebSocket.OPEN)', timeout=12000)
        open_sockets = dismissed.evaluate('dismissedSockets.filter(socket => socket.readyState === 1).length')
        assert open_sockets >= 1, 'The dismissed tab has no live directory connection to fault'
        dismissed.evaluate('dismissedSockets.filter(socket => socket.readyState === 1).forEach(socket => socket.close())')
        dismissed.get_by_role('button', name='Retry', exact=True).wait_for()
        stage('dismissed tab disconnected')
        expect(host.get_by_role('button', name='Close place', exact=True)).to_be_enabled(timeout=8000)
        host.get_by_role('button', name='Close place', exact=True).click()
        expect(host.get_by_role('button', name='Open place', exact=True)).to_be_enabled(timeout=8000)
        host.get_by_role('button', name='Open place', exact=True).click()
        dismissed.get_by_role('button', name='Retry', exact=True).click()
        dismissed.locator('.directory-title [role=status]').filter(has_text='Live').wait_for()
        stage('dismissed tab reconnected')
        assert dismissed.locator('.room-panel.invitation').count() == 0
        assert dismissed.get_by_role('button', name='Join room', exact=True).count() == 0
        assert dismissed.get_by_test_id('room-notice').count() == 0
        dismissed.screenshot(path=str(output.with_suffix('.dismissed-invite.png')))

        guest.get_by_role('button', name='Join room', exact=True).click()
        guest.get_by_test_id('room-view').wait_for(state='attached')
        assert guest.get_by_text('You', exact=True).first.is_visible()
        assert not errors, errors
        result = {'result': 'pass', 'room_code': code, 'lost_ack_retry_preserved_close': True,
                  'applied_broadcast_with_lost_ack_preserved_close': True,
                  'disconnected_invitation_refreshed_and_joined': True,
                  'dismissed_invitation_stayed_dismissed_after_reconnect': True, 'page_errors': errors,
                  'seconds': round(time.monotonic() - started, 2)}
        output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        browser.close()
finally:
    service.terminate()
    service.wait(timeout=10)
