"""Prove five-member microphone fanout, background mute, and isolated departure."""
import argparse
import contextlib
import json
import hashlib
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright
from background_smoke import write_tone

ROOT = Path(__file__).resolve().parents[2]
ENERGY = """async () => {
 const reports = await Promise.all(pcs.filter(pc=>pc.connectionState==='connected').map(pc=>pc.getStats()));
 return reports.reduce((sum,report)=>sum+[...report.values()]
  .filter(s=>s.type==='inbound-rtp'&&s.kind==='audio')
  .reduce((n,s)=>n+(s.totalAudioEnergy??0),0),0);
}"""
BOUNDS = """() => {
 const current=pcs.filter(pc=>pc.connectionState!=='closed');
 const tracks=captures.flatMap(s=>s.getAudioTracks());
 const live=tracks.filter(t=>t.readyState==='live');
 const senders=current.flatMap(pc=>pc.getSenders()).filter(s=>s.track?.kind==='audio');
 return {captures:captures.length,live:live.length,peers:current.length,senders:senders.length,
  sameTrack:senders.every(s=>s.track===live[0]),enabled:live[0]?.enabled};
}"""


def energy_arrives(receivers):
    before = [page.evaluate(ENERGY) for page in receivers]
    deadline = time.monotonic() + 12
    while True:
        delta = [page.evaluate(ENERGY) - value for page, value in zip(receivers, before)]
        if all(value > .00001 for value in delta):
            return delta
        assert time.monotonic() < deadline, f'not all receivers decoded audio: {delta}'
        time.sleep(.1)


def energy_stops(receivers):
    last = [page.evaluate(ENERGY) for page in receivers]
    stable = time.monotonic()
    deadline = stable + 8
    while time.monotonic() < deadline:
        time.sleep(.1)
        current = [page.evaluate(ENERGY) for page in receivers]
        if any(now - previous > .000001 for now, previous in zip(current, last)):
            stable = time.monotonic()
        if time.monotonic() - stable >= 1:
            return
        last = current
    raise AssertionError('decoded audio continued after explicit microphone mute')


def bounds(pages, peers):
    snapshots = [page.evaluate(BOUNDS) for page in pages]
    for value in snapshots:
        assert value['captures'] == value['live'] == 1, value
        assert value['peers'] == value['senders'] == peers, value
        assert value['sameTrack'], value
    return snapshots





def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, default=Path('/tmp/five-voice.json'))
    parser.add_argument('--relay', action='store_true')
    parser.add_argument('--turnserver', default='turnserver')
    parser.add_argument('--headed', action='store_true')
    args = parser.parse_args()
    runtime = args.runtime_root.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(runtime / 'scripts/peer'))
    from fixture import LocalTurn
    started = time.monotonic()
    errors, pages = [], []
    with contextlib.ExitStack() as stack:
        turn = stack.enter_context(LocalTurn(args.turnserver)) if args.relay else None
        env = {**os.environ, **(turn.environment() if turn else {'TURN_URLS': '', 'TURN_SECRET': ''})}
        if turn:
            env['TURN_PAIR_LIMIT'] = '10'
        server = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=runtime,
                                  env=env, stdout=subprocess.PIPE, text=True)
        stack.callback(lambda: server.wait(timeout=10))
        stack.callback(server.terminate)
        url = json.loads(server.stdout.readline())['url']
        tone = write_tone(Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='five-voice-'))) / 'tone.wav')
        playwright = stack.enter_context(sync_playwright())
        contexts = []
        versions = []
        for _ in range(3):
            browser = playwright.chromium.launch(channel='chromium', headless=not args.headed,
                ignore_default_args=['--mute-audio', '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding'],
                args=['--use-fake-device-for-media-stream', f'--use-file-for-fake-audio-capture={tone}'])
            stack.callback(browser.close)
            versions.append(browser.version)
            context = browser.new_context(permissions=['microphone'], viewport={'width': 1440, 'height': 1100})
            context.add_init_script((runtime / 'scripts/voice/fixtures.js').read_text() + """
window.voiceRoom=null;
const RoomSocket=WebSocket;
window.WebSocket=class extends RoomSocket {constructor(...args){super(...args);
 this.addEventListener('message',event=>{const value=JSON.parse(event.data);if(value.type==='room')voiceRoom=value.room;});}};
""")
            if args.relay:
                context.add_init_script("sessionStorage.setItem('retro-coop-connection-policy','relay')")
            contexts.append(context)
        for index in range(5):
            page = contexts[0 if index < 2 else 1 if index < 4 else 2].new_page()
            page.set_default_timeout(30000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.context.new_cdp_session(page).send('Emulation.setFocusEmulationEnabled', {'enabled': False})
            pages.append(page)
        try:
            host = pages[0]
            host.goto(url)
            host.get_by_role('button', name='Create game', exact=True).click()
            static = Path(env.get('RETRO_COOP_STATIC_ROOT', runtime / 'apps/client/dist'))
            host.set_input_files('input[type=file]', str(static / 'generated/diagnostic.nes'))
            host.get_by_role('button', name='Create room', exact=True).click()
            invitation = host.get_by_label('Room invitation', exact=True).input_value()
            # A real observer download failure must not prevent its independent voice mesh.
            pages[4].route('**/coordinator/rooms/*/rom', lambda route: route.fulfill(status=503, body='proof download unavailable'))
            for page in pages[1:]:
                page.goto(invitation)
                page.get_by_role('button', name='Join room', exact=True).click()
            for page in pages:
                page.wait_for_function("voiceRoom?.occupancy===5&&voiceRoom.peers.length===4&&voiceRoom.peers.every(p=>p.status==='connected')")
                page.wait_for_function("pcs.filter(p=>p.connectionState==='connected').length===4")
                page.bring_to_front()
                page.locator('details.voice-disclosure > summary').click()
                page.get_by_label('Remote voice volume', exact=False).fill('10')
                page.get_by_role('button', name='Enable voice', exact=True).click()
                page.wait_for_function('captures.length===1&&captures[0].getAudioTracks()[0].enabled')
                page.get_by_role('button', name='Mute microphone', exact=True).click()
            initial_bounds = bounds(pages, 4)
            print('Five members connected; microphones captured once.', flush=True)
            routes = [page.evaluate('''async () => Promise.all(pcs.filter(pc=>pc.connectionState==='connected').map(async pc=>{
 const stats=await pc.getStats();
 const transport=[...stats.values()].find(s=>s.type==='transport'&&s.selectedCandidatePairId);
 const pair=transport&&stats.get(transport.selectedCandidatePairId);
 return pair ? {local:stats.get(pair.localCandidateId)?.candidateType,remote:stats.get(pair.remoteCandidateId)?.candidateType} : null;
}))''') for page in pages]
            assert all(len(route)==4 and all(pair is not None for pair in route) for route in routes), routes
            if args.relay:
                assert all(pair['local']=='relay' and pair['remote']=='relay' for route in routes for pair in route), routes
            rooms = [page.evaluate('voiceRoom') for page in pages]
            members = [room['chatMembership'] for room in rooms]
            assert len(set(members)) == 5
            assert all(room['game']['status'] != 'playing' for room in rooms)
            failed_slot = next(slot for slot in rooms[4]['slots'] if (slot.get('member') or {}).get('id') == members[4])
            assert failed_slot['role'] == 'observer', failed_slot
            failed_member = failed_slot['member']
            assert failed_member['acquisition'] == 'failed', failed_member
            rotations = []
            for index, sender in enumerate(pages):
                receivers = [page for page in pages if page != sender]
                sender.bring_to_front()
                sender.get_by_role('button', name='Unmute microphone', exact=True).click()
                # Real background tabs in the same context; separate-process sender uses a blank tab.
                focus = pages[1] if index == 0 else pages[0] if index == 1 else pages[3] if index == 2 else pages[2] if index == 3 else contexts[2].new_page()
                focus.bring_to_front()
                sender.wait_for_function('!document.hasFocus()')
                assert sender.evaluate('captures[0].getAudioTracks()[0].enabled')
                delta = energy_arrives(receivers)
                sender.bring_to_front()
                sender.get_by_role('button', name='Mute microphone', exact=True).click()
                focus.bring_to_front()
                sender.wait_for_function('!document.hasFocus()')
                assert not sender.evaluate('captures[0].getAudioTracks()[0].enabled')
                energy_stops(receivers)
                bounds(pages, 4)
                print(f'Sender {index}: four receivers decoded audio; background mute silent.', flush=True)
                rotations.append({'sender': index, 'receiver_energy_deltas': delta, 'background_mute_silence': True})
                if index == 4:
                    focus.close()
            # Departure of one observer leaves three senders attached to the same microphone.
            host.bring_to_front()
            host.get_by_role('button', name='Unmute microphone', exact=True).click()
            pages[1].bring_to_front()
            energy_arrives(pages[1:])
            pages[4].get_by_role('button', name='Leave room', exact=True).click()
            if rooms[4]['established']:
                pages[4].get_by_role('button', name='Confirm leave', exact=True).click()
            pages[4].wait_for_function("captures.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
            for page in pages[:4]:
                page.wait_for_function("voiceRoom.occupancy===4&&pcs.filter(p=>p.connectionState==='connected').length===3")
            departure_energy = energy_arrives(pages[1:4])
            departure_bounds = bounds(pages[:4], 3)
            assert departure_bounds[0]['enabled'] and all(not value['enabled'] for value in departure_bounds[1:])
            host.screenshot(path=str(args.output.with_suffix('.png')))
            allocations = turn.allocation_counts() if turn else None
            if turn:
                assert 20 <= allocations['peak_live_allocations'] <= 32, allocations
                assert not turn.error_codes().get('486'), turn.error_codes()
            assert not errors, errors
            result = {'result': 'pass', 'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=runtime, text=True).strip(),
                'proof_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'static_sha256': {str(path.relative_to(static)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(static.rglob('*')) if path.is_file() and path.suffix in ['.html', '.js', '.wasm']},
                'relay': args.relay, 'members': 5, 'pairs': 10, 'browser_processes': 3, 'same_origin_tabs': True,
                'browser_versions': versions, 'selected_routes': routes, 'initial_bounds': initial_bounds, 'rotations': rotations,
                'observer_download_error_voice': True, 'departure_energy_deltas': departure_energy,
                'departure_bounds': departure_bounds, 'page_errors': errors,
                'turn_allocations': allocations, 'turn_error_codes': turn.error_codes() if turn else {}, 'seconds': round(time.monotonic() - started, 2)}
            args.output.write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result))
        except Exception:
            args.output.with_suffix('.failure.json').write_text(json.dumps({'page_errors': errors, 'turn_error_codes': turn.error_codes() if turn else {}}, indent=2))
            for index, page in enumerate(pages):
                with contextlib.suppress(Exception):
                    args.output.with_suffix(f'.member{index}.json').write_text(json.dumps(page.evaluate('({room:voiceRoom,bounds:(' + BOUNDS + ')(),errors:peerErrors})'), indent=2))
                    page.screenshot(path=str(args.output.with_suffix(f'.member{index}.png')))
            raise


if __name__ == '__main__':
    main()
