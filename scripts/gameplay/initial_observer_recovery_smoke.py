"""Recover an observing host's first start and a lost Ready command."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from playwright.sync_api import sync_playwright
from late_controller_smoke import NATIVE

ROOT = Path(__file__).resolve().parents[2]
PROBE = """
window.recovery={commands:[],results:[],events:[],droppedReady:0};
const Socket=WebSocket;
window.WebSocket=class extends Socket {
 constructor(...args){super(...args);this.addEventListener('message',({data})=>{
  const event=JSON.parse(data);
  if(event.type==='result')recovery.results.push(event);
  if(['gamePrepare','gameStart','gameStop'].includes(event.type))recovery.events.push(event);
 });}
 send(raw){const command=JSON.parse(raw);recovery.commands.push(command);
  if(command.type==='gameReady'&&window.dropInitialReady){recovery.droppedReady++;return;}
  return super.send(raw);
 }
};
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, default=ROOT)
    parser.add_argument('--case', choices=['all', 'barrier', 'pre-epoch'], default='all')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime_root.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    pages, errors, results = [], [], []
    source = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=runtime, text=True).strip(),
              'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'index_sha256': hashlib.sha256((runtime / 'apps/client/dist/index.html').read_bytes()).hexdigest()}
    with contextlib.ExitStack() as stack:
        server = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=runtime,
                                  env={**os.environ, 'TURN_URLS': '', 'TURN_SECRET': ''}, stdout=subprocess.PIPE, text=True)
        stack.callback(lambda: server.wait(timeout=10))
        stack.callback(server.terminate)
        url = json.loads(server.stdout.readline())['url']
        playwright = stack.enter_context(sync_playwright())
        browser = playwright.chromium.launch()
        stack.callback(browser.close)
        fixture = (ROOT / 'scripts/gameplay/fixture.js').read_text() + '\n' + PROBE

        def page():
            context = browser.new_context(viewport={'width': 1280, 'height': 900})
            context.add_init_script(fixture)
            tab = context.new_page()
            tab.set_default_timeout(15_000)
            tab.on('pageerror', lambda error: errors.append(str(error)))
            pages.append(tab)
            return tab

        def wait(tab, expression, arg=None, timeout=15_000):
            tab.wait_for_function(expression, arg=arg, timeout=timeout, polling=30)

        def setup():
            host, member = page(), page()
            host.goto(url)
            host.get_by_role('button', name='Create game', exact=True).click()
            host.set_input_files('input[type=file]', str(runtime / 'apps/client/dist/generated/diagnostic.nes'))
            host.get_by_role('button', name='Create room', exact=True).click()
            host.get_by_role('button', name='Start game', exact=True).wait_for()
            host.locator('[data-slot-id=slot-1] [data-slot-action]').select_option('role:observer')
            wait(host, "proof.room?.slots[0].role==='observer'")
            member.goto(host.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite"))
            member.get_by_role('button', name='Join room', exact=True).click()
            member.get_by_role('button', name='Ready', exact=True).click()
            host.get_by_role('button', name='Ready', exact=True).click()
            wait(host, 'proof.room.game.ready.includes(proof.room.slots[1].member?.id)')
            return host, member, host.evaluate('proof.room.id')

        def recover(host, member, room_id, case):
            if case == 'pre-epoch':
                host.get_by_role('button', name='Start game', exact=True).click()
            else:
                member.get_by_role('button', name='Retry shared play', exact=True).click()
                wait(host, 'proof.room.game.ready.includes(proof.room.slots[1].member?.id)')
                host.get_by_role('button', name='Retry shared play', exact=True).click()
            for tab in (host, member):
                wait(tab, "proof.room.game.status==='playing'&&proof.room.established")
                assert tab.evaluate('proof.room.id') == room_id
                tab.evaluate('releaseFrames()')
            assert host.evaluate('proof.room.slots[0].role') == 'observer'
            for tab in (host, member):
                wait(tab, 'proof.frameCount>=120')
            host.get_by_role('button', name='Pause', exact=True).click()
            for tab in (host, member):
                wait(tab, "proof.room.game.status==='paused'")
            deadline = time.monotonic() + 5
            while True:
                states = [tab.evaluate(NATIVE) for tab in (host, member)]
                fence = host.evaluate('proof.room.game.frame')
                if states[0] == states[1] and states[0]['frame'] == fence:
                    break
                assert time.monotonic() < deadline, states
                host.wait_for_timeout(30)
            host.get_by_role('button', name='Players', exact=True).click()
            host.get_by_label('Slot 1 identity', exact=True).scroll_into_view_if_needed()
            host.screenshot(path=str(args.output.with_suffix('.' + case + '-recovered.png')))
            assert states[0]['frame'] >= 120
            host.get_by_role('button', name='Leave room', exact=True).click()
            host.get_by_role('button', name='Confirm leave', exact=True).click()
            for tab in (host, member):
                tab.get_by_test_id('room-view').wait_for(state='detached')
            return states

        try:
            for case in ['barrier', 'pre-epoch'] if args.case == 'all' else [args.case]:
                host, member, room_id = setup()
                failed_at = time.monotonic()
                if case == 'barrier':
                    host.evaluate('window.dropGameAck=true')
                    host.get_by_role('button', name='Start game', exact=True).click()
                    wait(host, 'proof.room.game.startRequested')
                    wait(host, "proof.room.game.status==='starting'&&proof.droppedAcks>0")
                    wait(host, "['failed','paused'].includes(proof.room.game.status)&&!proof.room.established", timeout=20_000)
                else:
                    host.get_by_role('button', name='Not ready', exact=True).click()
                    wait(host, '!proof.room.game.ready.includes(proof.room.chatMembership)')
                    host.evaluate('window.dropInitialReady=true')
                    host.get_by_role('button', name='Ready', exact=True).click()
                    wait(host, 'recovery.droppedReady>0&&!proof.room.game.epoch')
                    assert host.get_by_role('button', name='Start game', exact=True).is_disabled()
                elapsed_timeout = time.monotonic() - failed_at
                host.screenshot(path=str(args.output.with_suffix('.' + case + '-failed.png')))
                if case == 'pre-epoch':
                    assert not host.evaluate('proof.room.game.epoch')
                host.evaluate('window.dropGameAck=false;window.dropInitialReady=false')
                if case == 'pre-epoch':
                    host.get_by_role('button', name='Cancel preparation', exact=True).click()
                    wait(host, '!proof.room.game.ready.includes(proof.room.chatMembership)')
                    host.get_by_role('button', name='Ready', exact=True).click()
                    wait(host, 'proof.room.game.ready.includes(proof.room.chatMembership)')
                states = recover(host, member, room_id, case)
                results.append({'case': case, 'failure_observed_seconds': round(elapsed_timeout, 2),
                                'same_room_recovered': True, 'host_role': 'observer',
                                'native_states': states, 'host_events': host.evaluate('recovery.events')})
            assert not errors, errors
            result = {'result': 'pass', 'source': source, 'cases': results, 'browser': browser.version,
                      'seconds': round(time.monotonic() - started, 2), 'page_errors': errors}
            args.output.write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result))
        except Exception:
            failure = {'result': 'fail', 'source': source, 'cases_completed': results, 'errors': errors,
                       'pages': [tab.evaluate('({room:proof.room,recovery,text:document.body.innerText})') for tab in pages]}
            args.output.write_text(json.dumps(failure, indent=2) + '\n')
            for index, tab in enumerate(pages):
                tab.screenshot(path=str(args.output.with_suffix(f'.failure-{index}.png')))
            raise


if __name__ == '__main__':
    main()
