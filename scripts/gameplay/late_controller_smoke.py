"""Late Player 2 explicitly prepares and joins the running host's preserved timeline."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
PROBE = """
window.lateProof={events:[],frozen:[],imports:[],commands:[]};
const Socket=WebSocket;
window.WebSocket=class extends Socket{
 constructor(...args){super(...args);this.addEventListener('message',({data})=>{const event=JSON.parse(data);
  if(['gamePrepare','gameStart','gameCheckpoint','gameStop'].includes(event.type))lateProof.events.push(event);});}
 send(raw){const command=JSON.parse(raw);
  if(command.type==='gameFrozen')lateProof.frozen.push(command);
  if(['slotRole','gameReady','gameObserve'].includes(command.type))lateProof.commands.push(command.type);
  return super.send(raw);}
};
const Core=Worker;
window.Worker=class extends Core{constructor(...args){super(...args);this.addEventListener('message',({data})=>{
 if(data.type==='peer-checkpoint-imported')lateProof.imports.push({epoch:data.epoch,frame:data.frame,hash:data.hash});});}};
"""
NATIVE = """()=>new Promise((resolve,reject)=>{const requestId=window.nativeRequest=(window.nativeRequest??850000)+1;
 const timer=setTimeout(()=>{currentWorker.removeEventListener('message',done);reject(Error('Native hash timeout'));},3000);
 function done({data}){if(data.requestId!==requestId)return;clearTimeout(timer);currentWorker.removeEventListener('message',done);
 if(data.type==='error')reject(Error(data.message));else resolve(data.info);}
 currentWorker.addEventListener('message',done);currentWorker.postMessage({type:'state-hash',requestId});})"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, default=Path('/tmp/late-controller.json'))
    args = parser.parse_args()
    runtime = args.runtime_root.resolve()
    static = Path(os.environ.get('RETRO_COOP_STATIC_ROOT', runtime / 'apps/client/dist'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    pages, errors = [], []
    with contextlib.ExitStack() as stack:
        server = subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=runtime,
            env={**os.environ,'TURN_URLS':'','TURN_SECRET':''},stdout=subprocess.PIPE,text=True)
        stack.callback(lambda: server.wait(timeout=10));stack.callback(server.terminate)
        url = json.loads(server.stdout.readline())['url']
        playwright = stack.enter_context(sync_playwright())
        for _ in range(3):
            browser = playwright.chromium.launch(ignore_default_args=['--mute-audio'])
            stack.callback(browser.close)
            page = browser.new_page(viewport={'width':1440,'height':1100})
            page.set_default_timeout(20000)
            page.add_init_script(path=runtime/'scripts/gameplay/fixture.js')
            page.add_init_script(PROBE)
            page.on('pageerror',lambda error:errors.append(str(error)))
            pages.append(page)
        host, player2, observer = pages
        try:
            host.goto(url)
            host.get_by_role('button',name='Create game',exact=True).click()
            host.set_input_files('input[type=file]',str(static/'generated/diagnostic.nes'))
            host.get_by_role('button',name='Create room',exact=True).click()
            host.get_by_test_id('room-view').wait_for(state='attached')
            invite = host.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite")
            host.locator('[data-slot-id=slot-2] [data-manage-slot]').click()
            assert host.get_by_label('Slot 2 role',exact=True).input_value() == 'player2'
            host.get_by_role('button',name='Done',exact=True).click()
            host.get_by_role('button',name='Ready',exact=True).click()
            host.get_by_role('button',name='Start game',exact=True).click()
            host.evaluate('releaseFrames()')
            host.wait_for_function('proof.frames.at(-1)?.frame>=240',polling=20)
            initial_epoch = host.evaluate('proof.room.game.epoch')
            original_owner = host.evaluate('proof.room.hostMembership')
            assert host.evaluate('proof.room.game.controllers.owners') == [original_owner,None]
            for page in (player2,observer):
                page.goto(invite)
                page.get_by_role('button',name='Join room',exact=True).click()
                page.wait_for_function("proof.room?.matches&&proof.room.slots.find(s=>s.member?.id===proof.room.chatMembership)?.member.acquisition==='loaded'",polling=20)
                page.evaluate('releaseFrames()')
            for page in pages:
                page.wait_for_function("proof.room.occupancy===3&&proof.room.peers.length===2&&proof.room.peers.every(p=>p.status==='connected')",polling=20)
            observer.wait_for_function('proof.frames.at(-1)?.frame>=10', polling=20)
            joining_member = player2.evaluate('proof.room.chatMembership')
            observer_member = observer.evaluate('proof.room.chatMembership')
            slots_before = host.evaluate('proof.room.slots.map(s=>({id:s.id,role:s.role,member:s.member?.id??null}))')
            assert slots_before[1]['member'] == joining_member and slots_before[1]['role'] == 'player2'
            assert slots_before[2]['member'] == observer_member and slots_before[2]['role'] == 'observer'
            unprepared = player2.evaluate(NATIVE)
            assert unprepared['frame'] == 0 and unprepared['fresh'], unprepared
            assert player2.evaluate('lateProof.commands') == []
            before_prepare = host.evaluate('proof.frames.at(-1).frame')
            host.wait_for_function('frame=>proof.frames.at(-1).frame>=frame+120',arg=before_prepare,polling=20)
            assert host.evaluate('proof.room.game.epoch') == initial_epoch
            assert host.evaluate('proof.room.game.controllers.owners') == [original_owner,None]
            # This is the sole activation consent: no role change or coordinator command injection.
            player2.get_by_role('button',name='Prepare to play',exact=True).click()
            for page in pages:
                page.wait_for_function("member=>proof.room.game.status==='playing'&&proof.room.game.controllers.owners[1]===member",arg=joining_member,polling=20)
            observer.wait_for_function('proof.frames.at(-1)?.frame>=10', polling=20)
            frozen = host.evaluate('lateProof.frozen.at(-1)')
            resumed = host.evaluate("lateProof.events.filter(e=>e.type==='gameStart').at(-1)")
            imports = player2.evaluate('lateProof.imports')
            assert frozen and frozen['frame'] > before_prepare
            assert resumed['frame'] == frozen['frame'] and resumed['hash'] == frozen['hash']
            assert resumed['epoch'] != initial_epoch
            assert any(value['frame']==frozen['frame'] and value['hash']==frozen['hash'] for value in imports), imports
            assert host.evaluate('proof.room.slots.map(s=>({id:s.id,role:s.role,member:s.member?.id??null}))') == slots_before
            assert all('slotRole' not in page.evaluate('lateProof.commands') for page in pages)
            assert player2.evaluate("lateProof.commands.filter(c=>c==='gameReady').length") == 1
            assert observer.evaluate("lateProof.commands.filter(c=>c==='gameReady').length") == 0
            host.locator('canvas').focus();host.keyboard.down('x')
            player2.locator('canvas').focus();player2.keyboard.down('z')
            observer.locator('canvas').focus();observer.keyboard.down('x');observer.keyboard.down('z')
            host.wait_for_function('frame=>proof.frames.at(-1).frame>=frame+120',arg=resumed['frame'],polling=20)
            for page in pages:
                page.evaluate("proof.controllerRam=undefined;currentWorker.postMessage({type:'state-export',requestId:900000})")
                page.wait_for_function('proof.controllerRam',polling=20)
                assert page.evaluate('proof.controllerRam') == [128,64]
            host.keyboard.up('x');player2.keyboard.up('z');observer.keyboard.up('x');observer.keyboard.up('z')
            host.get_by_role('button',name='Pause',exact=True).click()
            for page in pages:
                page.wait_for_function("proof.room.game.status==='paused'",polling=20)
            deadline = time.monotonic()+5
            while True:
                states = [page.evaluate(NATIVE) for page in pages]
                if all(value==states[0] for value in states):break
                assert time.monotonic()<deadline,states
                time.sleep(.05)
            assert states[0]['frame'] > frozen['frame']+120
            assert not errors,errors
            host.screenshot(path=str(args.output.with_suffix('.png')))
            result = {'result':'pass','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=runtime,text=True).strip(),
                'build_files':{str(path.relative_to(static)):hashlib.sha256(path.read_bytes()).hexdigest() for path in static.rglob('*') if path.suffix in ('.js','.wasm')},
                'unprepared_native_state':unprepared,'frame_before_prepare':before_prepare,
                'preserved_boundary':{'frame':frozen['frame'],'hash':frozen['hash']},
                'new_epoch_start':{'frame':resumed['frame'],'hash':resumed['hash']},'checkpoint_imports':imports,
                'explicit_prepare_only':True,'slot_roles_unchanged':True,'all_native_controller_ram':[128,64],
                'final_native_states':states,'page_errors':errors,'seconds':round(time.monotonic()-started,2)}
            args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
        except Exception:
            for index,page in enumerate(pages):
                with contextlib.suppress(Exception):
                    args.output.with_suffix(f'.member{index}.json').write_text(json.dumps(page.evaluate('({room:proof.room,evidence:lateProof,status:document.querySelector("[data-testid=game-status]")?.textContent})'),indent=2))
                    page.screenshot(path=str(args.output.with_suffix(f'.member{index}.png')))
            raise


if __name__ == '__main__':
    main()
