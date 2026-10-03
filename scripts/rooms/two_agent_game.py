#!/usr/bin/env python3
"""Prove two independent browsers play one host-selected NES game together."""

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
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
parser.add_argument('--role', choices=('host', 'guest', 'verify', 'run'), required=True)
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


if args.role == 'verify':
    verify()
elif args.role == 'run':
    run_pair()
else:
    player()
