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

from layout_geometry import browser_zoom, verify_zoom, zoom_context, control_visibility
from ui_helpers import choose_section, protect_lobby, rename_lobby, choose_audio


SOURCE = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--role', choices=('host', 'guest', 'verify', 'run', 'recovery', 'shared-load'), required=True)
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
parser.add_argument('--observer-churn', action='store_true', help='Join and leave as an unrelated observer during continuous play')
parser.add_argument('--required-peer-loss', action='store_true', help='Prove a departed controller fails the live check')
args = parser.parse_args()
ROOT = args.runtime_root.resolve()
SESSION = args.session_dir.resolve()
SESSION.mkdir(parents=True, exist_ok=True)
if not 0 <= args.play_seconds <= 30:
    parser.error('--play-seconds must be between 0 and 30')
if args.observer_churn and (args.role not in ('run', 'host', 'guest') or args.play_seconds < 10 or args.visibility != 'public'):
    parser.error('--observer-churn needs a public run with at least 10 play seconds')
if args.required_peer_loss and (args.role != 'run' or args.play_seconds < 10 or args.observer_churn):
    parser.error('--required-peer-loss needs a run with at least 10 play seconds')
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
    if args.observer_churn:
        assert host['observer_stop']['required'] is False
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
        'observer_stop': host['observer_stop'],
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
                    if args.observer_churn:
                        command.append('--observer-churn')
                    workers.append(subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT))
                deadline = time.monotonic() + 80
                try:
                    if args.required_peer_loss:
                        wait_for('host-live.json', 40)
                        wait_for('guest-live.json', 40)
                        workers[1].terminate()
                        workers[1].wait(timeout=5)
                        assert workers[0].wait(timeout=15) != 0, 'Host incorrectly passed after its controller left'
                        failure = wait_for('host-failure.json', 1)
                        assert any(stop['type'] == 'peerStop' and stop['required'] for stop in failure['stop_events']), failure
                        result = {'result': 'pass', 'required_stop': next(stop for stop in failure['stop_events'] if stop['type'] == 'peerStop' and stop['required'])}
                        save('required-peer-loss-result.json', result)
                        print(json.dumps(result, indent=2))
                        return
                    if args.observer_churn:
                        wait_for('host-live.json', 40)
                        wait_for('guest-live.json', 40)
                        invitation = wait_for('host-ready.json', 1)['invitation']
                        with sync_playwright() as playwright:
                            browser = playwright.chromium.launch(ignore_default_args=['--mute-audio'])
                            try:
                                context = browser.new_context(viewport={'width': args.width, 'height': args.height})
                                context.add_init_script((ROOT / 'scripts/gameplay/fixture.js').read_text())
                                observer = context.new_page()
                                observer.goto(invitation)
                                observer.evaluate('releaseFrames()')
                                observer.get_by_role('button', name='Join lobby', exact=True).click()
                                observer.wait_for_function('proof.room?.role === "member" && proof.room?.game?.status === "playing"', timeout=15000)
                                observer.wait_for_function('proof.room?.peers?.some(peer => peer.status === "connected")', timeout=15000)
                                observer_id = observer.evaluate('proof.room.chatMembership')
                                observer.get_by_role('button', name='Back to Main Page').click()
                                observer.get_by_role('button', name='Leave lobby', exact=True).click()
                                observer.locator('.rc-listing').wait_for(timeout=15000)
                                save('observer-left.json', {'member_id': observer_id})
                            finally:
                                browser.close()
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
                expect(page.get_by_role('button', name='Prepare', exact=True)).to_be_enabled(timeout=30000)
                page.get_by_role('button', name='Prepare', exact=True).click()
                save('host-ready.json', {'room_id': room['id'], 'invitation': invitation})
                prepared = wait_for('guest-ready.json')
                wait_for_page('member=>proof.room?.game?.ready?.includes(member)',
                                       arg=prepared['member_id'], timeout=30000)
                if page.get_by_role('button', name='Prepare', exact=True).count():
                    expect(page.get_by_role('button', name='Prepare', exact=True)).to_be_enabled(timeout=30000)
                    page.get_by_role('button', name='Prepare', exact=True).click()
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
                expect(page.get_by_role('button', name='Prepare', exact=True)).to_be_enabled(timeout=30000)
                page.get_by_role('button', name='Prepare', exact=True).click()
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
            play_epoch = page.evaluate('proof.activeEpoch')
            save(f'{args.role}-live.json', {'epoch': play_epoch})
            while time.monotonic() - play_started < args.play_seconds:
                wait_for_page('previous => proof.frameCount > previous', arg=play_frame, timeout=5000)
                play_frame = page.evaluate('proof.frameCount')
                assert page.evaluate('epoch => proof.room?.game?.status === "playing" && !proof.workloadStopped && proof.activeEpoch === epoch && proof.roomSocket?.readyState === WebSocket.OPEN', arg=play_epoch), 'Shared play stopped during the live check'
                page.wait_for_timeout(250)
            observer_stop = None
            if args.observer_churn and args.role == 'host':
                observer_id = wait_for('observer-left.json', 1)['member_id']
                stops = page.evaluate('proof.stopEvents')
                observer_stop = next((stop for stop in stops if stop['type'] == 'peerStop' and stop['member'] == observer_id and not stop['required']), None)
                assert observer_stop, stops
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
                page.evaluate("proof.controllerRam=undefined;(proof.acceptedLoadWorker??currentWorker).postMessage({type:'state-export',requestId:900000})")
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
                'observer_stop':observer_stop,
            }
            save(f'{args.role}.json', evidence)
            wait_for(f'{"guest" if args.role == "host" else "host"}.json', 15)
            print(json.dumps(evidence))
        except Exception:
            save(f'{args.role}-failure.json', {
                'role':args.role,'room':page.evaluate('''()=>{const room=window.proof?.room;return room?{id:room.id,role:room.role,status:room.status,matches:room.matches,started:room.started,occupancy:room.occupancy,fingerprint:room.fingerprint,game:room.game,slots:room.slots.map(slot=>({id:slot.id,role:slot.role,open:slot.open,member:slot.member?{id:slot.member.id,connected:slot.member.connected,acquisition:slot.member.acquisition}:undefined}))}:null}'''),
                'frames':page.evaluate('window.proof?.frameCount'),
                'active_epoch':page.evaluate('window.proof?.activeEpoch'),
                'socket_ready_state':page.evaluate('window.proof?.roomSocket?.readyState'),
                'stop_events':page.evaluate('window.proof?.stopEvents?.slice(-12)'),
                'recent_events':page.evaluate('window.proof?.events?.slice(-12)'),
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
      (()=>{const channels=[];proof.recoveryDiagnostics=[];
        const retain=value=>{proof.recoveryDiagnostics.push({at:Math.round(performance.now()),...value});if(proof.recoveryDiagnostics.length>80)proof.recoveryDiagnostics.shift();};
        const PC=RTCPeerConnection;window.RTCPeerConnection=class extends PC{constructor(...args){super(...args);this.addEventListener('datachannel',({channel})=>watch(channel));}createDataChannel(...args){const channel=super.createDataChannel(...args);watch(channel);return channel;}};
        function watch(channel){channels.push(channel);for(const event of ['open','close','error'])channel.addEventListener(event,()=>retain({kind:'channel',label:channel.label,state:channel.readyState,event}));}
        const Native=Worker;window.Worker=class extends Native{postMessage(data,...rest){if(data.type==='peer-checkpoint-bind'&&proof.failBinds?.length){const failure=proof.failBinds.shift();retain({kind:'native-request',type:data.type,requestId:data.requestId,epoch:data.epoch,frame:data.frame,hash:data.hash,failure});if(failure==='reject')queueMicrotask(()=>this.dispatchEvent(new MessageEvent('message',{data:{type:'peer-checkpoint-error',requestId:data.requestId,message:'Binding interrupted.'}})));return;}if(data.type.startsWith('peer-checkpoint-'))retain({kind:'native-request',type:data.type,requestId:data.requestId,epoch:data.epoch,frame:data.frame,hash:data.hash});return super.postMessage(data,...rest);}constructor(...args){super(...args);this.addEventListener('message',({data})=>{if(data.type==='error'||data.type.startsWith('peer-checkpoint-'))retain({kind:'native',type:data.type,requestId:data.requestId,message:data.message,epoch:data.epoch,frame:data.frame,hash:data.hash});});}};
        const Socket=WebSocket;window.WebSocket=class extends Socket{
        send(raw){const value=JSON.parse(raw);if(proof.rejectClose&&value.type==='close'){proof.rejectClose=false;proof.rejectedCloseRequest=value.requestId;const reject=()=>this.dispatchEvent(new MessageEvent('message',{data:JSON.stringify({type:'result',requestId:value.requestId,ok:false,error:'close_rejected'})}));if(proof.holdCloseFailure)proof.releaseCloseFailure=reject;else queueMicrotask(reject);return;}if(value.type==='gameRestore')proof.restoreRequest=value.requestId;if(value.type.startsWith('game'))retain({kind:'send',type:value.type,frame:value.frame,hash:value.hash,channels:channels.map(channel=>({label:channel.label,state:channel.readyState}))});return super.send(raw);}
        constructor(...args){super(...args);this.addEventListener('message',event=>{
          const value=JSON.parse(event.data);
          if(proof.holdRestoreResult&&value.type==='result'&&value.requestId===proof.restoreRequest&&!event.restoreReleased){event.stopImmediatePropagation();proof.releaseRestoreResult=()=>{proof.holdRestoreResult=false;const released=new MessageEvent('message',{data:proof.rejectRestoreResult?JSON.stringify({type:'result',requestId:value.requestId,ok:false,error:'restore_reply_lost'}):event.data});Object.defineProperty(released,'restoreReleased',{value:true});retain({kind:'restore-result-released'});this.dispatchEvent(released);};retain({kind:'restore-result-held'});return;}
          proof.recoveryResponses??=[];
          proof.recoveryResponses.push({type:value.type,reason:value.reason,requestId:value.requestId,
            ok:value.ok,code:value.error??value.code,message:value.message,
            preview:(value.preview??value.data?.preview)?{id:(value.preview??value.data.preview).id,status:(value.preview??value.data.preview).status,openSlots:(value.preview??value.data.preview).openSlots}:undefined});
          if(proof.recoveryResponses.length>40)proof.recoveryResponses.shift();
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
    def mute_game(page):
        selector=page.get_by_role('combobox',name='Settings section',include_hidden=True)
        prior=selector.locator('option:checked').inner_text()
        choose_audio(page, 'Game sound')
        mute=page.get_by_role('button',name='Mute game',exact=True)
        if mute.is_visible():mute.click()
        expect(page.get_by_role('button',name='Unmute game',exact=True)).to_be_visible()
        if selector.is_visible():selector.select_option(label=prior)
        else:page.get_by_role('button',name=prior,exact=True).click()
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
        def retain_failure():
            if sys.exc_info()[0] is None:
                return
            for index, context in enumerate(contexts):
                for page_index, page in enumerate(context.pages):
                    if page.is_closed():
                        continue
                    label=f'recovery-failure-{index}-{page_index}'
                    try:
                        page.set_default_timeout(2000)
                        save(label+'.json', {
                            'url':page.url,'body':page.locator('body').inner_text(),
                            'room':page.evaluate('''()=>{const room=window.proof?.room;return room?{id:room.id,role:room.role,status:room.status,matches:room.matches,started:room.started,occupancy:room.occupancy,fingerprint:room.fingerprint,game:room.game,slots:room.slots.map(slot=>({id:slot.id,role:slot.role,open:slot.open,member:slot.member?{id:slot.member.id,connected:slot.member.connected,acquisition:slot.member.acquisition}:undefined}))}:null}'''),
                            'session':page.evaluate('({nickname:window.proof?.session?.nickname,hasToken:!!window.proof?.session?.token})'),
                            'responses':page.evaluate('window.proof?.recoveryResponses'),
                            'synchronization':page.evaluate('window.proof?.recoveryDiagnostics'),
                            'events':page.evaluate('window.proof?.events?.slice(-12)'),
                            'page_errors':errors,
                        })
                    except Exception as error:
                        print(f'Could not retain {label}: {error}',file=sys.stderr)
        resources.callback(retain_failure)
        host.locator('.rc-identity .rc-header-edit').click()
        host.get_by_role('textbox',name='Your name').fill('Recovery Host')
        host.get_by_role('button',name='Save name',exact=True).click()
        host.get_by_role('button',name='Host a new game').click()
        host.wait_for_function('proof.room?.role==="host"')
        with host.expect_file_chooser() as chooser:
            host.get_by_role('button',name=re.compile(r'Load NES game')).click()
            host.get_by_role('button',name='Add game file',exact=True).click()
        chooser.value.set_files(str(args.rom.resolve()))
        host.wait_for_function('proof.room?.fingerprint && proof.room?.matches',timeout=30000)
        mute_game(host)
        old=host.evaluate('proof.room');old_token=host.evaluate('proof.session.token')
        invitation=args.url+'/#invite='+old['invite']
        guest.goto(invitation);guest.evaluate('releaseFrames()')
        guest.get_by_role('button',name='Join lobby',exact=True).click()
        expect(guest.get_by_role('button',name='Prepare',exact=True)).to_be_enabled(timeout=30000)
        mute_game(guest)
        guest.get_by_role('button',name='Prepare',exact=True).click()
        host.get_by_role('button',name='Prepare',exact=True).click()
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
        guest.get_by_text('The host did not return. This lobby has closed.',exact=True).wait_for()
        assert guest.evaluate('proof.recoveryResponses.some(event=>event.type==="ended" && event.reason==="host_expired")')
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
        # The guest is already at this invitation: goto alone is a same-document navigation.
        # Reload explicitly tests a fresh lookup, separately from the live expiry explanation.
        guest.goto(invitation);guest.reload();guest.evaluate('releaseFrames()')
        guest.get_by_text('This lobby is closed, unavailable, or the invitation has expired.',exact=True).wait_for()
        assert guest.get_by_role('button',name='Join lobby',exact=True).is_disabled()
        guest.goto(new_invitation);guest.evaluate('releaseFrames()')
        guest.get_by_role('button',name='Join lobby',exact=True).click()
        host.wait_for_function('proof.room.occupancy===2')
        host.evaluate('proof.holdRestoreResult=true;proof.rejectRestoreResult=true;proof.failBinds=["reject","timeout"]')
        host.get_by_role('button',name='Restore game',exact=True).click()
        host.wait_for_function('proof.room?.started==="shared" && proof.room.game.status==="paused"',timeout=30000)
        host.get_by_text('Game restored. Prepare to resume together.',exact=True).wait_for()
        host.wait_for_function('typeof proof.releaseRestoreResult==="function"')
        dialog=host.get_by_role('alertdialog');expect(dialog).to_be_visible()
        host.set_viewport_size({'width':320,'height':568})
        host.wait_for_function('document.querySelector(".rc-dialog-card")?.contains(document.activeElement)')
        for key in ('Tab','Shift+Tab','Tab','Shift+Tab','p','q','e'):
            host.keyboard.press(key);assert dialog.evaluate('node=>node.contains(document.activeElement)')
        box=dialog.bounding_box();assert box and box['x']>=0 and box['y']>=0 and box['x']+box['width']<=320 and box['y']+box['height']<=568,box
        screenshot(host,'recovery-bind-busy-narrow.png')
        assert host.evaluate('proof.room.game.status==="paused"&&!proof.recoveryDiagnostics.some(row=>row.type==="gameReady")')
        # Browser navigation can interrupt even a busy restore. Its committed reply must
        # retain the binding while Close is pending, then remain usable after rejection.
        host.evaluate('proof.rejectClose=true;proof.holdCloseFailure=true');host.go_back()
        host.get_by_role('button',name='Close lobby',exact=True).click()
        host.wait_for_function('typeof proof.releaseCloseFailure==="function"')
        host.evaluate('proof.releaseRestoreResult()')
        host.evaluate('proof.holdCloseFailure=false;proof.releaseCloseFailure()')
        host.get_by_role('alertdialog').get_by_text('Could not leave. Retry or stay in the lobby.',exact=True).wait_for()
        host.get_by_role('button',name='Stay',exact=True).click()
        for failure in ('reply','reject','timeout'):
            retry=host.get_by_role('button',name='Retry restoration',exact=True);expect(retry).to_be_enabled(timeout=15000)
            expect(host.get_by_role('button',name='Start fresh',exact=True)).to_have_count(0)
            assert host.evaluate('proof.recoveryDiagnostics.filter(row=>row.type==="gameRestore").length===1')
            assert host.evaluate('proof.room.game.frame')==snapshot['frame']
            if failure=='reply':
                screenshot(host,'recovery-bind-retry-narrow.png')
                host.get_by_role('button',name='Back to Main Page',exact=True).click()
                host.get_by_role('button',name='Stay',exact=True).click()
                expect(retry).to_be_enabled()
            if failure=='reject':
                host.evaluate('proof.rejectClose=true');host.get_by_role('button',name='Back to Main Page',exact=True).click()
                host.get_by_role('button',name='Close lobby',exact=True).click()
                host.get_by_role('alertdialog').get_by_text('Could not leave. Retry or stay in the lobby.',exact=True).wait_for()
                host.get_by_role('button',name='Stay',exact=True).click();expect(retry).to_be_enabled()
                assert host.evaluate('proof.room.game.frame')==snapshot['frame']
                screenshot(host,'recovery-rejected-close-stay.png')
            retry.click()
        host.get_by_role('alertdialog').wait_for(state='hidden')
        host.set_viewport_size({'width':args.width,'height':args.height})
        host.wait_for_function('proof.recoveryDiagnostics.some(row=>row.type==="peer-checkpoint-bound"&&row.epoch===proof.room.game.epoch)')
        host.wait_for_function('frame=>document.querySelector("canvas").dataset.frameCount===String(frame)',arg=snapshot['frame'])
        for page in (host,guest):mute_game(page)
        screenshot(host,'recovery-restored-paused.png')
        for page in (host,guest):
            expect(page.get_by_role('button',name='Prepare to resume',exact=True)).to_be_enabled(timeout=30000)
            page.get_by_role('button',name='Prepare to resume',exact=True).click()
        host.get_by_role('button',name='Resume together',exact=True).wait_for(timeout=30000)
        for page in (host,guest):
            page.evaluate("(proof.acceptedLoadWorker??currentWorker).postMessage({type:'state-hash',requestId:900005})")
            page.wait_for_function('frame=>proof.hashes.at(-1)?.frame===frame',arg=snapshot['frame'])
            assert page.evaluate('proof.hashes.at(-1).hash')==snapshot['hash']
        host.get_by_role('button',name='Resume together',exact=True).click()
        guest.wait_for_function('proof.room.game.status==="playing"')
        guest.wait_for_function('frame=>Number(document.querySelector("canvas").dataset.frameCount)>frame+10',arg=snapshot['frame'])
        guest.locator('canvas').focus();guest.keyboard.down('c')
        for page in (host,guest):
            page.wait_for_timeout(300)
            page.evaluate("proof.controllerRam=undefined;(proof.acceptedLoadWorker??currentWorker).postMessage({type:'state-export',requestId:900000})")
            page.wait_for_function('proof.controllerRam?.[1]===64')
        guest.keyboard.up('c');host.get_by_role('button',name='Pause',exact=True).click()
        for page in (host,guest):page.wait_for_function('proof.room.game.status==="paused"')
        for page in (host,guest):page.evaluate("(proof.acceptedLoadWorker??currentWorker).postMessage({type:'state-hash',requestId:900005})")
        host.wait_for_timeout(100)
        hashes=[page.evaluate('proof.hashes.at(-1)') for page in (host,guest)]
        assert hashes[0]==hashes[1]
        screenshot(host,'recovery-continued-host.png');screenshot(guest,'recovery-continued-guest.png')
        restore_diagnostics=[page.evaluate('proof.recoveryDiagnostics') for page in (host,guest)]
        # A full browser reload loses the emulator while this protected lobby survives.
        # Reacquisition must restore its automatic timeline before either player prepares.
        protect_lobby(host, 'live-recovery-password')
        live_room=host.evaluate('({id:proof.room.id,invite:proof.room.invite,visibility:proof.room.visibility,slots:proof.room.slots.map(s=>({id:s.id,role:s.role,name:s.member?.nickname})),epoch:proof.room.game.epoch})')
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            live_capture=record(host)['captures'][0]
            if live_capture['frame']==hashes[0]['frame'] and live_capture['hash']==hashes[0]['hash']:
                break
            host.wait_for_timeout(100)
        else:
            raise TimeoutError('The paused automatic capture did not complete')
        host.reload();host.evaluate('releaseFrames()')
        host.wait_for_function('old=>proof.room?.game.epoch!==old && proof.room?.game.status==="paused" && proof.recoveryDiagnostics.some(e=>e.type==="peer-checkpoint-imported")',arg=live_room['epoch'],timeout=30000)
        expect(host.locator('.rc-status')).to_contain_text('Automatic progress restored from')
        current_room=host.evaluate('({id:proof.room.id,invite:proof.room.invite,visibility:proof.room.visibility,slots:proof.room.slots.map(s=>({id:s.id,role:s.role,name:s.member?.nickname})),epoch:proof.room.game.epoch})')
        assert {k:v for k,v in live_room.items() if k!='epoch'}=={k:v for k,v in current_room.items() if k!='epoch'}
        imported=host.evaluate('proof.recoveryDiagnostics.filter(e=>e.type==="peer-checkpoint-imported").at(-1)')
        assert imported['frame']==live_capture['frame'] and imported['hash']==live_capture['hash'], (imported,live_capture)
        for page in (host,guest):
            if not page.evaluate('proof.room.game.ready.includes(proof.room.chatMembership)'):
                expect(page.get_by_role('button',name='Prepare to resume',exact=True)).to_be_enabled(timeout=30000)
                page.get_by_role('button',name='Prepare to resume',exact=True).click()
        expect(host.get_by_role('button',name='Resume together',exact=True)).to_be_enabled(timeout=30000)
        for page in (host,guest):
            page.evaluate('currentWorker.postMessage({type:"state-hash",requestId:900005})')
            page.wait_for_function('capture=>proof.hashes.at(-1)?.frame===capture.frame && proof.hashes.at(-1)?.hash===capture.hash',arg=live_capture)
        host.get_by_role('button',name='Resume together',exact=True).click()
        for page in (host,guest):page.wait_for_function('proof.room.game.status==="playing"')
        guest.locator('canvas').focus();guest.keyboard.down('c')
        for page in (host,guest):
            page.wait_for_timeout(300)
            page.evaluate('proof.controllerRam=undefined;currentWorker.postMessage({type:"state-export",requestId:900000})')
            page.wait_for_function('proof.controllerRam?.[1]===64')
        guest.keyboard.up('c');host.get_by_role('button',name='Pause',exact=True).click()
        for page in (host,guest):page.wait_for_function('proof.room.game.status==="paused"')
        # Recovery releases the automatic capture owner for subsequent play.
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if record(host)['captures'][0]['frame']==host.evaluate('proof.room.game.frame'):
                break
            host.wait_for_timeout(100)
        else:
            raise TimeoutError('Automatic captures did not resume after live recovery')
        screenshot(host,'recovery-live-host-restored.png')
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
        host.evaluate("proof.hashes=[];currentWorker.postMessage({type:'state-hash',requestId:900005})")
        host.wait_for_function('proof.hashes.at(-1)?.frame===0 && proof.hashes.at(-1)?.fresh===true')
        incompatible_fresh=host.evaluate('proof.hashes.at(-1)')
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
        # Independent storage faults use a separate session; the main recovery journey already
        # reaches the production limit of five new lobbies per session per minute.
        copied=host.evaluate("""()=>new Promise(resolve=>{const r=indexedDB.open('retro-coop-local');r.onsuccess=()=>{
          const db=r.result,tx=db.transaction('recovery'),row=tx.objectStore('recovery').get('host');
          row.onsuccess=()=>resolve({...row.result,captures:row.result.captures.map(c=>({...c,bytes:Array.from(new Uint8Array(c.bytes))}))});
          tx.oncomplete=()=>db.close();};})""")
        fault_context=contexts[0].browser.new_context(viewport={'width':args.width,'height':args.height})
        resources.callback(fault_context.close);fault_context.add_init_script(fixture)
        fault=open_page(fault_context,args.url)
        fault.wait_for_function("async()=> (await indexedDB.databases()).some(db=>db.name==='retro-coop-local')")
        fault.evaluate("""record=>new Promise(resolve=>{const r=indexedDB.open('retro-coop-local');r.onsuccess=()=>{
          const db=r.result,tx=db.transaction(['recovery','meta'],'readwrite');
          tx.objectStore('recovery').put({...record,captures:record.captures.map(c=>({...c,bytes:Uint8Array.from(c.bytes).buffer}))},'host');
          tx.objectStore('meta').put(record.revision,'recoveryRevision');tx.oncomplete=()=>{db.close();resolve();};};})""",copied)
        # A lookup belongs to its unused host membership, including after asynchronous completion.
        fault.evaluate("""()=>{window.recoveryTransaction=IDBDatabase.prototype.transaction;
          IDBDatabase.prototype.transaction=function(names,...args){const tx=recoveryTransaction.call(this,names,...args);
            if(Array.isArray(names)&&names.includes('recovery')&&args[0]==='readonly'){
              Object.defineProperty(tx,'oncomplete',{set(callback){tx.addEventListener('complete',event=>{
                window.releaseRecovery=()=>callback.call(tx,event);});}});}
            return tx;};}""")
        fault.get_by_role('button',name='Host a new game').click()
        fault.wait_for_function('typeof releaseRecovery==="function"')
        fault.evaluate('()=>{IDBDatabase.prototype.transaction=recoveryTransaction;}')
        fault.get_by_role('button',name='Back to Main Page').click();fault.get_by_role('button',name='Close lobby',exact=True).click()
        fault.get_by_role('button',name='Host a new game').wait_for()
        fault.evaluate('releaseRecovery()');fault.wait_for_timeout(100)
        expect(fault.get_by_role('button',name='Restore game',exact=True)).not_to_be_visible()
        # Another tab replaces an offered record. Start fresh remains a usable keyboard action,
        # dismisses only the local offer and cannot delete that newer record.
        fault.get_by_role('button',name='Host a new game').click()
        fault.get_by_role('button',name='Start fresh',exact=True).wait_for()
        other=fault_context.new_page();other.goto(args.url)
        other.evaluate("""()=>new Promise(resolve=>{const r=indexedDB.open('retro-coop-local');r.onsuccess=()=>{
          const db=r.result,tx=db.transaction(['recovery','meta'],'readwrite'),store=tx.objectStore('recovery'),row=store.get('host');
          row.onsuccess=()=>{const next={...row.result,revision:row.result.revision+1};store.put(next,'host');tx.objectStore('meta').put(next.revision,'recoveryRevision');};
          tx.oncomplete=()=>{db.close();resolve();};};})""")
        newer=record(fault)['revision'];other.close()
        fault.get_by_role('button',name='Start fresh',exact=True).focus();fault.keyboard.press('Enter')
        fault.locator('.rc-dialog-card').wait_for(state='hidden')
        fault.get_by_text('You can load a NES game normally.',exact=False).wait_for()
        fault.wait_for_function('document.activeElement?.matches(".rc-load-game")')
        assert record(fault)['revision']==newer
        screenshot(fault,'recovery-stale-start-fresh.png')
        fault.get_by_role('button',name='Back to Main Page').click();fault.get_by_role('button',name='Close lobby',exact=True).click()
        # A storage deletion failure also releases the blocker, preserving its durable record.
        fault.get_by_role('button',name='Host a new game').click();fault.get_by_role('button',name='Start fresh',exact=True).wait_for()
        fault.evaluate("""()=>{window.recoveryDelete=IDBObjectStore.prototype.delete;IDBObjectStore.prototype.delete=function(...args){
          if(this.name==='recovery')throw new DOMException('Device storage rejected deletion','UnknownError');return recoveryDelete.apply(this,args);};}""")
        fault.get_by_role('button',name='Start fresh',exact=True).focus();fault.keyboard.press('Enter')
        fault.locator('.rc-dialog-card').wait_for(state='hidden');fault.get_by_text('Device storage rejected deletion',exact=False).wait_for()
        fault.wait_for_function('document.activeElement?.matches(".rc-load-game")')
        fault.evaluate('()=>{IDBObjectStore.prototype.delete=recoveryDelete;}');assert record(fault)['revision']==newer
        screenshot(fault,'recovery-delete-failure.png')
        fault.get_by_role('button',name='Back to Main Page').click();fault.get_by_role('button',name='Close lobby',exact=True).click()
        fault_context.close()
        host.get_by_role('button',name='Host a new game').click()
        host.get_by_role('button',name='Start fresh',exact=True).click()
        host.locator('.rc-dialog-card').wait_for(state='hidden')
        host.get_by_role('button',name=re.compile(r'Load NES game|^Change game$')).wait_for()
        assert record(host) is None
        with host.expect_file_chooser() as chooser:
            host.get_by_role('button',name=re.compile(r'Load NES game')).click()
            host.get_by_role('button',name='Add game file',exact=True).click()
        chooser.value.set_files(str(args.rom.resolve()))
        expect(host.get_by_role('button',name='Prepare',exact=True)).to_be_enabled(timeout=30000)
        mute_game(host)
        host.evaluate("proof.hashes=[];currentWorker.postMessage({type:'state-hash',requestId:900005})")
        host.wait_for_function('proof.hashes.at(-1)?.frame===0 && proof.hashes.at(-1)?.fresh===true')
        start_fresh_native=host.evaluate('proof.hashes.at(-1)')
        host.get_by_role('button',name='Back to Main Page').click();host.get_by_role('button',name='Close lobby',exact=True).click()
        # Storage disabled by browser policy still permits the ordinary host/load/play journey.
        unavailable=contexts[0].browser.new_context(viewport={'width':args.width,'height':args.height})
        resources.callback(unavailable.close);unavailable.add_init_script(fixture)
        unavailable.add_init_script("Object.defineProperty(window,'indexedDB',{value:{open(){throw Error('Local storage is unavailable.');}},configurable:true})")
        offline=open_page(unavailable,args.url)
        offline.get_by_role('button',name='Host a new game').click()
        offline.wait_for_function('proof.room?.role==="host"')
        with offline.expect_file_chooser() as chooser:
            offline.get_by_role('button',name=re.compile(r'Load NES game')).click()
            offline.get_by_role('button',name='Add game file',exact=True).click()
        chooser.value.set_files(str(args.rom.resolve()))
        expect(offline.get_by_role('button',name='Prepare',exact=True)).to_be_enabled(timeout=30000)
        mute_game(offline)
        offline.get_by_role('button',name='Prepare',exact=True).click();offline.get_by_role('button',name='Start →').click()
        offline.wait_for_function('proof.frameCount>10',timeout=30000)
        offline.get_by_role('button',name='Back to Main Page').click();offline.get_by_role('button',name='Close lobby',exact=True).click()
        assert not errors,errors
        result={'result':'pass','live_host_refresh':{'capture':live_capture,'imported':imported,'same_protected_lobby':current_room,'matching_native_hash':True,'guest_real_controller_ram':[0,64]},'unavailable_storage_normal_play':True,'older_corrupt_capture_fallback':True,'incompatible_core_normal_flow':True,'incompatible_fresh_native':incompatible_fresh,'missing_rom_normal_flow':True,'start_fresh_discards_offer':True,'start_fresh_native':start_fresh_native,'late_offer_cannot_reopen_after_exit':True,'stale_start_fresh_keyboard_dismissal':True,'failed_delete_keyboard_dismissal':True,'natural_host_expiry':True,'replacement_guest_token':True,'remembered_name':'Recovery Host','fingerprint':old['fingerprint'],'original_capture':snapshot,'restore_acknowledgment_ordering':True,'committed_reply_during_rejected_close':True,'rejected_close_stay_keeps_retry':True,'committed_reply_and_bind_failures_retry':True,'busy_dialog_narrow_keyboard':True,'restore_synchronization':restore_diagnostics,'restored_matching_native_hash':True,'fresh_memberships_and_invite':True,'guest_real_controller_ram':[0,64],'continued_boundary':hashes[0],'brief_live_reconnect':True,'page_errors':errors,'elapsed_seconds':round(time.monotonic()-started,2)}
        save('recovery-result.json',result);print(json.dumps(result,indent=2))


def shared_load():
    """Use public Save/Load controls, then inspect actual native commit receipts."""
    if not args.rom:
        parser.error('shared-load needs --rom')
    started = time.monotonic()
    errors = []
    expected_download_errors=set()
    download_faults=[]
    def console_error(message):
        if message.type!='error':return
        if message.location.get('url') in expected_download_errors and message.text=='Failed to load resource: net::ERR_FAILED':
            expected_download_errors.discard(message.location['url']);return
        errors.append(message.text)
    def fail_first_download(page,stage):
        requests=[]
        def download(route):
            if route.request.method=='GET' and not requests:
                requests.append(route.request.url);expected_download_errors.add(route.request.url)
                download_faults.append({'stage':stage,'method':'GET','fault':'deliberate first ROM GET abort'});route.abort('failed')
            else:route.continue_()
        page.route('**/rooms/*/rom',download)
        return requests
    fixture = (ROOT / 'scripts/gameplay/fixture.js').read_text() + """
      const NativeWorker=Worker;
      proof.nativeLoadRequests=[];proof.nativeLoadReplies=[];
      window.Worker=class extends NativeWorker {
        postMessage(data,...options){
          if(this===proof.acceptedLoadWorker&&['peer-checkpoint-prepare','peer-checkpoint-commit','peer-checkpoint-rollback'].includes(data.type)){
            const fields=value=>({type:value.type,requestId:value.requestId,operationId:value.operationId,transactionId:value.transactionId,epoch:value.epoch,frame:value.frame,identity:value.identity,hash:value.hash,bytes:value.bytes?.byteLength,header:value.bytes?Array.from(new Uint8Array(value.bytes,0,Math.min(8,value.bytes.byteLength))):undefined});
            const request={original:fields(data),type:data.type,requestId:data.requestId,operationId:data.operationId,phase:proof.room?.game?.load?.phase,transactionId:proof.room?.game?.load?.id,event:proof.loadEvents?.at(-1)?.type,acceptedOwner:true};
            if(proof.rejectNativeLoad==='prepare'&&data.type==='peer-checkpoint-prepare'&&data.transactionId){
              proof.rejectNativeLoad=undefined;request.fault='corrupt-checkpoint';new Uint8Array(data.bytes)[0]^=255;
            }else if(proof.rejectNativeLoad==='commit'&&data.type==='peer-checkpoint-commit'){
              proof.rejectNativeLoad=undefined;request.fault='stale-native-operation';data={...data,operationId:data.operationId+'-invalid'};
            }
            request.sent=fields(data);proof.nativeLoadRequests.push(request);
          }
          return super.postMessage(data,...options);
        }
        constructor(...args){super(...args);this.addEventListener('message',({data})=>{
          if(['peer-checkpoint-prepared','peer-checkpoint-imported','peer-checkpoint-rolled-back','peer-checkpoint-error'].includes(data.type))proof.nativeLoadReplies.push({type:data.type,requestId:data.requestId,operationId:data.operationId,frame:data.frame,hash:data.hash,message:data.message,acceptedOwner:this===proof.acceptedLoadWorker});
          if(data.requestId===900005)proof.nativeProbe=data.type==='state-hash'?{info:data.info}:{error:data.message??data.type};
          if(data.type==='frame'&&data.epoch===proof.room?.game.epoch)proof.acceptedLoadWorker=this;
          if(['state-captured','peer-checkpoint-imported','peer-checkpoint-rolled-back'].includes(data.type)){
            proof.saveReceipts??=[];proof.saveReceipts.push({type:data.type,info:data.info,
              frame:data.frame,hash:data.hash,identity:data.identity,bytes:data.bytes?.byteLength});
          }
        });this.addEventListener('message',event=>{
          if(event.data.type!=='state-captured'||!proof.holdSaveCapture)return;
          const data=event.data;proof.heldSaveCapture={frame:data.frame,hash:data.hash};
          proof.releaseSaveCapture=()=>{proof.holdSaveCapture=false;this.dispatchEvent(new MessageEvent('message',{data}));};
          event.stopImmediatePropagation();
        });}
      };
      const RoomSocket=WebSocket;
      proof.readyAttempts=[];proof.commandTypes=new Map();proof.commandResults=[];proof.heldObserverCompletions=[];proof.observerSyncStops=[];
      window.WebSocket=class extends RoomSocket {
        send(raw){const value=JSON.parse(raw);if(value.type==='gameLoadBoundary'&&proof.holdLoadBoundary){proof.releaseLoadBoundary=()=>{proof.holdLoadBoundary=false;super.send(raw);};return;}if(value.type.startsWith('game'))proof.commandTypes.set(value.requestId,value.type);if(value.type==='gameReady')proof.readyAttempts.push({requestId:value.requestId});
          if(value.type==='gameObserved'&&proof.holdObserverCompletion){proof.heldObserverCompletions.push({raw,epoch:value.epoch,transferId:value.transferId,frame:value.frame});return;}return super.send(raw);}
        constructor(...args){super(...args);window.gameLoadSocket=this;proof.abortObservation=()=>this.send(JSON.stringify({type:'gameAbort',requestId:crypto.randomUUID(),epoch:proof.room.game.epoch,reason:'network'}));proof.releaseObserverCompletions=()=>{const held=proof.heldObserverCompletions.splice(0);for(const row of held)super.send(row.raw);return held.map(({raw,...row})=>row);};this.addEventListener('message',({data})=>{
          const value=JSON.parse(data);if(value.type==='result'&&value.ok&&value.data?.room)proof.room=value.data.room;
          if(value.type==='result'){if(proof.commandTypes.has(value.requestId))proof.commandResults.push({type:proof.commandTypes.get(value.requestId),ok:value.ok,error:value.error??value.code});const attempt=proof.readyAttempts.find(row=>row.requestId===value.requestId);if(attempt)attempt.result={ok:value.ok,error:value.error??value.code};}
          if(value.type==='gameSyncStop')proof.observerSyncStops.push({epoch:value.epoch,transferId:value.transferId});
          if(value.type.startsWith('gameLoad')){
            proof.loadEvents??=[];proof.loadEvents.push({type:value.type,transactionId:value.transactionId,
              epoch:value.epoch,frame:value.frame,hash:value.hash});
          }
        });}
      };
    """
    def native(page):
        page.evaluate("delete proof.nativeProbe;(proof.acceptedLoadWorker??currentWorker).postMessage({type:'state-hash',requestId:900005})")
        page.wait_for_function('proof.nativeProbe!==undefined')
        result=page.evaluate('proof.nativeProbe')
        assert 'error' not in result,result
        return result['info']
    def slot(page):
        return page.evaluate("""()=>new Promise((resolve,reject)=>{
          const request=indexedDB.open('retro-coop-local');request.onerror=()=>reject(request.error);
          request.onsuccess=()=>{const db=request.result,tx=db.transaction('saves','readonly'),all=tx.objectStore('saves').getAll();
            all.onsuccess=()=>{const row=all.result.find(row=>row.slot===1);resolve(row?{
              identity:row.identity,slot:row.slot,savedAt:row.savedAt,frame:row.frame,hash:row.hash,bytes:row.bytes.byteLength}:null);};
            tx.oncomplete=()=>db.close();};})""")
    def mute(page):
        choose_audio(page, 'Game sound')
        control=page.get_by_role('button',name='Mute game',exact=True)
        if control.is_visible():control.click()
        expect(page.get_by_role('button',name='Unmute game',exact=True)).to_be_visible()
        choose_section(page, 'Controls')
    def pause(host,guest):
        expect(host.get_by_role('button',name='Pause',exact=True)).to_be_enabled()
        expect(host.locator('.rc-footer')).not_to_have_attribute('inert','')
        host.locator('canvas').focus()
        host.keyboard.press('p')
        for page in (host,guest):page.wait_for_function('proof.room?.game?.status==="paused"&&!proof.room.game.load')
        snapshots=[native(page) for page in (host,guest)]
        assert snapshots[0]==snapshots[1],snapshots
        return snapshots[0]
    def resume(host,guest):
        for page in (host,guest):
            prepare=page.get_by_role('button',name='Prepare to resume',exact=True)
            geometry=prepare.evaluate('node=>{const b=node.getBoundingClientRect(),notice=node.closest(".rc-game-display").querySelector(".rc-game-save-status")?.getBoundingClientRect();return {button:b.toJSON(),notice:notice?.toJSON(),overlap:!!notice&&Math.min(b.right,notice.right)>Math.max(b.left,notice.left)&&Math.min(b.bottom,notice.bottom)>Math.max(b.top,notice.top)};}')
            assert not geometry['overlap'],geometry
            prepare.click()
            page.wait_for_function('proof.room.game.ready.includes(proof.room.chatMembership)')
        host.get_by_role('button',name='Resume together',exact=True).click()
        for page in (host,guest):page.wait_for_function('proof.room.game.status==="playing"&&proof.frames.at(-1)?.epoch===proof.room.game.epoch')
    with sync_playwright() as playwright, ExitStack() as resources:
        url=args.url
        if not url:
            log=resources.enter_context((SESSION/'server.log').open('w'))
            service=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=ROOT,stdout=subprocess.PIPE,stderr=log,text=True)
            resources.callback(lambda: (service.terminate(),service.wait(timeout=5)) if service.poll() is None else None)
            line=service.stdout.readline()
            if not line:raise RuntimeError('The shared Save/Load gateway did not start')
            url=json.loads(line)['url']
        browsers=[playwright.chromium.launch(ignore_default_args=['--mute-audio']) for _ in range(2)]
        for browser in browsers:resources.callback(browser.close)
        from unified_shell_browser import save_feedback
        print('shared Save/Load check: save_feedback',flush=True)
        save_feedback(browsers[0],url,SESSION)
        contexts=[browser.new_context(viewport={'width':args.width,'height':args.height},permissions=['clipboard-read','clipboard-write']) for browser in browsers]
        pages=[]
        for context in contexts:
            context.add_init_script(fixture)
            page=context.new_page();page.set_default_timeout(15000)
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('console',console_error)
            page.goto(url);page.evaluate('releaseFrames()');pages.append(page)
        host,guest=pages
        observer=None
        try:
            host.get_by_role('button',name='Host a new game').click()
            rename_lobby(host,LOBBY_NAME)
            with host.expect_file_chooser() as chooser:
                host.get_by_role('button',name=re.compile(r'Load NES game')).click()
                host.get_by_role('button',name='Add game file',exact=True).click()
            chooser.value.set_files(str(args.rom.resolve()))
            host.wait_for_function('proof.room?.matches&&proof.room.fingerprint')
            host.get_by_role('button',name='Copy invite',exact=True).click()
            invitation=host.evaluate('navigator.clipboard.readText()')
            prestart_requests=fail_first_download(guest,'before Start')
            guest.goto(invitation);guest.evaluate('releaseFrames()')
            guest.get_by_role('button',name='Join lobby',exact=True).click()
            guest.wait_for_function('proof.room?.slots.find(slot=>slot.member?.id===proof.room.chatMembership)?.member.acquisition==="failed"')
            assert len(prestart_requests)==1
            expect(guest.get_by_role('button',name='Retry game',exact=True)).to_be_enabled()
            guest.get_by_role('button',name='Retry game',exact=True).click()
            guest.wait_for_function('proof.room?.matches')
            for page in pages:mute(page)
            ready_deadline=time.monotonic()+30;ready_recoveries=[]
            def remaining_ready():
                remaining=int((ready_deadline-time.monotonic())*1000)
                assert remaining>0,'Shared Ready setup exceeded its deadline'
                return remaining
            while not host.get_by_role('button',name='Start →',exact=True).count():
                for label,page in zip(('host','guest'),pages):
                    page.wait_for_function('''()=>{const room=proof.room,owners=room?.game.controllers.owners;
                      return room?.matches&&room.slots.filter(slot=>slot.member&&slot.role!=='observer').every(slot=>slot.member.connected&&slot.member.acquisition==='loaded')
                        &&room.peers.filter(peer=>owners.includes(peer.member)||peer.member===room.hostMembership).every(peer=>peer.status==='connected');}''',timeout=remaining_ready())
                    if page.get_by_role('button',name='Cancel Ready',exact=True).count():continue
                    action=page.get_by_role('button',name=re.compile(r'^(Prepare|Retry preparation)$'))
                    if action.inner_text()=='Try Ready again':ready_recoveries.append({'visitor':label,'action':'Try Ready again'})
                    before=page.evaluate('proof.readyAttempts.length');action.click(timeout=remaining_ready())
                    outcome=page.wait_for_function('before=>proof.readyAttempts[before]?.result',arg=before,timeout=remaining_ready()).json_value()
                    if not outcome['ok']:
                        assert outcome['error'] in ('game_prerequisites','room_changed','stale_controllers'),outcome
                        ready_recoveries.append({'visitor':label,'error':outcome['error']})
                    else:page.wait_for_function('proof.room.game.ready.includes(proof.room.chatMembership)',timeout=remaining_ready())
            expect(host.get_by_role('button',name='Start →')).to_be_enabled()
            host.get_by_role('button',name='Start →').click()
            for page in pages:page.wait_for_function('proof.room.game.status==="playing"&&proof.frameCount>30')
            observer_context=browsers[0].new_context(viewport={'width':args.width,'height':args.height})
            observer_context.add_init_script(fixture)
            observer=observer_context.new_page();observer.set_default_timeout(15000)
            observer.on('pageerror',lambda error:errors.append(str(error)))
            observer.on('console',console_error)
            late_requests=fail_first_download(observer,'ongoing play')
            established=host.evaluate('({epoch:proof.room.game.epoch,owners:proof.room.game.controllers.owners,frames:proof.frameCount})')
            observer.goto(invitation);observer.evaluate('releaseFrames()')
            observer.get_by_role('button',name='Join lobby',exact=True).click()
            observer.wait_for_function('proof.room?.slots.find(slot=>slot.member?.id===proof.room.chatMembership)?.member.acquisition==="failed"')
            assert len(late_requests)==1
            retry=observer.get_by_role('button',name='Retry game',exact=True)
            expect(retry).to_be_enabled()
            for _ in range(40):
                observer.keyboard.press('Tab')
                if retry.evaluate('node=>node===document.activeElement'):break
            else:raise AssertionError('Ongoing-game download retry is not keyboard reachable')
            control_visibility(retry,require_focus=True)
            screenshot(observer,'ongoing-download-retry.png')
            observer.get_by_role('button',name='Retry game',exact=True).click()
            observer.wait_for_function('proof.room?.matches&&proof.frameCount>10')
            host.wait_for_function('before=>proof.frameCount>before.frames&&proof.room.game.epoch===before.epoch&&JSON.stringify(proof.room.game.controllers.owners)===JSON.stringify(before.owners)',arg=established)
            late_native=pause(host,guest)
            observer.wait_for_function('proof.room.game.status==="paused"')
            assert native(observer)==late_native
            screenshot(observer,'ongoing-download-recovered.png')
            resume(host,guest)
            mute(observer)
            host.keyboard.press('q')
            host.get_by_text('Saved to quick slot 1.',exact=True).wait_for()
            saved=slot(host)
            assert saved and saved['bytes']>72 and saved.get('frame') is not None and saved.get('hash'),saved
            host.wait_for_function('frame=>proof.frames.at(-1)?.frame>frame+60',arg=saved['frame'])
            assert host.evaluate('proof.room.game.status==="playing"')
            before=native(host)
            old_epoch=host.evaluate('proof.room.game.epoch')
            shell=shell_bounds(host)
            guest.evaluate('proof.holdSaveCapture=true')
            guest.locator('canvas').focus();guest.keyboard.press('q')
            guest.wait_for_function('typeof proof.releaseSaveCapture==="function"')
            held_save=guest.evaluate('proof.heldSaveCapture')
            host.get_by_role('button',name='Expand game to full screen',exact=True).click();host.locator('canvas').focus()
            host.keyboard.press('e')
            notice=host.locator('.rc-game-save-status').get_by_text('Saved progress loaded.',exact=True)
            expect(notice).to_be_visible(timeout=15000)
            expect(host.locator('.rc-game-progress')).to_be_visible()
            control_visibility(notice)
            assert notice.evaluate('n=>{const b=n.getBoundingClientRect(),hit=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2);return n.contains(hit)||n.parentElement.contains(hit);}')
            screenshot(host,'fullscreen-load-visible-during-start.png')
            host.get_by_role('button',name='Return to lobby view',exact=True).click()
            assert host.get_by_role('alertdialog').count()==0
            assert guest.get_by_role('alertdialog').count()==0
            for page in pages:
                page.wait_for_function('old=>proof.room.game.epoch!==old&&proof.room.game.status==="playing"&&!proof.room.game.load',arg=old_epoch)
                receipt=page.evaluate('proof.saveReceipts.filter(row=>row.type==="peer-checkpoint-imported").at(-1)')
                info=receipt.get('info') or receipt
                assert info['frame']==saved['frame'] and info['hash']==saved['hash'],(receipt,saved)
            check_shell(host,shell)
            # A different player changed the shared timeline while this save was
            # pending. Its native result must neither write nor describe the new one.
            guest.evaluate('proof.releaseSaveCapture()')
            expect(guest.get_by_text('Saved to quick slot 1.',exact=True)).to_have_count(0)
            assert slot(guest) is None
            guest.locator('canvas').focus();guest.keyboard.press('q')
            expect(guest.locator('.rc-game-save-status')).to_have_text('Saved to quick slot 1.')
            current_guest_save=slot(guest)
            assert current_guest_save and current_guest_save['bytes']>72
            screenshot(host,'shared-load-restored-host.png');screenshot(guest,'shared-load-restored-guest.png')
            observer.wait_for_function('old=>proof.room.game.epoch!==old&&proof.frames.at(-1)?.epoch===proof.room.game.epoch',arg=old_epoch)
            observer_epoch=observer.evaluate('proof.room.game.epoch')
            assert observer_epoch==host.evaluate('proof.room.game.epoch')
            assert observer.get_by_role('alertdialog').count()==0
            screenshot(observer,'shared-load-observer.png')
            observer.evaluate('proof.holdObserverCompletion=true')
            # Trusted P2 input must reach both real native machines after replacement.
            controller_ram=None
            if EXPECTED_RAM is not None:
                guest.keyboard.down('c')
                frame=guest.evaluate('proof.frameCount')
                guest.wait_for_function('n=>proof.frameCount>n+30',arg=frame)
                pause(host,guest)
                for page in pages:
                    page.evaluate("proof.controllerRam=undefined;(proof.acceptedLoadWorker??currentWorker).postMessage({type:'state-export',requestId:900000})")
                    page.wait_for_function('Array.isArray(proof.controllerRam)')
                    assert page.evaluate('proof.controllerRam')==EXPECTED_RAM
                controller_ram=EXPECTED_RAM
                guest.keyboard.up('c')
                resume(host,guest)
            # Restart prepares a fresh OSS machine, then uses the same atomic
            # replacement. Only its host confirmation needs human input.
            observer.evaluate('proof.holdObserverCompletion=false;proof.releaseObserverCompletions()')
            copies_before=slot(host)
            host.locator('canvas').focus();host.keyboard.press('n')
            restart_dialog=host.get_by_role('alertdialog',name='Restart this cartridge?')
            expect(restart_dialog).to_be_visible()
            host.get_by_role('button',name='Keep playing',exact=True).click()
            expect(restart_dialog).to_have_count(0)
            assert slot(host)==copies_before
            old_restart_epoch=host.evaluate('proof.room.game.epoch')
            host.keyboard.press('n');host.get_by_role('button',name='Restart cartridge',exact=True).click()
            for page in pages:page.wait_for_function('old=>proof.room.game.epoch!==old&&proof.room.game.status==="playing"&&!proof.room.game.load',arg=old_restart_epoch)
            fresh_restart=host.evaluate('proof.saveReceipts.filter(row=>row.type==="state-captured").at(-1)')
            assert fresh_restart['frame']==0,fresh_restart
            restart_imports=[page.evaluate('proof.saveReceipts.filter(row=>row.type==="peer-checkpoint-imported").at(-1)') for page in pages]
            assert all(row['frame']==0 and row['hash']==fresh_restart['hash'] for row in restart_imports),restart_imports
            assert slot(host)==copies_before
            expect(host.get_by_role('alertdialog')).to_have_count(0)
            expect(guest.get_by_role('alertdialog')).to_have_count(0)
            if EXPECTED_RAM is not None:
                guest.locator('canvas').focus();guest.keyboard.down('c')
                frame=guest.evaluate('proof.frameCount');guest.wait_for_function('n=>proof.frameCount>n+30',arg=frame)
                pause(host,guest)
                for page in pages:
                    page.evaluate("proof.controllerRam=undefined;(proof.acceptedLoadWorker??currentWorker).postMessage({type:'state-export',requestId:900000})")
                    page.wait_for_function('Array.isArray(proof.controllerRam)')
                    assert page.evaluate('proof.controllerRam')==EXPECTED_RAM
                guest.keyboard.up('c');resume(host,guest)
            # A successful Load of paused play stays paused without another
            # Prepare click or an acceptance menu; Resume is still explicit.
            pause(host,guest);paused_epoch=host.evaluate('proof.room.game.epoch')
            host.locator('canvas').focus();host.keyboard.press('e')
            for page in pages:page.wait_for_function('old=>proof.room.game.epoch!==old&&proof.room.game.status==="resume_ready"&&!proof.room.game.load',arg=paused_epoch)
            paused_load=[native(page) for page in pages]
            assert paused_load[0]==paused_load[1]
            assert paused_load[0]['frame']==saved['frame'] and paused_load[0]['hash']==saved['hash']
            host.get_by_role('button',name='Resume together',exact=True).click()
            for page in pages:page.wait_for_function('proof.room.game.status==="playing"&&proof.frames.at(-1)?.epoch===proof.room.game.epoch')
            observer.evaluate('proof.holdObserverCompletion=true')
            # Automatic loading still waits for real native pause boundaries.
            # Failure, the real barrier deadline and a replaced stored save all
            # preserve the previous machine; no human acceptance is involved.
            if EXPECTED_RAM is None:pause(host,guest);resume(host,guest)
            denials=[];observer_overlap=[]
            for decision in ('native-prepare-rejection','restart-commit-rejection','timeout','changed-save'):
                prior=pause(host,guest)
                observer.wait_for_function('proof.heldObserverCompletions.length>0')
                held=observer.evaluate('proof.heldObserverCompletions.map(({raw,...row})=>row)')
                native_fault=decision in ('native-prepare-rejection','restart-commit-rejection')
                guest.evaluate('(fault)=>{proof.holdLoadBoundary=!fault;proof.releaseLoadBoundary=undefined;proof.rejectNativeLoad=fault;proof.nativeLoadRequests=[];proof.nativeLoadReplies=[];}', 'prepare' if decision=='native-prepare-rejection' else 'commit' if decision=='restart-commit-rejection' else None)
                if decision=='restart-commit-rejection':
                    host.keyboard.press('n');host.get_by_role('button',name='Restart cartridge',exact=True).click()
                else:host.keyboard.press('e')
                if not native_fault:guest.wait_for_function('typeof proof.releaseLoadBoundary==="function"')
                observer.wait_for_function('proof.heldObserverCompletions.every(row=>proof.observerSyncStops.some(stop=>stop.transferId===row.transferId))')
                observer_overlap.append({'action':decision,'cancelled':held})
                observer.evaluate('proof.releaseObserverCompletions()')
                assert host.get_by_role('alertdialog').count()==0
                assert guest.get_by_role('alertdialog').count()==0
                if native_fault:
                    guest.wait_for_function('proof.nativeLoadRequests.some(row=>row.fault)&&proof.nativeLoadReplies.some(row=>row.type==="peer-checkpoint-error")')
                if decision=='changed-save':
                    host.evaluate("""()=>new Promise(resolve=>{const request=indexedDB.open('retro-coop-local');request.onsuccess=()=>{
                      const db=request.result,tx=db.transaction('saves','readwrite'),store=tx.objectStore('saves'),rows=store.getAll();
                      rows.onsuccess=()=>{const row=rows.result.find(row=>row.slot===1);store.put({...row,savedAt:row.savedAt+1});};
                      tx.oncomplete=()=>{db.close();resolve();};};})""")
                    guest.evaluate('proof.releaseLoadBoundary()')
                for page in pages:page.wait_for_function('proof.room.game.status==="paused"&&!proof.room.game.load',timeout=20000)
                snapshots=[native(page) for page in pages]
                assert snapshots[0]==snapshots[1]==prior,(decision,prior,snapshots)
                retry=host.get_by_role('button',name='Retry Restart' if decision=='restart-commit-rejection' else 'Retry Load',exact=True)
                expect(retry).to_be_visible()
                if decision=='restart-commit-rejection':
                    retry.click();expect(host.get_by_role('alertdialog',name='Restart this cartridge?')).to_be_visible()
                    host.get_by_role('button',name='Keep playing',exact=True).click()
                native_receipts=None
                if native_fault:
                    native_receipts=guest.evaluate('({requests:proof.nativeLoadRequests,replies:proof.nativeLoadReplies})')
                    fault=next(row for row in native_receipts['requests'] if row.get('fault'))
                    assert fault['acceptedOwner'] and fault['operationId']==fault['transactionId']
                    assert (fault['phase']=='staging' if decision=='native-prepare-rejection' else fault['event']=='gameLoadCommit'),native_receipts
                    rejection=next(row for row in native_receipts['replies'] if row['type']=='peer-checkpoint-error' and row['requestId']==fault['requestId'])
                    assert rejection['acceptedOwner'] and rejection['message'],native_receipts
                    assert fault['sent']['requestId']==rejection['requestId']
                    if decision=='native-prepare-rejection':assert fault['original']['header']!=fault['sent']['header'],native_receipts
                    else:assert fault['original']['operationId']!=fault['sent']['operationId'],native_receipts
                    if decision=='restart-commit-rejection':
                        assert any(row['type']=='peer-checkpoint-prepared' and row['operationId']==fault['operationId'] for row in native_receipts['replies']),native_receipts
                    assert any(row['type']=='peer-checkpoint-rolled-back' and row['frame']==prior['frame'] and row['hash']==prior['hash'] for row in native_receipts['replies']),native_receipts
                denials.append({'action':decision,'preserved':prior,'matching_retry':True,'native_receipts':native_receipts})
                guest.evaluate('proof.holdLoadBoundary=false;proof.releaseLoadBoundary=undefined')
                resume(host,guest)
            observed_before=observer.evaluate("proof.commandResults.length")
            observer.evaluate("proof.holdObserverCompletion=false;proof.releaseObserverCompletions()")
            observer.wait_for_function('before=>proof.commandResults.slice(before).some(row=>row.type==="gameObserved"&&row.ok)',arg=observed_before)
            observer.wait_for_function('proof.frames.at(-1)?.epoch===proof.room.game.epoch&&proof.room.game.status==="playing"')
            final_observer_epoch=observer.evaluate("proof.room.game.epoch")
            assert final_observer_epoch==host.evaluate("proof.room.game.epoch")
            # Every Local data confirmation shares the shell blocker and returns keyboard focus.
            choose_section(host, 'Controls');host.get_by_role('button',name='Local data',exact=True).click()
            host.get_by_role('button',name='Saves',exact=True).click()
            for action in ('Delete save','Delete all local data'):
                trigger=host.get_by_role('button',name=action,exact=True);trigger.click()
                dialog=host.get_by_role('alertdialog',name='Confirm local data action');expect(dialog).to_be_visible()
                for key in ('Tab','Tab','Shift+Tab','Shift+Tab'):
                    host.keyboard.press(key)
                    assert dialog.evaluate('node=>node.contains(document.activeElement)')
                assert host.locator('.rc-tool-back').evaluate('node=>!!node.closest("[inert]")')
                host.keyboard.press('Escape');expect(dialog).to_have_count(0)
                expect(trigger).to_be_focused()
            host.get_by_role('button',name='Back',exact=True).click();choose_section(host, 'Controls')
            # A production-format byte-only copy remains usable after refresh in a new lobby.
            restored_epoch=host.evaluate('proof.room.game.epoch')
            host.get_by_role('button',name='Back to Main Page',exact=True).click()
            host.get_by_role('button',name='Close lobby',exact=True).click()
            host.locator('.rc-listing').wait_for()
            host.reload();host.evaluate('releaseFrames()');host.locator('.rc-listing').wait_for()
            host.evaluate("""()=>new Promise(resolve=>{const request=indexedDB.open('retro-coop-local');request.onsuccess=()=>{
              const db=request.result,tx=db.transaction('saves','readwrite'),store=tx.objectStore('saves'),rows=store.getAll();
              rows.onsuccess=()=>{const row=rows.result.find(row=>row.slot===1);delete row.frame;delete row.hash;store.put(row);};
              tx.oncomplete=()=>{db.close();resolve();};};})""")
            host.get_by_role('button',name='Host a new game').click()
            host.wait_for_function('proof.room?.role==="host"')
            fresh=host.get_by_role('button',name='Start fresh',exact=True)
            fresh.wait_for();fresh.click()
            host.get_by_role('alertdialog').wait_for(state='hidden')
            with host.expect_file_chooser() as chooser:
                host.get_by_role('button',name=re.compile(r'Load NES game')).click()
                host.get_by_role('button',name='Add game file',exact=True).click()
            chooser.value.set_files(str(args.rom.resolve()))
            host.wait_for_function('proof.room?.matches&&proof.room.fingerprint')
            assert not host.evaluate('proof.room.started')
            mute(host)
            host.keyboard.press('e');
            host.wait_for_function('proof.room.started==="shared"&&proof.room.game.status==="resume_ready"&&!proof.room.game.load')
            host.get_by_role('button',name='Resume together',exact=True).click()
            host.wait_for_function('proof.room.game.status==="playing"&&proof.frames.at(-1)?.epoch===proof.room.game.epoch')
            legacy=host.evaluate('proof.saveReceipts.filter(row=>row.type==="peer-checkpoint-imported").at(-1)')
            assert legacy['frame']==0 and legacy['hash']==saved['hash'],(legacy,saved)
            legacy_slot=slot(host);assert legacy_slot.get('frame') is None and legacy_slot.get('hash') is None
            screenshot(host,'shared-load-later-byte-only.png')
            assert not errors,errors
            save('shared-load-result.json' ,{'result':'pass','rom_sha256':hashlib.sha256(args.rom.read_bytes()).hexdigest(),
                'download_recovery_faults':download_faults,'late_download_native':late_native,'established_during_recovery':established,'saved':saved,'advanced_native':before,'old_epoch':old_epoch,'new_epoch':restored_epoch,'observer_epoch':observer_epoch,'later_byte_only_native':legacy,
                'direct_load':True,'paused_intent_preserved':paused_load,'restart_fresh_capture':fresh_restart,'restart_native_imports':restart_imports,'obsolete_guest_save_suppressed':held_save,'current_guest_save':current_guest_save,'native_commit_receipts':[page.evaluate('proof.saveReceipts') for page in pages],
                'command_results':[page.evaluate('proof.commandResults') for page in [*pages,observer]],'ready_recoveries':ready_recoveries,'superseded_observer_transfers':observer_overlap,'final_observer_epoch':final_observer_epoch,'cancelled_loads':denials,'controller_ram':controller_ram,'page_errors':errors,'elapsed_seconds':round(time.monotonic()-started,2)})
        except Exception:
            for index,page in enumerate([*pages,observer] if observer is not None else pages):
                save(f'shared-load-{index}-failure.json',{'status':page.locator('.rc-status').all_inner_texts(),
                    'visible_controls':page.locator('button:visible').all_text_contents(),'focused':page.evaluate('({tag:document.activeElement?.tagName,label:document.activeElement?.getAttribute("aria-label")})'),'game':page.evaluate('proof.room?.game'),'peers':page.evaluate('proof.room?.peers'),'command_results':page.evaluate('proof.commandResults'),'events':page.evaluate('proof.loadEvents??[]'),
                    'native':page.evaluate('proof.saveReceipts??[]'),'held_observer_completions':page.evaluate('proof.heldObserverCompletions?.map(({raw,...row})=>row)??[]'),'observer_sync_stops':page.evaluate('proof.observerSyncStops??[]'),'page_errors':errors})
            raise
        finally:
            try:
                host.set_default_timeout(3000)
                host.get_by_role('button',name='Back to Main Page',exact=True).click()
                host.get_by_role('button',name='Close lobby',exact=True).click()
                host.locator('.rc-listing').wait_for()
            except Exception as error:print(f'Test lobby cleanup failed: {error}',file=sys.stderr)


if args.role == 'shared-load':
    shared_load()
elif args.role == 'recovery':
    recovery()
elif args.role == 'verify':
    verify()
elif args.role == 'run':
    run_pair()
else:
    player()
