"""Exercise actual anonymous room flows in independent browser tabs and inspect wire metadata."""
import argparse
import os
import json
import re
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser()
parser.add_argument('--chrome',action='store_true')
parser.add_argument('--output',default='rooms.local.json')
args=parser.parse_args()
root=Path(__file__).resolve().parents[2]
output=Path(args.output)
rom=(Path(os.environ.get('RETRO_COOP_STATIC_ROOT', root/'apps/client/dist'))/'generated/diagnostic.nes').read_bytes()
different=bytearray(rom);different[-1]^=1
started=time.monotonic()
service=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,stdout=subprocess.PIPE,text=True)
try:
    url=json.loads(service.stdout.readline())['url']
    with sync_playwright() as p:
        browser=p.chromium.launch(ignore_default_args=['--mute-audio'],**({'channel':'chrome'} if args.chrome else {}))
        frames,errors=[],[]
        def page():
            value=browser.new_page(viewport={'width':1280,'height':1000})
            value.add_init_script("const NativeSocket=WebSocket;window.WebSocket=class extends NativeSocket{constructor(...args){super(...args);this.addEventListener('message',event=>{const d=JSON.parse(event.data);if(d.type==='room')window.lastRoom=d.room;if(d.type==='result'&&d.ok&&d.data?.room)window.lastRoom=d.data.room})}}")
            value.on('pageerror',lambda error: errors.append(str(error)))
            value.on('websocket',lambda socket: socket.on('framesent',lambda raw: frames.append(json.loads(raw))))
            return value
        host=page();host.goto(url)
        host.get_by_role('button',name='Create game',exact=True).click()
        assert host.get_by_label('Room access').input_value()=='public'
        host.screenshot(path=str(output.with_suffix('.before.png')),full_page=True)
        host.set_input_files('input[type=file]',{'name':'PRIVATE-HOST-FILENAME.nes','mimeType':'application/octet-stream','buffer':rom})
        assert host.get_by_test_id('room-view').count()==0
        host.get_by_role('button',name='Create room',exact=True).click()
        host.wait_for_function("document.querySelector('[data-testid=room-view]')!==null")
        assert host.locator('canvas').get_attribute('data-frame-count')=='0'
        assert host.get_by_label('Room access').count()==0
        invitation=host.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite")
        assert '#invite=' in invitation and len(invitation.split('#invite=')[1])>=22
        host.screenshot(path=str(output.with_suffix('.host.png')),full_page=True)
        dismissed=page();dismissed.goto(invitation)
        dismissed.get_by_role('button',name='Join room',exact=True).wait_for()
        assert dismissed.get_by_label('Connection privacy',exact=True).count()==0
        assert dismissed.get_by_role('button',name='Create game',exact=True).count()==0
        dismissed.get_by_role('button',name='View public rooms',exact=True).click()
        assert dismissed.get_by_test_id('directory').is_visible()
        assert dismissed.locator('.room-panel.invitation').count()==0
        assert '#invite=' not in dismissed.url
        dismissed.goto(invitation)
        dismissed.locator('.room-panel.invitation').wait_for(state='visible')
        dismissed.get_by_role('button',name='Join room',exact=True).wait_for()
        dismissed.get_by_role('button',name='View public rooms',exact=True).click()
        dismissed.get_by_role('button',name='Create game',exact=True).click()
        dismissed.set_input_files('input[type=file]',{'name':'LOCAL-PRACTICE.nes','mimeType':'application/octet-stream','buffer':rom})
        dismissed.get_by_role('button',name='Play locally',exact=True).click()
        assert dismissed.locator('main').get_attribute('class').startswith('playing')
        dismissed.get_by_test_id('player-status').filter(has_text='Game loaded').wait_for(state='attached')
        dismissed.goto(invitation)
        dismissed.get_by_role('button',name='Join room',exact=True).click()
        dismissed.get_by_role('button',name='Leave room',exact=True).wait_for()
        dismissed.get_by_role('button',name='Leave room',exact=True).click()
        dismissed.get_by_test_id('directory').wait_for(state='visible')
        assert '#invite=' not in dismissed.url
        dismissed.goto(invitation)
        dismissed.locator('.room-panel.invitation').wait_for(state='visible')
        dismissed.close()
        stale_host=page();stale_host.goto(url)
        stale_host.get_by_role('button',name='Create game',exact=True).click()
        stale_host.get_by_label('Room access').select_option('protected')
        stale_host.get_by_label('Room password').fill('stale-room-password')
        stale_host.set_input_files('input[type=file]',{'name':'STALE-PREVIEW.nes','mimeType':'application/octet-stream','buffer':rom})
        stale_host.get_by_role('button',name='Create room',exact=True).click()
        stale_host.get_by_test_id('room-view').wait_for(state='attached')
        stale_guest=page();stale_guest.goto(stale_host.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite"))
        stale_guest.get_by_role('button',name='Join room',exact=True).wait_for()
        stale_host.get_by_role('button',name='Leave room',exact=True).click()
        stale_host.get_by_role('button',name='Confirm leave',exact=True).click()
        stale_host.get_by_test_id('room-view').wait_for(state='detached')
        stale_guest.get_by_role('button',name='Join room',exact=True).click()
        stale_guest.get_by_label('Room password').fill('stale-room-password')
        stale_guest.get_by_role('dialog').get_by_role('button',name='Join room',exact=True).click()
        stale_guest.get_by_test_id('room-status').filter(has_text='closed, unavailable').wait_for()
        assert stale_guest.get_by_test_id('room-view').count()==0
        assert stale_guest.get_by_role('button',name='Retry invitation',exact=True).is_visible()
        stale_guest.screenshot(path=str(output.with_suffix('.stale-invite.png')),full_page=True)
        stale_host.close();stale_guest.close()
        # Leave exactly one of five slots available for the atomic admission race.
        for slot in ['slot-3','slot-4','slot-5']:
            row=host.locator(f'[data-slot-id={slot}]')
            row.get_by_role('button',name='Manage',exact=True).click()
            management=host.get_by_role('dialog',name=re.compile('Manage slot'))
            management.get_by_role('button',name='Close slot',exact=True).click()
            management.get_by_role('button',name='Open slot',exact=True).wait_for()
            management.get_by_role('button',name='Done',exact=True).click()
        first=page();second=page()
        for guest in [first,second]:
            guest.add_init_script('''(() => {const send=WebSocket.prototype.send;
              WebSocket.prototype.send=function(data){const command=JSON.parse(data);
                if(command.type==='join'&&!window.releaseRaceJoin){window.releaseRaceJoin=()=>send.call(this,data);return;}
                return send.call(this,data);};})();''')
            guest.goto(invitation)
            guest.get_by_role('button',name='Join room',exact=True).wait_for()
            assert guest.get_by_test_id('room-view').count()==0
            assert guest.locator('canvas').get_attribute('data-frame-count')=='0'
        # Independent clients race without loading a game first.
        for guest in [first,second]:
            guest.get_by_role('button',name='Join room',exact=True).click()
            guest.wait_for_function("typeof releaseRaceJoin === 'function'")
        first.evaluate('releaseRaceJoin()')
        second.evaluate('releaseRaceJoin()')
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            candidates=[first,second]
            rooms=[guest.get_by_test_id('room-view').count() for guest in candidates]
            statuses=[guest.get_by_test_id('room-status').text_content() or '' for guest in candidates]
            if sum(rooms)==1 and 'All five slots are occupied or closed' in statuses[rooms.index(0)]:break
            time.sleep(.05)
        assert sum(rooms)==1 and 'All five slots are occupied or closed' in statuses[rooms.index(0)],(rooms,statuses)
        first,second=(candidates[0],candidates[1]) if rooms==[1,0] else (candidates[1],candidates[0])
        first.get_by_test_id('room-view').wait_for(state='attached')
        assert first.get_by_test_id('room-view').count()==1
        first.get_by_role('button',name='Leave room',exact=True).wait_for()
        # A reserved guest automatically downloads the host's exact game.
        first.get_by_role('button',name='Ready',exact=True).wait_for(timeout=30000)
        assert first.get_by_role('button',name='Choose matching NES file').count()==0
        assert first.locator('canvas').get_attribute('data-frame-count')=='0'
        first.locator('[data-slot-id=slot-2] [data-slot-region=status]').get_by_text('Not ready',exact=True).wait_for()
        first.screenshot(path=str(output.with_suffix('.guest.png')),full_page=True)
        # Reloading the host and choosing the same file preserves the room, loaded membership, and cleared acquisition deadline.
        original_reservation=first.evaluate('({member:lastRoom.chatMembership,lease:lastRoom.reservationUntil??null})')
        assert original_reservation['lease'] is None, 'Loaded member still has an acquisition deadline'
        host.reload()
        host.set_input_files('input[type=file]',{'name':'PRIVATE-RELOADED.nes','mimeType':'application/octet-stream','buffer':rom})
        host.wait_for_function("document.querySelector('[data-testid=player-status]')?.textContent?.startsWith('Game loaded')")
        assert host.evaluate('lastRoom.invite')==invitation.split('#invite=')[1]
        assert first.evaluate('({member:lastRoom.chatMembership,lease:lastRoom.reservationUntil??null})')==original_reservation
        assert first.get_by_test_id('room-view').count()==1
        leave=first.get_by_role('button',name='Leave room',exact=True)
        leave.wait_for();leave.click()
        first.get_by_test_id('room-view').wait_for(state='detached')
        assert first.get_by_test_id('directory').is_visible()
        assert first.locator('.room-panel.invitation').count()==0
        assert '#invite=' not in first.url
        # The live invitation reopens as soon as the first guest leaves.
        second.get_by_role('button',name='Join room',exact=True).wait_for()
        second.get_by_role('button',name='Join room',exact=True).click()
        second.get_by_test_id('room-view').wait_for(state='attached')
        second.get_by_role('button',name='Leave room',exact=True).click()
        second.get_by_test_id('room-view').wait_for(state='detached')
        # Rename renders hostile text literally, and access changes protect future admission.
        host.get_by_role('button',name='Ready',exact=True).click()
        host.get_by_role('button',name='Start game',exact=True).click()
        host.wait_for_function("Number(document.querySelector('canvas').dataset.frameCount)>10")
        host.locator('.room-panel').wait_for()
        late=page();late.goto(invitation)
        late.get_by_role('button',name='Join room',exact=True).click()
        late.get_by_test_id('room-view').wait_for(state='attached')
        late.get_by_role('button',name='Players',exact=True).click()
        assert late.get_by_test_id('room-slot').count()==5
        late.get_by_role('button',name='Leave room',exact=True).click()
        late.get_by_role('button',name='Confirm leave',exact=True).click()
        late.get_by_test_id('room-view').wait_for(state='detached')
        late.close()
        host.get_by_text('Room settings',exact=True).click()
        host.get_by_label('Room name',exact=True).fill('<img src=x onerror=alert(1)>')
        host.get_by_role('button',name='Save room name',exact=True).click()
        host.wait_for_function("document.querySelector('#room-heading').textContent.startsWith('<img')")
        assert host.locator('.room-panel img').count()==0
        host.get_by_role('button',name='Protect room',exact=True).click()
        host.get_by_label('New room password').fill('changed-room-password')
        host.get_by_role('button',name='Protect room',exact=True).last.click()
        host.get_by_text('Room access: Password protected',exact=True).wait_for()
        # Explicit close removes the invitation and exits the game before returning to rooms.
        host.get_by_role('button',name='Leave room',exact=True).click()
        host.get_by_role('button',name='Confirm leave',exact=True).click()
        host.get_by_test_id('room-view').wait_for(state='detached')
        assert host.get_by_test_id('directory').is_visible()
        second.goto(invitation)
        second.reload()
        second.screenshot(path=str(output.with_suffix('.closed-preview.png')),full_page=True)
        second.get_by_role('button',name='Retry invitation',exact=True).click()
        second.wait_for_function("document.querySelector('[data-testid=room-status]')?.textContent.includes('closed, unavailable')")
        assert host.locator('canvas').get_attribute('data-frame-count')=='0'
        # A room keeps its verified game. A different local file cannot replace it;
        # after leaving, deliberate Create room publishes a new room instead.
        replacement=page();replacement.goto(url)
        replacement.get_by_role('button',name='Create game',exact=True).click()
        replacement.set_input_files('input[type=file]',{'name':'PRIVATE-ORIGINAL.nes','mimeType':'application/octet-stream','buffer':rom})
        assert replacement.get_by_test_id('room-view').count()==0
        replacement.get_by_role('button',name='Create room',exact=True).click()
        replacement.get_by_test_id('room-view').wait_for(state='attached')
        old_invite=replacement.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite")
        waiting=page();waiting.goto(old_invite)
        waiting.get_by_role('button',name='Join room',exact=True).click()
        waiting.get_by_test_id('room-view').wait_for(state='attached')
        replacement.set_input_files('input[type=file]',{'name':'PRIVATE-REPLACEMENT.nes','mimeType':'application/octet-stream','buffer':bytes(different)})
        replacement.get_by_test_id('room-status').filter(has_text='Leave this room before choosing a different game.').wait_for(state='attached')
        assert waiting.get_by_test_id('room-view').count()==1
        assert replacement.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite")==old_invite
        replacement.reload()
        replacement.set_input_files('input[type=file]',{'name':'PRIVATE-REPLACEMENT.nes','mimeType':'application/octet-stream','buffer':bytes(different)})
        replacement.get_by_test_id('room-status').filter(has_text='Leave this room before choosing a different game.').wait_for(state='attached')
        assert waiting.get_by_test_id('room-view').count()==1
        assert replacement.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite")==old_invite
        replacement.evaluate("window.originalRead=FileReader.prototype.readAsArrayBuffer;FileReader.prototype.readAsArrayBuffer=function(){}")
        replacement.set_input_files('input[type=file]',{'name':'PRIVATE-CANCELLED.nes','mimeType':'application/octet-stream','buffer':bytes(different)})
        replacement.get_by_role('button',name='Cancel loading',exact=True).click()
        replacement.evaluate("()=>{FileReader.prototype.readAsArrayBuffer=window.originalRead}")
        assert waiting.get_by_test_id('room-view').count()==1
        assert replacement.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite")==old_invite
        replacement.set_input_files('input[type=file]',{'name':'PRIVATE-INVALID.nes','mimeType':'application/octet-stream','buffer':b'invalid'})
        replacement.wait_for_function("document.querySelector('[data-testid=player-status]').textContent.includes('NES')")
        assert waiting.get_by_test_id('room-view').count()==1
        replacement.screenshot(path=str(output.with_suffix('.replacement-declined.png')),full_page=True)
        replacement.get_by_role('button',name='Leave room',exact=True).click()
        replacement.get_by_role('button',name='Confirm leave',exact=True).click()
        waiting.get_by_test_id('room-view').wait_for(state='detached')
        replacement.get_by_role('button',name='Create game',exact=True).click()
        replacement.set_input_files('input[type=file]',{'name':'PRIVATE-REPLACEMENT.nes','mimeType':'application/octet-stream','buffer':bytes(different)})
        assert replacement.get_by_test_id('room-view').count()==0
        replacement.get_by_role('button',name='Create room',exact=True).click()
        replacement.get_by_test_id('room-status').filter(has_text='Room created').wait_for(state='attached')
        assert replacement.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite")!=old_invite
        replacement.screenshot(path=str(output.with_suffix('.replacement-confirmed.png')),full_page=True)
        replacement.close();waiting.close()
        # A fresh tab starts Public. Keep this room Public to isolate stale join handling.
        race_host=page();race_host.goto(url)
        race_host.get_by_role('button',name='Create game',exact=True).click()
        assert race_host.get_by_label('Room access').input_value()=='public'
        race_host.set_input_files('input[type=file]',{'name':'PRIVATE-RACE.nes','mimeType':'application/octet-stream','buffer':rom})
        race_host.get_by_role('button',name='Create room',exact=True).click()
        race_host.get_by_test_id('room-view').wait_for(state='attached')
        # A cancelled join's delayed response must not release a newer reservation.
        raced=page()
        raced.add_init_script("""const Native=WebSocket;let holdFirstJoin=true;
          window.WebSocket=class extends Native {
            set onmessage(handler){super.onmessage=event=>{let data;try{data=JSON.parse(event.data)}catch{};
              if(holdFirstJoin && data?.type==='result' && data.ok && data.data?.room?.role==='member'){
                holdFirstJoin=false;window.releaseJoinA=()=>handler(event);
              }else handler(event);};}
          };""")
        race_invite=race_host.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite")
        raced.goto(race_invite)
        raced.wait_for_function("document.querySelector('[data-testid=room-status]')?.textContent.startsWith('Join reserves')")
        raced.get_by_role('button',name='Join room',exact=True).click()
        raced.wait_for_function('typeof releaseJoinA === "function"')
        raced.get_by_role('button',name='Cancel pending room action',exact=True).click()
        raced.get_by_test_id('room-view').wait_for(state='detached')
        raced.get_by_role('button',name='Join room',exact=True).click()
        raced.wait_for_function("document.querySelector('[data-testid=room-status]')?.textContent.startsWith('Slot reserved')")
        raced.evaluate('releaseJoinA()')
        # Close the other three empty slots so capacity still proves Join B survived.
        for slot in ['slot-3','slot-4','slot-5']:
            row=race_host.locator(f'[data-slot-id={slot}]')
            row.get_by_role('button',name='Manage',exact=True).click()
            management=race_host.get_by_role('dialog',name=re.compile('Manage slot'))
            management.get_by_role('button',name='Close slot',exact=True).click()
            management.get_by_role('button',name='Open slot',exact=True).wait_for()
            management.get_by_role('button',name='Done',exact=True).click()
        competing=page();competing.goto(race_invite)
        competing.locator('.room-panel.invitation').get_by_text('0 open places', exact=False).wait_for()
        assert '0 open places' in competing.locator('.room-panel.invitation').inner_text()
        assert competing.get_by_role('button',name='Join room',exact=True).count()==0
        assert competing.get_by_role('button',name='View public rooms',exact=True).is_visible()
        assert competing.get_by_test_id('room-view').count()==0, 'stale Join A released newer Join B on the real server'
        assert raced.get_by_test_id('room-view').count()==1
        raced.get_by_role('button',name='Leave room',exact=True).click()
        raced.get_by_test_id('room-view').wait_for(state='detached')
        # Hold the create reply at the browser boundary. Cancellation must close the provisional room,
        # and releasing the stale response must never confirm it.
        cancelled=page()
        cancelled.add_init_script('''const Native=WebSocket;
          window.holdCreate=true;window.staleReply=null;
          window.WebSocket=class extends Native {
            set onmessage(handler){super.onmessage=event=>{let data;try{data=JSON.parse(event.data)}catch{};
              if(window.holdCreate && data?.type==='result' && data.ok && data.data?.room && data.data.room.role==='host'){
                window.staleReply=()=>handler(event);window.heldInvite=data.data.room.invite;
              }else handler(event);};}
          };''')
        cancelled.goto(url)
        cancelled.get_by_role('button',name='Create game',exact=True).click()
        cancelled.set_input_files('input[type=file]',{'name':'PRIVATE-CANCELLED.nes','mimeType':'application/octet-stream','buffer':rom})
        cancelled.get_by_role('button',name='Create room',exact=True).click()
        cancelled.wait_for_function('typeof staleReply === "function"')
        cancelled.get_by_role('button',name='Cancel',exact=True).click()
        stale_invite=cancelled.evaluate('heldInvite')
        cancelled.evaluate('holdCreate=false;staleReply()')
        cancelled.locator('.create-options [role=status]').filter(has_text='cancelled').wait_for()
        assert cancelled.get_by_test_id('room-view').count()==0
        observer=page();observer.goto(url+'#invite='+stale_invite)
        observer.wait_for_function("document.querySelector('[data-testid=room-status]')?.textContent.includes('closed, unavailable')")
        # Socket failure is recoverable without dropping the loaded file or claiming a room exists.
        offline=page()
        offline.add_init_script("const Native=WebSocket;window.WebSocket=class extends Native {constructor(url,...args){super(String(url).replace('/ws','/offline'),...args)}};")
        offline.goto(url)
        offline.get_by_role('button',name='Create game',exact=True).click()
        offline.set_input_files('input[type=file]',{'name':'PRIVATE-OFFLINE.nes','mimeType':'application/octet-stream','buffer':rom})
        offline.get_by_role('button',name='Create room',exact=True).click()
        offline.locator('.create-options [role=status]').filter(has_text='Room connection lost').wait_for()
        offline.get_by_role('button',name='Play locally',exact=True).click()
        offline.get_by_role('button',name='Resume',exact=True).click()
        offline.wait_for_function("Number(document.querySelector('canvas').dataset.frameCount)>10")
        offline.get_by_role('button',name='Public rooms',exact=True).click()
        offline.get_by_role('button',name='Create game',exact=True).wait_for()
        assert offline.get_by_test_id('room-view').count()==0
        offline.screenshot(path=str(output.with_suffix('.offline.png')),full_page=True)
        race_host.set_viewport_size({'width':390,'height':844})
        assert race_host.evaluate('document.documentElement.scrollWidth<=innerWidth')
        race_host.screenshot(path=str(output.with_suffix('.mobile.png')),full_page=True)
        assert not errors,errors
        encoded=json.dumps(frames)
        assert 'PRIVATE-' not in encoded
        assert not any(key in command for command in frames for key in ['rom','filename','save','state'])
        # Raw tokens are intentionally excluded from published evidence.
        counts={kind:sum(command['type']==kind for command in frames) for kind in sorted({command['type'] for command in frames})}
        result={'result':'pass','browser':browser.version,'seconds':round(time.monotonic()-started,2),'file_requires_explicit_create_room':True,'public_default_and_password_protection':True,'invite_preview_before_join':True,'atomic_final_open_slot_browser_race':True,'late_join_after_start':True,'reservation_before_file':True,'host_reload_matching_file_preserves_room_and_lease':True,'cancel_releases_slot':True,'rename_plain_text':True,'access_changes_future_admission':True,'close_expires_invite_and_quits_game':True,'cancelled_stale_create_not_published':True,'stale_join_cannot_release_newer_reservation':True,'hosted_game_cannot_be_replaced':True,'leave_then_explicit_create_new_room':True,'cancelled_and_invalid_selection_preserve_room_and_game':True,'offline_preserves_local_game':True,'metadata_only_websocket_requests':True,'mobile_no_overflow':True,'command_counts':counts,'page_errors':errors}
        output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
        browser.close()
finally:
    service.terminate()
    try:service.wait(timeout=5)
    except subprocess.TimeoutExpired:service.kill();service.wait()
