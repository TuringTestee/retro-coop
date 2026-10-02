"""Five real members: faulty observer transfers expire without stopping shared play."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
PROBE = r"""
window.observerFault=sessionStorage.getItem('observer-proof-fault')??'none';
window.observerProbe={transfers:[],chunks:0,bytes:0,maxChunk:0,dropped:0,corrupted:0,
 maxCheckpointBuffered:0,maxGameBuffered:0,imports:0,events:[],pcs:[]};
const onmessage=Object.getOwnPropertyDescriptor(RTCDataChannel.prototype,'onmessage');
Object.defineProperty(RTCDataChannel.prototype,'onmessage',{...onmessage,set(callback){
 const channel=this;
 onmessage.set.call(this,callback&&function(event){
  let data=event.data;
  if(channel.label==='retro-coop-checkpoint'){
   if(typeof data==='string'){
    const value=JSON.parse(data);observerProbe.transfers.push({at:performance.now(),frame:value.frame,bytes:value.byteLength});
   }else if(data instanceof ArrayBuffer){
    observerProbe.chunks++;observerProbe.bytes+=data.byteLength;observerProbe.maxChunk=Math.max(observerProbe.maxChunk,data.byteLength);
    if(observerFault==='hold'){observerProbe.dropped++;return;}
    if(observerFault==='corrupt'){data=data.slice(0);new Uint8Array(data)[data.byteLength-1]^=1;observerProbe.corrupted++;event=new MessageEvent('message',{data});}
   }
  }
  return callback.call(this,event);
 });
}});
const send=RTCDataChannel.prototype.send;
RTCDataChannel.prototype.send=function(data){const result=send.call(this,data);
 const key=this.label==='retro-coop-checkpoint'?'maxCheckpointBuffered':'maxGameBuffered';
 observerProbe[key]=Math.max(observerProbe[key],this.bufferedAmount);return result;};
const Peer=RTCPeerConnection;
window.RTCPeerConnection=class extends Peer{constructor(...args){super(...args);observerProbe.pcs.push(this);}};
const Socket=WebSocket;
window.WebSocket=class extends Socket{constructor(...args){super(...args);this.addEventListener('message',({data})=>{
 const value=JSON.parse(data);if(['gameCheckpoint','gameSyncStop','gameStop','gamePauseAt','gameStart'].includes(value.type)){
  observerProbe.events.push({at:performance.now(),type:value.type,reason:value.reason,frame:value.frame});
  if(observerProbe.events.length>40)observerProbe.events.shift();
 }
});}};
const Core=Worker;
window.Worker=class extends Core{constructor(...args){super(...args);this.addEventListener('message',({data})=>{if(data.type==='peer-checkpoint-imported')observerProbe.imports++;});}};
"""
NATIVE = """()=>new Promise((resolve,reject)=>{const requestId=window.proofRequest=(window.proofRequest??850000)+1;
 const timer=setTimeout(()=>{currentWorker.removeEventListener('message',done);reject(Error('Native proof timeout'));},3000);
 function done({data}){if(data.requestId!==requestId)return;clearTimeout(timer);currentWorker.removeEventListener('message',done);
 if(data.type==='error')reject(Error(data.message));else resolve(data.info);}
 currentWorker.addEventListener('message',done);currentWorker.postMessage({type:'state-hash',requestId});})"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, default=Path('/tmp/observer-failure.json'))
    args = parser.parse_args()
    runtime = args.runtime_root.resolve()
    static = Path(os.environ.get('RETRO_COOP_STATIC_ROOT', runtime / 'apps/client/dist'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    errors, pages, scenarios = [], [], []
    with contextlib.ExitStack() as stack:
        server = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=runtime,
            env={**os.environ, 'TURN_URLS': '', 'TURN_SECRET': ''}, stdout=subprocess.PIPE, text=True)
        stack.callback(lambda: server.wait(timeout=10))
        stack.callback(server.terminate)
        url = json.loads(server.stdout.readline())['url']
        playwright = stack.enter_context(sync_playwright())
        contexts = []
        for index in range(3):
            browser = playwright.chromium.launch(ignore_default_args=['--mute-audio'])
            stack.callback(browser.close)
            contexts.append(browser.new_context(viewport={'width':1440, 'height':1100},
                permissions=['clipboard-read', 'clipboard-write'] if index == 0 else []))
        for index in range(5):
            page = contexts[0 if index < 2 else 1 if index < 4 else 2].new_page()
            page.set_default_timeout(20000)
            page.add_init_script(path=runtime / 'scripts/gameplay/fixture.js')
            page.add_init_script(PROBE)
            page.on('pageerror', lambda error: errors.append(str(error)))
            pages.append(page)
        host, owner, *observers = pages
        target = observers[-1]

        def membership(page):
            return page.evaluate("proof.room.slots.filter(s=>s.member).map(s=>({slot:s.id,id:s.member.id,role:s.role}))")

        def playing():
            for page in pages:
                page.wait_for_function("proof.room?.occupancy===5&&proof.room.peers.length===4&&proof.room.peers.every(p=>p.status==='connected')", polling=50)
            for page in observers:
                page.wait_for_function('proof.frames.at(-1)?.frame>=10', polling=20)

        def matching_boundary(selected):
            host.get_by_role('button', name='Pause', exact=True).click()
            for page in pages:
                page.wait_for_function("proof.room.game.status==='paused'", polling=20)
            deadline = time.monotonic() + 5
            while True:
                values = [page.evaluate(NATIVE) for page in selected]
                if all(value == values[0] for value in values):
                    return values
                assert time.monotonic() < deadline, values
                time.sleep(.05)

        def resume():
            for page in (host, owner):
                page.get_by_role('button', name='Prepare to resume', exact=True).click()
            host.wait_for_function("proof.room.game.status==='resume_ready'", polling=20)
            host.get_by_role('button', name='Resume together', exact=True).click()
            playing()

        try:
            host.goto(url)
            host.get_by_role('button', name='Browse lobbies →').click()
            host.get_by_role('button', name='Create lobby →').click()
            host.get_by_label('Lobby name').fill('Observer Recovery')
            host.get_by_role('button', name='Create lobby →').click()
            host.get_by_role('button', name='Load NES game').wait_for()
            host.locator('input[aria-label="NES cartridge file"]').set_input_files(
                str(static / 'generated/diagnostic.nes'))
            host.get_by_role('button', name='Change game').wait_for(timeout=30000)
            host.get_by_role('button', name='Copy invite').click()
            invite = host.evaluate('navigator.clipboard.readText()')
            assert urlsplit(invite).path == '/', 'Displayed invitation must use the canonical room route, never /create'
            for page in pages[1:]:
                page.goto(invite)
                page.get_by_role('button', name='Join lobby', exact=True).click()
                page.wait_for_function("proof.room?.matches&&proof.room.slots.find(s=>s.member?.id===proof.room.chatMembership)?.member.acquisition==='loaded'", polling=50)
            for page in pages:
                page.wait_for_function("proof.room.peers.length===4&&proof.room.peers.every(p=>p.status==='connected')", polling=50)
            members = membership(host)
            assert len(members) == 5
            for page in pages:
                page.get_by_role('button', name='Ready', exact=True).click()
                page.wait_for_function('proof.room.game.ready.includes(proof.room.chatMembership)', polling=20)
            host.get_by_role('button', name='Start →', exact=True).click()
            for page in pages:
                page.evaluate('releaseFrames()')
            playing()
            host.wait_for_function('proof.frames.at(-1)?.frame>=240', polling=20)
            for fault in ('corrupt', 'hold'):
                epoch = host.evaluate('proof.room.game.epoch')
                before = host.evaluate('proof.frames.at(-1).frame')
                target.evaluate('fault=>sessionStorage.setItem("observer-proof-fault",fault)', fault)
                target.reload()
                target.evaluate('releaseFrames()')
                target.wait_for_function('observerProbe.transfers.length===1', polling=20)
                target.get_by_role('button', name='Observe game', exact=True).wait_for(timeout=18000)
                metrics = target.evaluate('({...observerProbe,pcs:undefined,elapsed:performance.now()-observerProbe.transfers[0].at})')
                assert metrics['imports'] == 0, metrics
                assert metrics['maxChunk'] <= 12 * 1024 and metrics['transfers'][0]['bytes'] <= 2 * 1024 * 1024, metrics
                assert metrics['chunks'] <= 256 and metrics['bytes'] <= 2 * 1024 * 1024 + 64 * 1024, metrics
                if fault == 'hold':
                    assert metrics['dropped'] > 0 and 13000 <= metrics['elapsed'] <= 17500, metrics
                else:
                    assert metrics['corrupted'] > 0 and metrics['elapsed'] < 15000, metrics
                after = host.evaluate('proof.frames.at(-1).frame')
                assert after > before and host.evaluate('proof.room.game.epoch') == epoch
                assert host.evaluate('proof.room.game.status') == 'playing'
                assert all(membership(page) == members for page in pages)
                for page in pages[:4]:
                    if page in observers:
                        page.wait_for_function('proof.frames.at(-1)?.frame>=10', polling=20)
                # Each unaffected worker independently hashes this completed periodic frame.
                hash_frame = ((before // 120) + 1) * 120
                for page in pages[:4]:
                    page.wait_for_function('frame=>proof.hashes.some(value=>value.frame===frame)',arg=hash_frame,polling=20)
                boundary = [page.evaluate('frame=>proof.hashes.find(value=>value.frame===frame)',hash_frame) for page in pages[:4]]
                assert all(value == boundary[0] for value in boundary), boundary
                preserved = target.evaluate(NATIVE)
                assert preserved['frame'] == 0 and preserved['fresh'], preserved
                target.evaluate("window.observerFault='none';sessionStorage.removeItem('observer-proof-fault')")
                target.get_by_role('button', name='Observe game', exact=True).click()
                playing()
                assert host.evaluate('proof.room.game.epoch') == epoch
                host.wait_for_function('frame=>proof.frames.at(-1).frame>=frame+120', arg=after, polling=20)
                recovered = matching_boundary(pages)
                scenarios.append({'fault':fault, 'frames_before':before, 'frames_after_failure':after,
                    'failed_observer_transfer':metrics, 'unaffected_native_states':boundary, 'recovered_native_states':recovered})
                print(f'{fault}: isolated failure and public retry converged at frame {recovered[0]["frame"]}', flush=True)
                if fault == 'corrupt':
                    resume()
            send_bounds = [page.evaluate('({checkpoint:observerProbe.maxCheckpointBuffered,game:observerProbe.maxGameBuffered})') for page in pages]
            assert all(value['checkpoint'] <= 256 * 1024 and value['game'] <= 64 * 1024 for value in send_bounds), send_bounds
            assert not errors, errors
            result = {'result':'pass', 'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=runtime,text=True).strip(),
                'build_files':{str(path.relative_to(static)):hashlib.sha256(path.read_bytes()).hexdigest() for path in static.rglob('*') if path.suffix in ('.js','.wasm')},
                'proof_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'members':5, 'pairs':10, 'scenarios':scenarios, 'actual_send_buffer_maxima':send_bounds,
                'retention_contract':{'history_frames':2048,'history_bytes':20480,'owner':'apps/client/src/game-scheduler.ts',
                    'bounded_history_test':'apps/client/src/game-scheduler.test.ts', 'note':'Internal ring bound is covered by source/unit test; browser metrics measure actual transport buffers and transfer sizes.'},
                'page_errors':errors, 'seconds':round(time.monotonic()-started,2)}
            args.output.write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps({'result':'pass','seconds':result['seconds']}))
        except Exception:
            for index,page in enumerate(pages):
                with contextlib.suppress(Exception):
                    args.output.with_suffix(f'.member{index}.json').write_text(json.dumps(page.evaluate('({room:proof.room,status:document.querySelector("[data-testid=game-status]")?.textContent,probe:{...observerProbe,pcs:undefined}})'),indent=2))
                    page.screenshot(path=str(args.output.with_suffix(f'.member{index}.png')))
            raise


if __name__ == '__main__':
    main()
