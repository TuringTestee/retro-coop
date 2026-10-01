"""Real lobby recovery when Ready fails at the controller or room service."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import subprocess
import time

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
PROBE = r"""
window.readyProbe={room:null,attempts:0,padConnected:true,rejectOnce:false,dropOnce:false};
const pad={id:'Test controller',index:0,connected:true,mapping:'standard',timestamp:0,
 buttons:Array.from({length:17},()=>({pressed:false,touched:false,value:0})),axes:[0,0,0,0]};
Object.defineProperty(navigator,'getGamepads',{configurable:true,value:()=>readyProbe.padConnected?[pad]:[null]});
const Socket=WebSocket;
window.WebSocket=class extends Socket {
 constructor(...args){super(...args);this.addEventListener('message',({data})=>{
  const event=JSON.parse(data);if(event.type==='room')readyProbe.room=event.room;
  if(event.type==='result'&&event.ok&&event.data?.room)readyProbe.room=event.data.room;
 });}
 send(raw){const command=JSON.parse(raw);
  if(command.type==='gameReady'){
   readyProbe.attempts++;
   if(readyProbe.rejectOnce){readyProbe.rejectOnce=false;return super.send(JSON.stringify({...command,roomRevision:command.roomRevision-1}));}
   if(readyProbe.dropOnce){readyProbe.dropOnce=false;return;}
  }
  return super.send(raw);
 }
};
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with contextlib.ExitStack() as stack:
        server = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                                  env={**os.environ, 'TURN_URLS': '', 'TURN_SECRET': ''}, stdout=subprocess.PIPE, text=True)
        stack.callback(lambda: server.wait(timeout=10))
        stack.callback(server.terminate)
        url = json.loads(server.stdout.readline())['url']
        playwright = stack.enter_context(sync_playwright())
        browser = playwright.chromium.launch()
        stack.callback(browser.close)
        host = browser.new_page(viewport={'width': 1280, 'height': 800})
        guest = browser.new_page(viewport={'width': 390, 'height': 800})
        errors = []
        for page in (host, guest):
            page.add_init_script(PROBE)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.set_default_timeout(15_000)

        host.goto(url)
        host.get_by_role('button', name='Create game', exact=True).click()
        host.set_input_files('input[type=file]', str(ROOT / 'apps/client/dist/generated/diagnostic.nes'))
        host.get_by_role('button', name='Create room', exact=True).click()
        host.get_by_role('button', name='Start game', exact=True).wait_for()
        invite = host.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite")
        guest.goto(invite)
        guest.get_by_role('button', name='Join room', exact=True).click()
        guest.wait_for_function("readyProbe.room?.matches&&readyProbe.room.slots.find(slot=>slot.member?.id===readyProbe.room.chatMembership)?.member.acquisition==='loaded'", polling=30)
        guest.wait_for_function("readyProbe.room?.peers.some(peer=>peer.status==='connected')", polling=30)

        guest.get_by_role('button', name='Settings', exact=True).click()
        guest.get_by_label('Input device', exact=True).select_option('0')
        guest.get_by_role('button', name='Back', exact=True).click()
        action = guest.locator('[data-layout-region=readiness-actions]')
        base = action.bounding_box()
        assert base and base['height'] > 0, base

        def error_visible():
            slot, alert = action.bounding_box(), action.get_by_role('alert').bounding_box()
            assert slot and alert, (slot, alert)
            assert slot['x'] <= alert['x'] and slot['y'] <= alert['y'], (slot, alert)
            assert alert['x'] + alert['width'] <= slot['x'] + slot['width'] + 1, (slot, alert)
            assert alert['y'] + alert['height'] <= slot['y'] + slot['height'] + 1, (slot, alert)

        guest.evaluate('readyProbe.padConnected=false')
        action.get_by_role('button', name='Ready', exact=True).click()
        action.get_by_role('alert').get_by_text('Reconnect your controller before shared play.', exact=True).wait_for()
        error_visible()
        assert action.get_by_role('button', name='Try again', exact=True).is_visible()
        assert host.get_by_role('button', name='Start game', exact=True).is_disabled()
        guest.screenshot(path=str(args.output.with_suffix('.controller-failure-mobile.png')))
        assert action.bounding_box() == base, 'Readiness slot moved after controller failure'
        guest.evaluate('readyProbe.padConnected=true')
        action.get_by_role('button', name='Try again', exact=True).click()
        guest.wait_for_function('readyProbe.room?.game.ready.includes(readyProbe.room.chatMembership)', polling=30)
        assert action.get_by_role('button', name='Not ready', exact=True).is_visible()
        assert action.bounding_box() == base, 'Readiness slot moved after controller recovery'

        action.get_by_role('button', name='Not ready', exact=True).click()
        guest.wait_for_function('!readyProbe.room?.game.ready.includes(readyProbe.room.chatMembership)', polling=30)
        guest.evaluate('readyProbe.rejectOnce=true')
        action.get_by_role('button', name='Ready', exact=True).click()
        action.get_by_role('alert').get_by_text('Room changed. Try again.', exact=True).wait_for()
        error_visible()
        assert not guest.evaluate('readyProbe.room.game.ready.includes(readyProbe.room.chatMembership)')
        guest.set_viewport_size({'width': 1280, 'height': 800})
        guest.screenshot(path=str(args.output.with_suffix('.rejected-failure-desktop.png')))
        action.get_by_role('button', name='Try again', exact=True).click()
        guest.wait_for_function('readyProbe.room?.game.ready.includes(readyProbe.room.chatMembership)', polling=30)

        action.get_by_role('button', name='Not ready', exact=True).click()
        guest.wait_for_function('!readyProbe.room?.game.ready.includes(readyProbe.room.chatMembership)', polling=30)
        guest.evaluate('readyProbe.dropOnce=true')
        action.get_by_role('button', name='Ready', exact=True).click()
        action.get_by_role('alert').get_by_text('Room service did not respond. Try again.', exact=True).wait_for(timeout=12_000)
        error_visible()
        assert not guest.evaluate('readyProbe.room.game.ready.includes(readyProbe.room.chatMembership)')
        guest.set_viewport_size({'width': 390, 'height': 800})
        guest.screenshot(path=str(args.output.with_suffix('.timeout-failure-mobile.png')))
        action.get_by_role('button', name='Try again', exact=True).click()
        guest.wait_for_function('readyProbe.room?.game.ready.includes(readyProbe.room.chatMembership)', polling=30)
        assert action.bounding_box() == base, 'Readiness slot moved after timed-out preparation recovery'
        guest.screenshot(path=str(args.output.with_suffix('.ready-mobile.png')))
        host.get_by_role('button', name='Ready', exact=True).click()
        host.wait_for_function('readyProbe.room?.game.ready.length===2', polling=30)
        host.get_by_role('button', name='Start game', exact=True).click()
        for page in (host, guest):
            page.wait_for_function("readyProbe.room?.game.status==='playing'&&readyProbe.room.established", polling=30)
        assert not errors, errors
        result = {'result': 'pass', 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  'browser': browser.version, 'cases': ['controller disconnected', 'coordinator rejection', 'room-service timeout'],
                  'guest_ready_attempts': guest.evaluate('readyProbe.attempts'), 'authoritative_ready_before_start': True,
                  'shared_play': True, 'seconds': round(time.monotonic() - start, 2), 'page_errors': errors}
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))


if __name__ == '__main__':
    main()
