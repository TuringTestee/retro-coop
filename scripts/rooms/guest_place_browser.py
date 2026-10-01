"""Prove five-slot admission, removal, and recovery through the public browser entry point."""
import argparse
import os
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
rom = (Path(os.environ.get('RETRO_COOP_STATIC_ROOT', root/'apps/client/dist')) / 'generated/diagnostic.nes').read_bytes()
started = time.monotonic()
def stage(name):
    print(f'five-slot-admission: {name} at {time.monotonic() - started:.2f}s', flush=True)

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
          window.slotProbe={dropRoom:false,dropAck:false,requestId:null,blocked:[],sockets:[]};
          const Native=WebSocket;
          window.WebSocket=class extends Native {
            constructor(...args){super(...args);slotProbe.sockets.push(this)}
            send(raw){const command=JSON.parse(raw);if(command.type==='slotAvailability')slotProbe.requestId=command.requestId;return super.send(raw)}
            set onmessage(handler){super.onmessage=event=>{
              const message=JSON.parse(event.data);
              if(slotProbe.dropRoom&&message.type==='room'&&message.room.slots.find(slot=>slot.id==='slot-2')?.open===false){
                slotProbe.blocked.push('room');return;
              }
              if(slotProbe.dropAck&&message.type==='result'&&message.requestId===slotProbe.requestId){
                slotProbe.blocked.push('result');return;
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
        slot=host.locator('[data-slot-id=slot-2]')
        def manage(slot_id):
            row=host.locator(f'[data-slot-id={slot_id}]')
            actions=row.locator('[data-slot-action]')
            expect(actions).to_be_enabled(timeout=20000)
            return actions

        def slot_action(slot_id, name):
            manage(slot_id).select_option('close' if name=='Close slot' else 'open')

        manage('slot-2').locator('option[value="close"]').wait_for(state='attached',timeout=20000)
        assert host.get_by_test_id('room-slot').count()==5
        for slot_id in ['slot-3','slot-4','slot-5']:
            slot_action(slot_id, 'Close slot')
            manage(slot_id).locator('option[value="open"]').wait_for(state='attached')
        stage('host room ready')
        invite = host.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite")
        room_name = host.locator('#room-heading').inner_text().strip()

        # Coordinator applies Close, but this browser misses both its room broadcast and result.
        host.evaluate('slotProbe.dropRoom=true;slotProbe.dropAck=true')
        slot_action('slot-2', 'Close slot')
        host.wait_for_function("slotProbe.blocked.includes('room')&&slotProbe.blocked.includes('result')")
        host.get_by_text('The change was not confirmed.', exact=False).wait_for(timeout=12000)
        assert manage('slot-2').locator('option[value="close"]').count()==1
        host.screenshot(path=str(output.with_suffix('.lost-response.png')))
        stage('lost room and acknowledgement observed')
        host.evaluate('slotProbe.dropRoom=false;slotProbe.dropAck=false')
        # Retrying the stale revision must not invert the authoritative closed slot.
        slot_action('slot-2', 'Close slot')
        host.get_by_text('The change was not confirmed.',exact=False).wait_for()
        host.evaluate('slotProbe.sockets.at(-1).close()')
        host.get_by_role('button',name='Reconnect rooms',exact=True).click()
        manage('slot-2').locator('option[value="open"]').wait_for(state='attached')

        guest.goto(url)
        guest.get_by_role('searchbox').fill(room_name)
        row = guest.locator('.room-list li').filter(has_text=room_name)
        row.get_by_text('Full',exact=True).wait_for()
        assert row.get_by_role('button', name='Join', exact=True).count() == 0
        guest.goto(invite)
        guest.locator('.room-panel.invitation').get_by_text('0 open places',exact=False).first.wait_for()
        assert guest.get_by_role('button', name='Join room', exact=True).count() == 0

        slot_action('slot-2', 'Open slot')
        guest.get_by_role('button', name='Join room', exact=True).wait_for()
        # A successful Close broadcast arrives but its acknowledgement is lost.
        host.evaluate('slotProbe.dropAck=true')
        slot_action('slot-2', 'Close slot')
        manage('slot-2').locator('option[value="open"]').wait_for(state='attached')
        guest.locator('.room-panel.invitation').get_by_text('0 open places',exact=False).first.wait_for()
        host.wait_for_function("slotProbe.blocked.filter(item=>item==='result').length>=2")
        host.wait_for_function("document.querySelector('[data-testid=room-status]')?.textContent?.includes('did not respond')", timeout=12000)
        assert manage('slot-2').locator('option[value="open"]').count()==1
        host.screenshot(path=str(output.with_suffix('.applied-close.png')))
        stage('lost acknowledgement observed')
        host.evaluate('slotProbe.dropAck=false')

        guest.evaluate('invitationSockets.at(-1).close()')
        guest.get_by_role('button', name='Reconnect rooms', exact=True).wait_for()
        slot_action('slot-2', 'Open slot')
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
        dismissed.locator('[data-testid=directory][data-directory-status=live]').wait_for()
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
        slot_action('slot-2', 'Close slot')
        slot_action('slot-2', 'Open slot')
        dismissed.get_by_role('button', name='Retry', exact=True).click()
        dismissed.locator('[data-testid=directory][data-directory-status=live]').wait_for()
        stage('dismissed tab reconnected')
        assert dismissed.locator('.room-panel.invitation').count() == 0
        assert dismissed.get_by_role('button', name='Join room', exact=True).count() == 0
        assert dismissed.get_by_test_id('room-notice').count() == 0
        dismissed.screenshot(path=str(output.with_suffix('.dismissed-invite.png')))

        guest.get_by_role('button', name='Join room', exact=True).click()
        guest.get_by_test_id('room-view').wait_for(state='attached')
        assert guest.get_by_test_id('room-slot').count()==5
        manage('slot-2').select_option('kick')
        host.get_by_role('button',name='Cancel',exact=True).click()
        assert guest.get_by_test_id('room-view').count()==1
        manage('slot-2').select_option('kick')
        host.get_by_role('button',name='Kick member',exact=True).click()
        guest.get_by_test_id('room-view').wait_for(state='detached')
        manage('slot-2').locator('option[value="close"]').wait_for(state='attached')
        assert host.get_by_test_id('room-slot').count()==5
        assert not errors, errors
        result = {'result': 'pass', 'room_name': room_name, 'lost_ack_stale_retry_and_reconnect_preserved_close': True, 'cancel_and_confirm_member_removal': True,
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
