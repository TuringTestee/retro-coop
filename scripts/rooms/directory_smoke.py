"""Verify public discovery and admission through the actual browser and coordinator."""
import argparse
import json
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser()
parser.add_argument('--chrome',action='store_true')
parser.add_argument('--output',default='directory.local.json')
args=parser.parse_args()
root=Path(__file__).resolve().parents[2]
output=Path(args.output)
started=time.monotonic()
service=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,stdout=subprocess.PIPE,text=True)
try:
    url=json.loads(service.stdout.readline())['url']
    rom=(root/'apps/client/dist/generated/diagnostic.nes').read_bytes()
    with sync_playwright() as p:
        browser=p.chromium.launch(ignore_default_args=['--mute-audio'],**({'channel':'chrome'} if args.chrome else {}))
        errors,received,sent=[],[],[]
        def page():
            page=browser.new_page(viewport={'width':1280,'height':1000})
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('websocket',lambda socket:socket.on('framereceived',lambda raw:received.append(json.loads(raw))))
            page.on('websocket',lambda socket:socket.on('framesent',lambda raw:sent.append(json.loads(raw))))
            page.add_init_script('window.directorySockets=[]; const OriginalSocket=WebSocket; window.WebSocket=class extends OriginalSocket {constructor(...args){super(...args);directorySockets.push(this)}};')
            page.goto(url)
            return page
        viewer=page()
        viewer.get_by_text('No public rooms yet. Host a game to start one.',exact=True).wait_for()
        assert viewer.get_by_role('button',name='Included game unavailable').is_disabled()
        viewer.get_by_role('button',name='Host a game',exact=True).click()
        assert viewer.get_by_role('button',name='Choose NES file',exact=True).evaluate('(el)=>el===document.activeElement')
        hosts=[page(),page()]
        for host in hosts:
            host.set_input_files('input[type=file]',{'name':'PRIVATE-DIRECTORY-GAME.nes','mimeType':'application/octet-stream','buffer':rom})
            host.get_by_test_id('room-view').wait_for()
            host.get_by_text('Session settings',exact=True).click()
            host.get_by_label('Room name',exact=True).fill('Duplicate Arcade')
            host.get_by_role('button',name='Save room name',exact=True).click()
            host.wait_for_function("document.querySelector('#room-heading').textContent==='Duplicate Arcade'")
        viewer.wait_for_function("document.querySelectorAll('.room-list li').length===2")
        search=viewer.get_by_label('Search rooms, hosts or public code')
        search.fill('dUPlicate')
        assert viewer.locator('.room-list li').count()==2
        codes=viewer.locator('.room-list code').all_text_contents()
        assert codes[0]!=codes[1]
        search.fill(codes[0].lower())
        assert viewer.locator('.room-list li').count()==1
        join=viewer.locator('.room-list button');join.focus()
        # A live rename retains the keyed row and keyboard focus.
        hosts[0].get_by_label('Room name',exact=True).fill('Renamed Arcade')
        hosts[0].get_by_role('button',name='Save room name',exact=True).click()
        viewer.get_by_text('Renamed Arcade',exact=True).wait_for()
        assert join.evaluate('(el)=>el===document.activeElement')
        observer=page();observer.get_by_label('Search rooms, hosts or public code').fill(codes[0])
        observer.locator('.room-list button').focus()
        join.click();viewer.get_by_test_id('room-view').wait_for()
        assert viewer.get_by_test_id('frames').inner_text()=='0 frames'
        assert 'Player 2 (reserved)' in viewer.get_by_test_id('room-view').inner_text()
        observer.get_by_role('button',name='Player 2 reserved',exact=True).wait_for()
        assert observer.locator('.room-list button').evaluate('(el)=>el===document.activeElement')
        assert observer.locator('.room-list').get_by_text('Host-provided title',exact=True).count()==1
        assert observer.locator('.room-list').get_by_text('Bring your own matching ROM',exact=True).count()==1
        assert observer.get_by_role('button',name='Player 2 reserved',exact=True).is_disabled()
        viewer.set_input_files('input[type=file]',{'name':'PRIVATE-DIRECTORY-GUEST.nes','mimeType':'application/octet-stream','buffer':rom})
        viewer.wait_for_function("document.querySelector('[data-testid=room-view]').textContent.includes('Files match')")
        viewer.get_by_role('button',name='Cancel join',exact=True).click()
        viewer.get_by_test_id('room-view').wait_for(state='detached')
        observer.get_by_role('button',name='Join room',exact=True).wait_for()
        observer.get_by_role('button',name='Join room',exact=True).focus()
        hosts[0].get_by_label('Unlisted · invitation only',exact=True).click()
        observer.get_by_text('No matching public rooms.',exact=True).wait_for()
        assert observer.get_by_label('Search rooms, hosts or public code').evaluate('(el)=>el===document.activeElement')
        observer.get_by_role('button',name='Clear search',exact=True).click()
        assert observer.get_by_label('Search rooms, hosts or public code').input_value()==''
        observer.wait_for_function("document.querySelectorAll('.room-list li').length===1")
        observer.screenshot(path=str(output.with_suffix('.live.png')),full_page=True)
        # Close this tab's actual coordinator socket: stale rows remain visible and inert.
        offline=page()
        offline.wait_for_function("document.querySelectorAll('.room-list li').length===1")
        offline.evaluate('directorySockets.forEach(socket=>socket.close())')
        offline.get_by_role('button',name='Retry directory',exact=True).wait_for()
        assert offline.locator('.room-list li').count()==1
        assert offline.locator('.room-list button').is_disabled()
        offline.screenshot(path=str(output.with_suffix('.stale.png')),full_page=True)
        offline.get_by_role('button',name='Retry directory',exact=True).click()
        offline.wait_for_function("document.querySelector('.room-list button')?.getAttribute('aria-disabled')==='false'")
        assert not errors,errors
        public=[event['rooms'] for event in received if event.get('type')=='directory']
        public += [event['data']['directory'] for event in received if event.get('type')=='result' and event.get('ok') and 'directory' in event['data']]
        assert public
        allowed={'id','label','host','visibility','code','status','occupancy'}
        assert all(set(room)<=allowed and room['visibility']=='public' for snapshot in public for room in snapshot)
        assert not any('PRIVATE-DIRECTORY' in json.dumps(frame) for frame in sent)
        result={'empty':True,'duplicate_names_distinct_codes':codes,'case_insensitive_search':True,'live_focus_retained':True,'occupancy_change_retains_button_focus':True,'clear_search_and_source_disclosure':True,'reserve_before_file':True,'matching_guest_file':True,'full_room_disabled':True,'unlisted_removed_and_focus_recovered':True,'stale_rows_disabled_retry_recovers':True,'directory_payloads_metadata_only':len(public),'private_filenames_never_sent':True,'page_errors':errors,'elapsedSeconds':round(time.monotonic()-started,2)}
        output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
        browser.close()
finally:
    service.terminate();service.wait(timeout=5)
