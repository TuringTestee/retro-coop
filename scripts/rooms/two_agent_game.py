#!/usr/bin/env python3
"""Prove two independent browsers play one host-selected NES game together."""

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
import re
import math
import statistics
import subprocess
import struct
import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from layout_geometry import browser_zoom, verify_zoom, zoom_context
from ui_helpers import protect_lobby, rename_lobby


SOURCE = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--role', choices=('host', 'guest', 'verify', 'run', 'recovery'), required=True)
parser.add_argument('--runtime-root', type=Path, default=SOURCE)
parser.add_argument('--url')
parser.add_argument('--rom', type=Path)
parser.add_argument('--visibility', choices=('public', 'protected'), default='public')
parser.add_argument('--expect-controller-ram')
parser.add_argument('--session-dir', type=Path, required=True)
parser.add_argument('--width', type=int, default=1366)
parser.add_argument('--height', type=int, default=682)
parser.add_argument('--zoom', type=int, choices=(1, 2), default=1)
parser.add_argument('--play-seconds', type=int, default=0)
args = parser.parse_args()
ROOT = args.runtime_root.resolve()
SESSION = args.session_dir.resolve()
SESSION.mkdir(parents=True, exist_ok=True)
if not 0 <= args.play_seconds <= 30:
    parser.error('--play-seconds must be between 0 and 30')
LOBBY_NAME = 'Play check ' + hashlib.sha256(str(SESSION).encode()).hexdigest()[:10]
EXPECTED_RAM = [int(value) for value in args.expect_controller_ram.split(',')] if args.expect_controller_ram else None
if EXPECTED_RAM is not None and (len(EXPECTED_RAM) != 2 or any(value < 0 or value > 255 for value in EXPECTED_RAM)):
    parser.error('--expect-controller-ram needs two byte values')


def save(name, value):
    target = SESSION / name
    temporary = SESSION / f'.{name}.{os.getpid()}'
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(target)


def wait_for(name, seconds=60):
    target = SESSION / name
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if target.exists():
            return json.loads(target.read_text())
        time.sleep(.1)
    raise TimeoutError(f'The other player did not reach {name}')


def screenshot(page, name):
    image = page.screenshot(path=str(SESSION / name), full_page=False)
    size = struct.unpack_from('>II', image, 16)
    assert size == (page.viewport_size['width'], page.viewport_size['height']), (name, size)


def shell_bounds(page):
    return page.evaluate("""() => Object.fromEntries([
      '.rc-shell','.rc-header','.rc-status','.rc-stage','.rc-footer'
    ].map(selector=>{
      const rect=document.querySelector(selector).getBoundingClientRect();
      return [selector,[rect.x,rect.y,rect.width,rect.height]];
    }))""")


def check_shell(page, original):
    current = shell_bounds(page)
    assert all(all(abs(a-b) <= 1 for a,b in zip(rect,current[selector]))
               for selector,rect in original.items()), (original,current)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight')


def verify():
    host, guest = wait_for('host.json', 1), wait_for('guest.json', 1)
    assert host['result'] == guest['result'] == 'pass'
    assert host['room_id'] == guest['room_id']
    assert host['visibility'] == guest['visibility'] == args.visibility
    assert host['rom_sha256'] == guest['rom_sha256']
    assert host['started'] == guest['started'] == 'shared'
    assert host['established'] and guest['established']
    assert host['resumed_together'] and guest['resumed_together']
    assert host['frames'] >= 200 and guest['frames'] >= 200
    assert host['controller_ram'] == guest['controller_ram']
    if EXPECTED_RAM is not None:
        assert host['controller_ram'] == EXPECTED_RAM
    assert host['received_gameplay']['input'] > 0
    assert guest['received_gameplay']['frame'] > 0
    assert host['paused_hash'] == guest['paused_hash']
    assert guest['rom_argument_received'] is False and guest['file_chooser_count'] == 0
    assert host['filename_absent_from_websocket']
    assert not host['page_errors'] and not guest['page_errors']
    assert host['continuous_play_seconds'] >= args.play_seconds
    assert guest['continuous_play_seconds'] >= args.play_seconds
    if args.play_seconds:
        for player in (host, guest):
            assert player['measured_fps'] > 0
            assert player['ping_ms'] >= 0 and math.isfinite(player['ping_ms'])
            assert player['routes'] and all(route in ('direct', 'relay') for route in player['routes'])
    for role in ('host','guest'):
        for view in ('playing','paused'):
            assert (SESSION / f'{role}-{view}.png').stat().st_size > 0
    result = {
        'result': 'pass', 'claim': 'Two independent browser processes played the same NES game',
        'room_id': host['room_id'], 'visibility': args.visibility,
        'rom_sha256': host['rom_sha256'], 'controller_ram': host['controller_ram'],
        'paused_hash': host['paused_hash'], 'host_frames': host['frames'],
        'guest_frames': guest['frames'], 'host_received_inputs': host['received_gameplay']['input'],
        'guest_received_frames': guest['received_gameplay']['frame'],
        'fixed_shell_through_pause_and_resume': True,
        'guest_rom_argument_received': False, 'guest_file_chooser_count': 0,
        'host_filename_absent_from_websocket': True,
        'host_elapsed_seconds': host['elapsed_seconds'],
        'guest_elapsed_seconds': guest['elapsed_seconds'],
        'continuous_play_seconds': min(host['continuous_play_seconds'], guest['continuous_play_seconds']),
        'host_metrics': {key: host[key] for key in ('measured_fps', 'ping_ms', 'routes')},
        'guest_metrics': {key: guest[key] for key in ('measured_fps', 'ping_ms', 'routes')},
    }
    save('result.json', result)
    print(json.dumps(result, indent=2))


def run_pair():
    if not args.rom:
        parser.error('run needs --rom')
    if any((SESSION / name).exists() for name in ('host-ready.json','host.json','guest.json')):
        parser.error('run needs a fresh --session-dir')
    with (SESSION / 'server.log').open('w') as server_log:
        service = None
        try:
            url = args.url
            if not url:
                service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                                           stdout=subprocess.PIPE, stderr=server_log, text=True)
                line = service.stdout.readline()
                if not line:
                    raise RuntimeError('The browser gateway exited before reporting its URL')
                url = json.loads(line)['url']
            workers = []
            with (SESSION / 'host.log').open('w') as host_log, (SESSION / 'guest.log').open('w') as guest_log:
                for role, log in (('host',host_log),('guest',guest_log)):
                    rom_arg = ['--rom', str(args.rom.resolve())] if role == 'host' else []
                    command = [sys.executable, __file__, '--role', role, '--url', url,
                               *rom_arg, '--runtime-root', str(ROOT), '--session-dir', str(SESSION),
                               '--width', str(args.width), '--height', str(args.height),
                               '--zoom', str(args.zoom), '--visibility', args.visibility,
                               '--play-seconds', str(args.play_seconds)]
                    if args.expect_controller_ram:
                        command.extend(['--expect-controller-ram', args.expect_controller_ram])
                    workers.append(subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT))
                deadline = time.monotonic() + 80
                try:
                    while time.monotonic() < deadline:
                        statuses = [worker.poll() for worker in workers]
                        if all(status == 0 for status in statuses):
                            break
                        if any(status is not None and status != 0 for status in statuses):
                            raise RuntimeError(f'Player processes failed: {statuses}')
                        time.sleep(.1)
                    else:
                        raise TimeoutError('Player processes exceeded 80 seconds')
                finally:
                    for worker in workers:
                        if worker.poll() is None:
                            worker.terminate()
                            worker.wait(timeout=5)
        except Exception:
            for role in ('host','guest'):
                log = SESSION / f'{role}.log'
                if log.exists():
                    print(f'{role} log:\n{log.read_text()[-6000:]}', file=sys.stderr)
            raise
        finally:
            if service:
                service.terminate()
                service.wait(timeout=5)
    verify()


def player():
    if not args.url or (args.role == 'host' and not args.rom) or (args.role == 'guest' and args.rom):
        parser.error('host needs --url and --rom; guest needs --url without --rom')
    rom = args.rom.read_bytes() if args.rom else None
    rom_hash = hashlib.sha256(rom).hexdigest() if rom else None
    errors = []
    sent_frames = []
    private_name = 'LOCAL-PRIVATE-GAME.nes'
    started = time.monotonic()
    with sync_playwright() as playwright, ExitStack() as resources:
        zoom_worker = None
        if args.zoom == 2:
            context, zoom_worker = resources.enter_context(zoom_context(playwright, {
                'width': args.width * 2, 'height': args.height * 2}))
            page = context.new_page()
            browser = context.browser
        else:
            browser = playwright.chromium.launch(ignore_default_args=['--mute-audio'])
            resources.callback(browser.close)
            context = browser.new_context(viewport={'width': args.width, 'height': args.height},
                                          permissions=['clipboard-read','clipboard-write'])
            page = context.new_page()
        wait_for_page = lambda expression, **kwargs: page.wait_for_function(expression, polling=100, **kwargs)
        try:
            context.grant_permissions(['clipboard-read','clipboard-write'], origin=args.url)
            page.set_default_timeout(15000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('websocket', lambda socket: socket.on('framesent', lambda raw: sent_frames.append(raw)))
            page.add_init_script((ROOT / 'scripts/gameplay/fixture.js').read_text() + """
              (()=>{const Socket=WebSocket;window.WebSocket=class extends Socket{
                constructor(...args){super(...args);this.addEventListener('message',event=>{
                  try{const packet=JSON.parse(event.data);
                    const room=packet.type==='result'&&packet.ok?packet.data?.room:undefined;
                    if(room)proof.room=room;
                  }catch{}
                });}
              };})();
            """)
            page.goto(args.url)
            zoom_receipt = browser_zoom(page, zoom_worker, 2) if zoom_worker else None
            page.locator('.rc-listing').wait_for()
            file_choosers = []
            page.on('filechooser', lambda chooser: file_choosers.append(chooser))

            if args.role == 'host':
                page.get_by_role('button', name='Host a new game').click()
                rename_lobby(page, LOBBY_NAME)
                if args.visibility == 'protected':
                    protect_lobby(page, 'blue-sky-room')
                page.get_by_role('button', name='Load NES game').wait_for()
                page.locator('input[aria-label="NES cartridge file"]').set_input_files({
                    'name':private_name,'mimeType':'application/octet-stream','buffer':rom})
                page.get_by_role('button', name='Change game').wait_for(timeout=30000)
                wait_for_page('proof.room?.fingerprint && proof.room?.role==="host"')
                room = page.evaluate('proof.room')
                assert room['visibility'] == args.visibility and room['occupancy'] == 1
                assert room['fingerprint']['romSha256'] == rom_hash
                assert page.get_by_role('button', name='Start →').count() == 0
                page.get_by_role('button', name='Copy invite').click()
                invitation = page.evaluate('navigator.clipboard.readText()')
                expect(page.get_by_role('button', name='Ready', exact=True)).to_be_enabled(timeout=30000)
                page.get_by_role('button', name='Ready', exact=True).click()
                save('host-ready.json', {'room_id': room['id'], 'invitation': invitation})
                prepared = wait_for('guest-ready.json')
                wait_for_page('member=>proof.room?.game?.ready?.includes(member)',
                                       arg=prepared['member_id'], timeout=30000)
                if page.get_by_role('button', name='Ready', exact=True).count():
                    expect(page.get_by_role('button', name='Ready', exact=True)).to_be_enabled(timeout=30000)
                    page.get_by_role('button', name='Ready', exact=True).click()
                expect(page.get_by_role('button', name='Start →')).to_be_enabled(timeout=30000)
                page.get_by_role('button', name='Start →').click()
            else:
                expected = wait_for('host-ready.json')
                if args.visibility == 'protected':
                    page.goto(expected['invitation'])
                    if zoom_worker:
                        zoom_receipt = browser_zoom(page, zoom_worker, 2)
                    page.get_by_label('Lobby password').fill('blue-sky-room')
                    page.get_by_role('button', name='Join lobby', exact=True).click()
                else:
                    page.locator('.rc-listing').wait_for()
                    page.get_by_placeholder('Search lobbies').fill(LOBBY_NAME)
                    page.locator('.rc-lobby-card').filter(has_text=LOBBY_NAME).click()
                wait_for_page('proof.room?.role==="member"')
                assert page.evaluate('proof.room.id') == expected['room_id']
                rom_hash = page.evaluate('proof.room.fingerprint.romSha256')
                expect(page.get_by_role('button', name='Ready', exact=True)).to_be_enabled(timeout=30000)
                page.get_by_role('button', name='Ready', exact=True).click()
                save('guest-ready.json', {'member_id': page.evaluate('proof.room.chatMembership')})

            wait_for_page('proof.room?.established && proof.room?.started==="shared" && proof.room?.game?.status==="playing"',
                                   timeout=30000)
            page.evaluate('releaseFrames()')
            # A server Playing update can arrive before this browser has begun local frames.
            # Keydown is ignored until the local player is running.
            wait_for_page('proof.frameCount >= 10', timeout=30000)
            page.locator('canvas').focus()
            assert page.evaluate("document.activeElement === document.querySelector('canvas')")
            page.keyboard.press('Space')
            held_from = page.evaluate('proof.frameCount')
            page.keyboard.down('z' if args.role == 'host' else 'c')
            play_started = time.monotonic()
            play_frame = held_from
            while time.monotonic() - play_started < args.play_seconds:
                wait_for_page('previous => proof.frameCount > previous', arg=play_frame, timeout=5000)
                play_frame = page.evaluate('proof.frameCount')
                assert page.evaluate('proof.room?.game?.status === "playing" && !proof.workloadStopped'), 'Shared play stopped during the live check'
                page.wait_for_timeout(250)
            continuous_play_seconds = round(time.monotonic() - play_started, 2)
            measured_fps = round((play_frame-held_from)/continuous_play_seconds, 2) if args.play_seconds else None
            rtts = page.evaluate('proof.admission.nonceRttMs')
            ping_ms = round(statistics.median(rtts), 2) if rtts else None
            reported_routes = {}
            for raw in sent_frames:
                try:
                    packet = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    continue
                if packet.get('type') == 'peerRoute':
                    reported_routes[packet['pairId']] = packet['route']
            routes = [reported_routes.get(peer['pairId']) for peer in page.evaluate('proof.room.peers')]
            wait_for_page('target => proof.frameCount >= target', arg=max(220, held_from + 60), timeout=30000)
            if EXPECTED_RAM is not None:
                page.evaluate("currentWorker.postMessage({type:'state-export',requestId:900000})")
                wait_for_page('Array.isArray(proof.controllerRam)', timeout=10000)
                controller_ram = page.evaluate('proof.controllerRam')
                assert controller_ram == EXPECTED_RAM, controller_ram
            else:
                controller_ram = None
            save(f'{args.role}-sampled.json', {'controller_ram': controller_ram})
            wait_for(f'{"guest" if args.role == "host" else "host"}-sampled.json', 15)
            page.keyboard.up('z' if args.role == 'host' else 'c')
            frames = page.evaluate('proof.frameCount')
            shell = shell_bounds(page)
            screenshot(page, f'{args.role}-playing.png')
            save(f'{args.role}-playing-captured.json', {'frames': frames})
            wait_for(f'{"guest" if args.role == "host" else "host"}-playing-captured.json', 15)
            if args.role == 'guest':
                page.keyboard.press('p')
                save('guest-200.json', {'frames': frames})
            else:
                wait_for('guest-200.json', 30)
            wait_for_page('proof.room?.game?.status==="paused"', timeout=15000)
            wait_for_page('proof.hashes.length>0', timeout=15000)
            check_shell(page, shell)
            screenshot(page, f'{args.role}-paused.png')
            paused_hash = page.evaluate('proof.hashes.at(-1)')
            page.keyboard.press('p')
            wait_for_page('proof.room?.game?.ready?.includes(proof.room.chatMembership)', timeout=15000)
            check_shell(page, shell)
            if args.role == 'host':
                wait_for_page('proof.room?.game?.status==="resume_ready"', timeout=15000)
                page.keyboard.press('p')
            wait_for_page('proof.room?.game?.status==="playing"', timeout=15000)
            check_shell(page, shell)
            room = page.evaluate('proof.room')
            filename_absent = all(private_name not in (
                raw.decode('utf-8', errors='replace') if isinstance(raw, bytes) else raw
            ) for raw in sent_frames)
            assert filename_absent, 'The local NES filename appeared in a WebSocket frame.'
            evidence = {
                'result':'pass','role':args.role,'room_id':room['id'],'visibility':room['visibility'],
                'rom_sha256':rom_hash,'started':room['started'],'established':room['established'],
                'frames':frames,'controller_ram':controller_ram,'paused_hash':paused_hash,
                'received_gameplay':page.evaluate('proof.admission.received'),
                'resumed_together':True,'rom_argument_received':args.rom is not None,
                'file_chooser_count':len(file_choosers),'zoom_verified':verify_zoom(zoom_worker,zoom_receipt) if zoom_worker else None,
                'filename_absent_from_websocket':filename_absent,
                'elapsed_seconds':round(time.monotonic()-started,2),'page_errors':errors,
                'continuous_play_seconds':continuous_play_seconds,
                'measured_fps':measured_fps,'ping_ms':ping_ms,'routes':routes,
            }
            save(f'{args.role}.json', evidence)
            wait_for(f'{"guest" if args.role == "host" else "host"}.json', 15)
            print(json.dumps(evidence))
        except Exception:
            screenshot(page, f'{args.role}-failure.png')
            save(f'{args.role}-failure.json', {
                'role':args.role,'room':page.evaluate('window.proof?.room'),
                'frames':page.evaluate('window.proof?.frameCount'),
                'status':page.locator('.rc-status').all_inner_texts(),'page_errors':errors,
            })
            raise
        finally:
            if args.role == 'host':
                try:
                    page.set_default_timeout(3000)
                    back = page.get_by_role('button', name='Back to Main Page')
                    if back.is_visible():
                        back.click()
                        page.get_by_role('button', name='Close lobby', exact=True).click()
                        page.locator('.rc-listing').wait_for()
                except Exception as error:
                    print(f'Test lobby cleanup failed: {error}', file=sys.stderr)


def recovery():
    """Recover actual completed native progress into a fresh host/guest authority."""
    if not args.rom:
        parser.error('recovery needs --rom')
    started = time.monotonic()
    errors = []
    fixture = (ROOT / 'scripts/gameplay/fixture.js').read_text() + """
      (()=>{const Socket=WebSocket;window.WebSocket=class extends Socket{
        constructor(...args){super(...args);this.addEventListener('message',event=>{
          const value=JSON.parse(event.data);
          if(value.type==='result'&&value.ok){if(value.data.room)proof.room=value.data.room;
            if(value.data.session)proof.session=value.data.session;}
        });}
      };})();
    """
    def record(page):
        return page.evaluate("""()=>new Promise((resolve,reject)=>{
          const request=indexedDB.open('retro-coop-local');
          request.onerror=()=>reject(request.error);
          request.onsuccess=()=>{const db=request.result;
            const row=db.transaction('recovery').objectStore('recovery').get('host');
            row.onsuccess=()=>{db.close();resolve(row.result?{revision:row.result.revision,
              captures:row.result.captures.map(c=>({frame:c.frame,hash:c.hash,savedAt:c.savedAt}))}:null);};
          };
        })""")
    def wait_record(page, count, seconds):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            value=record(page)
            if value and len(value['captures'])>=count:
                return value
            page.wait_for_timeout(100)
        raise TimeoutError('The automatic host capture did not commit')
    def open_page(context, url):
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('console',lambda message:errors.append(message.text) if message.type=='error' else None)
        page.goto(url);page.evaluate('releaseFrames()');return page
    with sync_playwright() as playwright, ExitStack() as resources:
        if not args.url:
            log=resources.enter_context((SESSION/'server.log').open('w'))
            service=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=ROOT,stdout=subprocess.PIPE,stderr=log,text=True)
            def stop_service():
                if service.poll() is None:service.terminate()
                service.wait(timeout=5)
            resources.callback(stop_service)
            line=service.stdout.readline()
            if not line:raise RuntimeError('The recovery browser gateway did not start')
            args.url=json.loads(line)['url']
        browsers=[playwright.chromium.launch(ignore_default_args=['--mute-audio']) for _ in range(2)]
        for browser in browsers:resources.callback(browser.close)
        contexts=[browser.new_context(viewport={'width':args.width,'height':args.height},permissions=['clipboard-read','clipboard-write']) for browser in browsers]
        for context in contexts:context.add_init_script(fixture)
        host=open_page(contexts[0],args.url);guest=open_page(contexts[1],args.url)
        host.locator('.rc-identity .rc-header-edit').click()
        host.get_by_role('textbox',name='Your name').fill('Recovery Host')
        host.get_by_role('button',name='Save name',exact=True).click()
        host.get_by_role('button',name='Host a new game').click()
        host.wait_for_function('proof.room?.role==="host"')
        host.locator('input[aria-label="NES cartridge file"]').set_input_files(str(args.rom.resolve()))
        host.wait_for_function('proof.room?.fingerprint && proof.room?.matches',timeout=30000)
        old=host.evaluate('proof.room');old_token=host.evaluate('proof.session.token')
        invitation=args.url+'/#invite='+old['invite']
        guest.goto(invitation);guest.evaluate('releaseFrames()')
        guest.get_by_role('button',name='Join lobby',exact=True).click()
        expect(guest.get_by_role('button',name='Ready',exact=True)).to_be_enabled(timeout=30000)
        guest.get_by_role('button',name='Ready',exact=True).click()
        host.get_by_role('button',name='Ready',exact=True).click()
        host.get_by_role('button',name='Start →').click()
        host.wait_for_function('proof.frameCount>120',timeout=30000)
        guest.wait_for_function('proof.frameCount>120',timeout=30000)
        first=wait_record(host,1,35)
        assert first['captures'][0]['frame']>0
        # Brief signaling loss retains the live room and native game, without an offer.
        host.evaluate('proof.roomSocket.close()')
        host.get_by_role('button',name='Retry connection',exact=True).click()
        host.wait_for_function('id=>proof.room?.id===id',arg=old['id'])
        assert host.get_by_role('button',name='Restore game',exact=True).count()==0
        # Reconnect may have paused the shared timeline; prepare it before the next capture.
        for page in (host,guest):
            page.get_by_role('button',name='Prepare to resume',exact=True).click()
        host.get_by_role('button',name='Resume together',exact=True).click()
        host.wait_for_function('proof.room.game.status==="playing"')
        prior=host.evaluate('proof.frameCount');host.wait_for_function('prior=>proof.frameCount>prior+60',arg=prior)
        host.get_by_role('button',name='Pause',exact=True).click()
        host.wait_for_function('proof.room.game.status==="paused"')
        guest.wait_for_function('proof.room.game.status==="paused"')
        saved=wait_record(host,2,10);snapshot=saved['captures'][0]
        assert snapshot['frame']>first['captures'][0]['frame']
        screenshot(host,'recovery-original-paused.png')
        host.close()
        # Observe the production host reservation expiry; no clock or expiry mutation.
        guest.get_by_role('button',name='Host a new game').wait_for(timeout=100000)
        host=open_page(contexts[0],args.url)
        host.evaluate('sessionStorage.removeItem("retro-coop-guest")')
        host.reload();host.evaluate('releaseFrames()')
        host.wait_for_function('proof.session?.nickname==="Recovery Host"')
        assert host.evaluate('proof.session.token')!=old_token
        host.get_by_role('button',name='Host a new game').click()
        host.get_by_role('button',name='Restore game',exact=True).wait_for()
        new=host.evaluate('proof.room')
        assert new['id']!=old['id'] and new['chatMembership']!=old['chatMembership']
        assert new['host']=='Recovery Host'
        screenshot(host,'recovery-offer.png')
        new_invitation=args.url+'/#invite='+new['invite']
        guest.goto(invitation);guest.evaluate('releaseFrames()')
        guest.get_by_text('The host did not return. This lobby has closed.',exact=True).wait_for()
        assert guest.get_by_role('button',name='Join lobby',exact=True).is_disabled()
        guest.goto(new_invitation);guest.evaluate('releaseFrames()')
        guest.get_by_role('button',name='Join lobby',exact=True).click()
        host.wait_for_function('proof.room.occupancy===2')
        host.get_by_role('button',name='Restore game',exact=True).click()
        host.wait_for_function('proof.room?.started==="shared" && proof.room.game.status==="paused"',timeout=30000)
        host.wait_for_function('frame=>document.querySelector("canvas").dataset.frameCount===String(frame)',arg=snapshot['frame'])
        screenshot(host,'recovery-restored-paused.png')
        for page in (host,guest):
            expect(page.get_by_role('button',name='Prepare to resume',exact=True)).to_be_enabled(timeout=30000)
            page.get_by_role('button',name='Prepare to resume',exact=True).click()
        host.get_by_role('button',name='Resume together',exact=True).wait_for(timeout=30000)
        for page in (host,guest):
            page.evaluate("currentWorker.postMessage({type:'state-hash',requestId:900005})")
            page.wait_for_function('frame=>proof.hashes.at(-1)?.frame===frame',arg=snapshot['frame'])
            assert page.evaluate('proof.hashes.at(-1).hash')==snapshot['hash']
        host.get_by_role('button',name='Resume together',exact=True).click()
        guest.wait_for_function('proof.room.game.status==="playing"')
        guest.wait_for_function('frame=>Number(document.querySelector("canvas").dataset.frameCount)>frame+10',arg=snapshot['frame'])
        guest.locator('canvas').focus();guest.keyboard.down('c')
        for page in (host,guest):
            page.wait_for_timeout(300)
            page.evaluate("proof.controllerRam=undefined;currentWorker.postMessage({type:'state-export',requestId:900000})")
            page.wait_for_function('proof.controllerRam?.[1]===64')
        guest.keyboard.up('c');host.get_by_role('button',name='Pause',exact=True).click()
        for page in (host,guest):page.wait_for_function('proof.room.game.status==="paused"')
        for page in (host,guest):page.evaluate("currentWorker.postMessage({type:'state-hash',requestId:900005})")
        host.wait_for_timeout(100)
        hashes=[page.evaluate('proof.hashes.at(-1)') for page in (host,guest)]
        assert hashes[0]==hashes[1]
        screenshot(host,'recovery-continued-host.png');screenshot(guest,'recovery-continued-guest.png')
        host.get_by_role('button',name='Back to Main Page').click();host.get_by_role('button',name='Close lobby',exact=True).click()
        # A damaged newest state offers the older capture with its actual saved time.
        older=record(host)['captures'][1]
        host.evaluate("""()=>new Promise(resolve=>{const request=indexedDB.open('retro-coop-local');
          request.onsuccess=()=>{const db=request.result,tx=db.transaction('recovery','readwrite'),store=tx.objectStore('recovery');
            const row=store.get('host');row.onsuccess=()=>{const bytes=new Uint8Array(row.result.captures[0].bytes);bytes[bytes.length-1]^=1;store.put(row.result,'host');};
            tx.oncomplete=()=>{db.close();resolve();};};})""")
        host.get_by_role('button',name='Host a new game').click()
        host.get_by_role('button',name='Restore game',exact=True).click()
        host.get_by_text('You can try the older save shown below.',exact=False).wait_for()
        screenshot(host,'recovery-older-offer.png')
        host.get_by_role('button',name='Restore game',exact=True).click()
        host.wait_for_function('frame=>proof.room?.started==="shared"&&proof.room.game.frame===frame',arg=older['frame'])
        host.get_by_role('button',name='Back to Main Page').click();host.get_by_role('button',name='Close lobby',exact=True).click()
        # A different core cannot import the remembered machine state.
        original_core=old['fingerprint']['coreSha256']
        def change_core(core):
            host.evaluate("""core=>new Promise(resolve=>{const request=indexedDB.open('retro-coop-local');
              request.onsuccess=()=>{const db=request.result,tx=db.transaction('recovery','readwrite'),store=tx.objectStore('recovery');
                const row=store.get('host');row.onsuccess=()=>{for(const capture of row.result.captures)capture.fingerprint.coreSha256=core;store.put(row.result,'host');};
                tx.oncomplete=()=>{db.close();resolve();};};})""",core)
        change_core('f'*64)
        host.get_by_role('button',name='Host a new game').click()
        for _ in range(2):
            host.get_by_role('button',name='Restore game',exact=True).click()
        host.locator('.rc-dialog-card').wait_for(state='hidden')
        host.get_by_role('button',name=re.compile(r'Load NES game|^Change game$')).wait_for()
        assert not host.evaluate('proof.room.started')
        host.evaluate("currentWorker.postMessage({type:'state-hash',requestId:900005})")
        host.wait_for_function('proof.hashes.at(-1)?.frame===0')
        screenshot(host,'recovery-incompatible-core.png')
        host.get_by_role('button',name='Back to Main Page').click();host.get_by_role('button',name='Close lobby',exact=True).click()
        change_core(original_core)
        # A missing remembered ROM preserves ordinary loading and never announces a restore.
        host.evaluate("""()=>new Promise(resolve=>{const request=indexedDB.open('retro-coop-local');
          request.onsuccess=()=>{const db=request.result,tx=db.transaction('roms','readwrite');tx.objectStore('roms').clear();
            tx.oncomplete=()=>{db.close();resolve();};};})""")
        host.get_by_role('button',name='Host a new game').click()
        host.get_by_role('button',name='Restore game',exact=True).click()
        host.get_by_text('You can try the older save shown below.',exact=False).wait_for()
        if host.get_by_text('You can try the older save shown below.',exact=False).count():
            host.get_by_role('button',name='Restore game',exact=True).click()
        host.locator('.rc-dialog-card').wait_for(state='hidden')
        host.get_by_role('button',name=re.compile(r'Load NES game|^Change game$')).wait_for()
        assert not host.evaluate('proof.room.started')
        screenshot(host,'recovery-missing-rom.png')
        host.get_by_role('button',name='Back to Main Page').click();host.get_by_role('button',name='Close lobby',exact=True).click()
        host.get_by_role('button',name='Host a new game').click()
        host.get_by_role('button',name='Start fresh',exact=True).click()
        host.locator('.rc-dialog-card').wait_for(state='hidden')
        host.get_by_role('button',name=re.compile(r'Load NES game|^Change game$')).wait_for()
        assert record(host) is None
        host.evaluate("currentWorker.postMessage({type:'state-hash',requestId:900005})")
        host.wait_for_function('proof.hashes.at(-1)?.frame===0')
        host.get_by_role('button',name='Back to Main Page').click();host.get_by_role('button',name='Close lobby',exact=True).click()
        # Storage disabled by browser policy still permits the ordinary host/load/play journey.
        unavailable=contexts[0].browser.new_context(viewport={'width':args.width,'height':args.height})
        resources.callback(unavailable.close);unavailable.add_init_script(fixture)
        unavailable.add_init_script("Object.defineProperty(window,'indexedDB',{value:{open(){throw Error('Local storage is unavailable.');}},configurable:true})")
        offline=open_page(unavailable,args.url)
        offline.get_by_role('button',name='Host a new game').click()
        offline.wait_for_function('proof.room?.role==="host"')
        offline.locator('input[aria-label="NES cartridge file"]').set_input_files(str(args.rom.resolve()))
        expect(offline.get_by_role('button',name='Ready',exact=True)).to_be_enabled(timeout=30000)
        offline.get_by_role('button',name='Ready',exact=True).click();offline.get_by_role('button',name='Start →').click()
        offline.wait_for_function('proof.frameCount>10',timeout=30000)
        offline.get_by_role('button',name='Back to Main Page').click();offline.get_by_role('button',name='Close lobby',exact=True).click()
        assert not errors,errors
        result={'result':'pass','unavailable_storage_normal_play':True,'older_corrupt_capture_fallback':True,'incompatible_core_normal_flow':True,'missing_rom_normal_flow':True,'start_fresh_discards_offer':True,'natural_host_expiry':True,'replacement_guest_token':True,'remembered_name':'Recovery Host','original_capture':snapshot,'restored_matching_native_hash':True,'fresh_memberships_and_invite':True,'guest_real_controller_ram':[0,64],'continued_boundary':hashes[0],'brief_live_reconnect':True,'page_errors':errors,'elapsed_seconds':round(time.monotonic()-started,2)}
        save('recovery-result.json',result);print(json.dumps(result,indent=2))


if args.role == 'recovery':
    recovery()
elif args.role == 'verify':
    verify()
elif args.role == 'run':
    run_pair()
else:
    player()
