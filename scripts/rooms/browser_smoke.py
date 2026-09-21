"""Exercise actual anonymous room flows in independent browser tabs and inspect wire metadata."""
import argparse
import json
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
rom=(root/'apps/client/dist/generated/diagnostic.nes').read_bytes()
started=time.monotonic()
service=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,stdout=subprocess.PIPE,text=True)
try:
    url=json.loads(service.stdout.readline())['url']
    with sync_playwright() as p:
        browser=p.chromium.launch(ignore_default_args=['--mute-audio'],**({'channel':'chrome'} if args.chrome else {}))
        frames,errors=[],[]
        def page():
            value=browser.new_page(viewport={'width':1280,'height':1000})
            value.on('pageerror',lambda error: errors.append(str(error)))
            value.on('websocket',lambda socket: socket.on('framesent',lambda raw: frames.append(json.loads(raw))))
            return value
        host=page();host.goto(url)
        assert not host.get_by_label('Unlisted · invitation only',exact=True).is_checked()
        host.screenshot(path=str(output.with_suffix('.before.png')),full_page=True)
        host.set_input_files('input[type=file]',{'name':'PRIVATE-HOST-FILENAME.nes','mimeType':'application/octet-stream','buffer':rom})
        host.wait_for_function("document.querySelector('[data-testid=room-view]')!==null")
        host.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>10")
        assert 'Public ·' in host.get_by_test_id('room-view').inner_text()
        invitation=host.get_by_label('Room invitation',exact=True).input_value()
        assert '#invite=' in invitation and len(invitation.split('#invite=')[1])>=22
        host.screenshot(path=str(output.with_suffix('.host.png')),full_page=True)
        first=page();second=page()
        for guest in [first,second]:
            guest.goto(invitation)
            guest.wait_for_function("document.querySelector('[data-testid=room-status]').textContent.startsWith('Join reserves')")
            assert guest.get_by_test_id('room-view').count()==0
            assert guest.get_by_test_id('frames').inner_text()=='0 frames'
        # Independent clients race without loading a game first.
        first.get_by_role('button',name='Retry join / Join',exact=True).click()
        second.get_by_role('button',name='Retry join / Join',exact=True).click()
        first.get_by_test_id('room-view').wait_for()
        second.wait_for_function("document.querySelector('[data-testid=room-status]').textContent.includes('place was just taken')")
        assert 'the guest (reserved)' in first.get_by_test_id('room-view').inner_text()
        assert first.get_by_role('button',name='Close room',exact=True).count()==0
        # A reserved guest can choose mismatching and matching files without another ready click.
        solo_frames=int(host.get_by_test_id('frames').inner_text().split()[0])
        different=bytearray(rom);different.extend(b'header byte identity test')
        first.set_input_files('input[type=file]',{'name':'PRIVATE-GUEST-FILENAME.nes','mimeType':'application/octet-stream','buffer':bytes(different)})
        first.wait_for_function("document.querySelector('[data-testid=player-status]').textContent.startsWith('Game loaded')")
        assert first.get_by_role('button',name='Resume',exact=True).is_enabled()
        assert first.get_by_test_id('frames').inner_text()=='0 frames'
        assert 'Game loaded' in first.get_by_test_id('player-status').inner_text()
        assert 'exact matching file' in first.get_by_test_id('room-view').inner_text()
        host.wait_for_function("before=>Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>before",arg=solo_frames)
        first.set_input_files('input[type=file]',{'name':'PRIVATE-GUEST-FILENAME.nes','mimeType':'application/octet-stream','buffer':rom})
        first.wait_for_function("document.querySelector('[data-testid=room-view]').textContent.includes('Files match')")
        first.screenshot(path=str(output.with_suffix('.guest.png')),full_page=True)
        # Reloading the host and choosing the same file preserves the room and original guest lease.
        original_reservation=first.get_by_test_id('room-view').inner_text().split('Reservation expires at ')[1].split('.')[0]
        host.reload()
        host.set_input_files('input[type=file]',{'name':'PRIVATE-RELOADED.nes','mimeType':'application/octet-stream','buffer':rom})
        host.wait_for_function("document.querySelector('[data-testid=room-status]').textContent.includes('existing room')")
        assert host.get_by_label('Room invitation',exact=True).input_value()==invitation
        assert original_reservation in host.get_by_test_id('room-view').inner_text()
        assert first.get_by_test_id('room-view').count()==1
        first.get_by_role('button',name='Cancel join',exact=True).click()
        first.get_by_test_id('room-view').wait_for(state='detached')
        second.get_by_role('button',name='Retry join / Join',exact=True).click()
        second.get_by_test_id('room-view').wait_for()
        second.get_by_role('button',name='Cancel join',exact=True).click()
        second.get_by_test_id('room-view').wait_for(state='detached')
        # Rename renders hostile text literally, and visibility changes revoke the public code.
        host.get_by_text('Session settings',exact=True).click()
        host.get_by_label('Room name',exact=True).fill('<img src=x onerror=alert(1)>')
        host.get_by_role('button',name='Save room name',exact=True).click()
        host.wait_for_function("document.querySelector('#room-heading').textContent.startsWith('<img')")
        assert host.locator('.room-panel img').count()==0
        host.get_by_label('Unlisted · invitation only',exact=True).click()
        host.wait_for_function("document.querySelector('[data-testid=room-view]').textContent.includes('Unlisted · invite only')")
        assert 'Public ·' not in host.get_by_test_id('room-view').inner_text()
        # Explicit close removes the invite immediately and retains local emulation.
        host.on('dialog',lambda dialog:dialog.accept())
        host.get_by_role('button',name='Close details',exact=True).click()
        host.get_by_test_id('room-view').wait_for(state='detached')
        second.get_by_role('button',name='Retry join / Join',exact=True).click()
        second.wait_for_function("document.querySelector('[data-testid=room-status]').textContent.includes('closed, unavailable')")
        assert int(host.get_by_test_id('frames').inner_text().split()[0])>10
        # Recover the host before committing a replacement: decline preserves room/guest and active game.
        replacement=page();replacement.goto(url)
        replacement.set_input_files('input[type=file]',{'name':'PRIVATE-ORIGINAL.nes','mimeType':'application/octet-stream','buffer':rom})
        replacement.get_by_test_id('room-view').wait_for()
        old_invite=replacement.get_by_label('Room invitation',exact=True).input_value()
        waiting=page();waiting.goto(old_invite)
        waiting.get_by_role('button',name='Retry join / Join',exact=True).click()
        waiting.get_by_test_id('room-view').wait_for()
        declines=[]
        def decline(dialog):
            declines.append(dialog.message);dialog.dismiss()
        replacement.on('dialog',decline)
        replacement.set_input_files('input[type=file]',{'name':'PRIVATE-REPLACEMENT.nes','mimeType':'application/octet-stream','buffer':bytes(different)})
        replacement.wait_for_function("document.querySelector('[data-testid=player-status]').textContent.includes('Selection cancelled')")
        assert len(declines)==1 and waiting.get_by_test_id('room-view').count()==1
        assert replacement.get_by_label('Room invitation',exact=True).input_value()==old_invite
        replacement.locator('.panel summary').click()
        assert __import__('hashlib').sha256(rom).hexdigest() in replacement.get_by_test_id('fingerprint').inner_text()
        replacement.reload()
        replacement.set_input_files('input[type=file]',{'name':'PRIVATE-REPLACEMENT.nes','mimeType':'application/octet-stream','buffer':bytes(different)})
        replacement.wait_for_function("document.querySelector('[data-testid=player-status]').textContent.includes('Selection cancelled')")
        assert len(declines)==2 and waiting.get_by_test_id('room-view').count()==1
        assert replacement.get_by_label('Room invitation',exact=True).input_value()==old_invite
        assert replacement.get_by_test_id('frames').inner_text()=='0 frames'
        replacement.evaluate("window.originalRead=FileReader.prototype.readAsArrayBuffer;FileReader.prototype.readAsArrayBuffer=function(){}")
        replacement.set_input_files('input[type=file]',{'name':'PRIVATE-CANCELLED.nes','mimeType':'application/octet-stream','buffer':bytes(different)})
        replacement.get_by_role('button',name='Cancel loading',exact=True).click()
        replacement.evaluate("()=>{FileReader.prototype.readAsArrayBuffer=window.originalRead}")
        assert len(declines)==2 and waiting.get_by_test_id('room-view').count()==1
        assert replacement.get_by_label('Room invitation',exact=True).input_value()==old_invite
        replacement.set_input_files('input[type=file]',{'name':'PRIVATE-INVALID.nes','mimeType':'application/octet-stream','buffer':b'invalid'})
        replacement.wait_for_function("document.querySelector('[data-testid=player-status]').textContent.includes('NES')")
        assert len(declines)==2 and waiting.get_by_test_id('room-view').count()==1
        replacement.screenshot(path=str(output.with_suffix('.replacement-declined.png')),full_page=True)
        replacement.remove_listener('dialog',decline)
        confirms=[]
        def confirm(dialog):
            confirms.append(dialog.message);dialog.accept()
        replacement.on('dialog',confirm)
        replacement.set_input_files('input[type=file]',{'name':'PRIVATE-REPLACEMENT.nes','mimeType':'application/octet-stream','buffer':bytes(different)})
        waiting.get_by_test_id('room-view').wait_for(state='detached')
        replacement.wait_for_function("document.querySelector('[data-testid=room-status]').textContent.startsWith('Room created')")
        assert len(confirms)==1
        assert replacement.get_by_label('Room invitation',exact=True).input_value()!=old_invite
        replacement.screenshot(path=str(output.with_suffix('.replacement-confirmed.png')),full_page=True)
        replacement.close();waiting.close()
        # A fresh tab does not inherit Unlisted; selecting it before loading creates an unlisted room.
        unlisted=page();unlisted.goto(url)
        assert not unlisted.get_by_label('Unlisted · invitation only',exact=True).is_checked()
        unlisted.get_by_label('Unlisted · invitation only',exact=True).check()
        unlisted.set_input_files('input[type=file]',{'name':'PRIVATE-UNLISTED.nes','mimeType':'application/octet-stream','buffer':rom})
        unlisted.get_by_test_id('room-view').wait_for()
        assert 'Unlisted · invite only' in unlisted.get_by_test_id('room-view').inner_text()
        # A cancelled join's delayed response must not release a newer reservation.
        raced=page()
        raced.add_init_script("""const Native=WebSocket;let holdFirstJoin=true;
          window.WebSocket=class extends Native {
            set onmessage(handler){super.onmessage=event=>{let data;try{data=JSON.parse(event.data)}catch{};
              if(holdFirstJoin && data?.type==='result' && data.ok && data.data?.room?.role==='guest'){
                holdFirstJoin=false;window.releaseJoinA=()=>handler(event);
              }else handler(event);};}
          };""")
        race_invite=unlisted.get_by_label('Room invitation',exact=True).input_value()
        raced.goto(race_invite)
        raced.wait_for_function("document.querySelector('[data-testid=room-status]').textContent.startsWith('Join reserves')")
        raced.get_by_role('button',name='Retry join / Join',exact=True).click()
        raced.wait_for_function('typeof releaseJoinA === "function"')
        raced.get_by_role('button',name='Cancel pending room action',exact=True).click()
        raced.get_by_test_id('room-view').wait_for(state='detached')
        raced.get_by_role('button',name='Retry join / Join',exact=True).click()
        raced.wait_for_function("document.querySelector('[data-testid=room-status]').textContent.startsWith('Guest reserved')")
        raced.evaluate('releaseJoinA()')
        competing=page();competing.goto(race_invite)
        competing.wait_for_function("document.querySelector('[data-testid=room-status]').textContent.startsWith('Join reserves')")
        competing.get_by_role('button',name='Retry join / Join',exact=True).click()
        competing.wait_for_function("document.querySelector('[data-testid=room-view]') || document.querySelector('[data-testid=room-status]').textContent.includes('place was just taken')")
        assert competing.get_by_test_id('room-view').count()==0, 'stale Join A released newer Join B on the real server'
        assert raced.get_by_test_id('room-view').count()==1
        raced.get_by_role('button',name='Cancel join',exact=True).click()
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
        cancelled.set_input_files('input[type=file]',{'name':'PRIVATE-CANCELLED.nes','mimeType':'application/octet-stream','buffer':rom})
        cancelled.wait_for_function('typeof staleReply === "function"')
        cancelled.get_by_role('button',name='Cancel pending room action',exact=True).click()
        stale_invite=cancelled.evaluate('heldInvite')
        cancelled.evaluate('holdCreate=false;staleReply()')
        cancelled.wait_for_function("document.querySelector('[data-testid=room-status]').textContent.toLowerCase().includes('cancelled')")
        assert cancelled.get_by_test_id('room-view').count()==0
        observer=page();observer.goto(url+'#invite='+stale_invite)
        observer.wait_for_function("document.querySelector('[data-testid=room-status]').textContent.includes('closed, unavailable')")
        # Socket failure is recoverable without dropping the loaded file or claiming a room exists.
        offline=page()
        offline.add_init_script("const Native=WebSocket;window.WebSocket=class extends Native {constructor(url,...args){super(String(url).replace('/ws','/offline'),...args)}};")
        offline.goto(url)
        offline.set_input_files('input[type=file]',{'name':'PRIVATE-OFFLINE.nes','mimeType':'application/octet-stream','buffer':rom})
        offline.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>10")
        offline.get_by_role('button',name='Retry room creation',exact=True).wait_for()
        assert offline.get_by_test_id('room-view').count()==0
        offline.screenshot(path=str(output.with_suffix('.offline.png')),full_page=True)
        unlisted.set_viewport_size({'width':390,'height':844})
        assert unlisted.evaluate('document.documentElement.scrollWidth<=innerWidth')
        unlisted.screenshot(path=str(output.with_suffix('.mobile.png')),full_page=True)
        assert not errors,errors
        encoded=json.dumps(frames)
        assert 'PRIVATE-' not in encoded
        assert not any(key in command for command in frames for key in ['rom','filename','save','state'])
        # Raw tokens are intentionally excluded from published evidence.
        counts={kind:sum(command['type']==kind for command in frames) for kind in sorted({command['type'] for command in frames})}
        result={'result':'pass','browser':browser.version,'seconds':round(time.monotonic()-started,2),'host_file_to_room_no_extra_form':True,'public_default_and_unlisted_selection':True,'invite_preview_before_join':True,'atomic_browser_race':True,'reservation_before_file':True,'mismatch_then_match_without_ready_click':True,'host_reload_matching_file_preserves_room_and_lease':True,'cancel_releases_slot':True,'rename_plain_text':True,'visibility_removes_code':True,'close_expires_invite_preserves_local_game':True,'cancelled_stale_create_not_published':True,'stale_join_cannot_release_newer_reservation':True,'recovered_host_replacement_requires_confirmation':True,'declined_and_invalid_replacement_preserve_room_and_game':True,'offline_preserves_local_game':True,'metadata_only_websocket_requests':True,'mobile_no_overflow':True,'command_counts':counts,'page_errors':errors}
        output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
        browser.close()
finally:
    service.terminate()
    try:service.wait(timeout=5)
    except subprocess.TimeoutExpired:service.kill();service.wait()
