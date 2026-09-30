"""Verify actual included games, local observers, and exact role-promotion checkpoints."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=Path('/tmp/catalog-slots.json'))
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
static = Path(os.environ.get('RETRO_COOP_STATIC_ROOT', root / 'apps/client/dist'))
args.output.parent.mkdir(parents=True, exist_ok=True)
catalog = json.loads(subprocess.check_output([
    'node', '--input-type=module', '-e',
    "import {catalog} from './packages/contracts/src/catalog.ts';console.log(JSON.stringify(catalog))",
], cwd=root, text=True))
# Use only the existing, explicitly enabled, digest-verified supplied artifacts.
# Missing files are an unavailable qualification, never a synthetic-ROM substitute.
for entry in catalog:
    asset = static / 'catalog' / f"{entry['assetName']}-{entry['sha256']}.nes"
    if not asset.is_file():
        args.output.write_text(json.dumps({'result': 'unavailable', 'game': entry['id'],
            'reason': 'Build with both PUBLIC_CATALOG_GAMES enabled and the supplied verified assets.'}, indent=2))
        raise SystemExit(f"Included asset unavailable: {entry['id']}")
    data = asset.read_bytes()
    assert len(data) == entry['bytes'] and hashlib.sha256(data).hexdigest() == entry['sha256']

started = time.monotonic()
errors, results = [], []
with contextlib.ExitStack() as stack:
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=root,
        env={**os.environ, 'COORDINATOR_EMPTY_OFFERS': ','.join(entry['id'] for entry in catalog),
             'TURN_URLS': '', 'TURN_SECRET': ''}, stdout=subprocess.PIPE, text=True)
    stack.callback(service.wait, timeout=10)
    stack.callback(service.terminate)
    url = json.loads(service.stdout.readline())['url']
    playwright = stack.enter_context(sync_playwright())
    browsers = [playwright.chromium.launch(ignore_default_args=['--mute-audio']) for _ in range(2)]
    for browser in browsers:
        stack.callback(browser.close)

    def native(page):
        return page.evaluate("""()=>new Promise((resolve,reject)=>{
          const requestId=window.nativeRequest=(window.nativeRequest??800000)+1;
          const done=({data})=>{if(data.requestId!==requestId)return;
            clearTimeout(timer);currentWorker.removeEventListener('message',done);
            data.type==='error'?reject(Error(data.message)):resolve(data.info);};
          const timer=setTimeout(()=>{currentWorker.removeEventListener('message',done);reject(Error('Native hash timed out'));},3000);
          currentWorker.addEventListener('message',done);currentWorker.postMessage({type:'state-hash',requestId});})""")

    def paused_states(pages):
        for page in pages:
            page.wait_for_function("proof.room.game.status==='paused'", polling=20)
        deadline = time.monotonic() + 5
        while True:
            states = [native(page) for page in pages]
            if all(state == states[0] for state in states):
                return states
            assert time.monotonic() < deadline, states
            time.sleep(.05)

    for entry in catalog:
        print(f"catalog-slots: {entry['title']}", flush=True)
        contexts = [browser.new_context(viewport={'width': 1440, 'height': 1100}) for browser in browsers]
        pages = [contexts[0].new_page(), contexts[0].new_page(), contexts[1].new_page()]
        downloads = [[] for _ in pages]
        try:
            for index, page in enumerate(pages):
                page.set_default_timeout(30000)
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('response', lambda response, index=index: downloads[index].append(response.status)
                    if '/catalog/' in response.url and entry['sha256'] in response.url else None)
                page.add_init_script(path=root / 'scripts/gameplay/fixture.js')
                page.add_init_script("""window.catalogProof={starts:[],imports:[]};
                  const Socket=WebSocket;window.WebSocket=class extends Socket{constructor(...a){super(...a);
                    this.addEventListener('message',({data})=>{const e=JSON.parse(data);if(e.type==='gameStart'){
                      catalogProof.starts.push({frame:e.frame,hash:e.hash});if(catalogProof.starts.length>64)catalogProof.starts.shift();}})}};
                  const Core=Worker;window.Worker=class extends Core{constructor(...a){super(...a);
                    this.addEventListener('message',({data})=>{if(data.type==='peer-checkpoint-imported'){
                      catalogProof.imports.push({frame:data.frame,hash:data.hash});if(catalogProof.imports.length>64)catalogProof.imports.shift();}})}};""")
            host = pages[0]
            host.goto(url)
            host.get_by_role('button', name='Create game', exact=True).click()
            host.get_by_role('button', name=re.compile('^' + re.escape(entry['title']))).click()
            host.get_by_role('button', name='Create room', exact=True).click()
            host.get_by_role('button', name='Copy invite', exact=True).wait_for()
            invite = host.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite")
            for page in pages[1:]:
                page.goto(invite)
                page.get_by_role('button', name='Join room', exact=True).click()
                page.wait_for_function("proof.room?.matches&&proof.room.slots.find(s=>s.member?.id===proof.room.chatMembership)?.member.acquisition==='loaded'", polling=50)
            for page in pages:
                page.wait_for_function("proof.room?.occupancy===3&&proof.room.peers.length===2&&proof.room.peers.every(p=>p.status==='connected')", polling=50)
                assert page.get_by_test_id('room-slot').count() == 5
                assert page.evaluate('proof.room.catalogId') == entry['id']
                assert page.evaluate('proof.room.fingerprint.romSha256') == entry['sha256']
            expected_roles = ['player1', 'player2' if entry['controllers'] == 2 else 'observer', 'observer', 'observer', 'observer']
            assert host.evaluate('proof.room.slots.map(s=>s.role)') == expected_roles
            if entry['controllers'] == 1:
                assert host.get_by_label('Slot 3 role', exact=True).locator('option[value=player2]').count() == 0
            else:
                pages[1].get_by_role('button', name='Ready', exact=True).click()
                pages[1].wait_for_function('proof.room.game.ready.includes(proof.room.chatMembership)', polling=20)
            host.get_by_role('button', name='Start game', exact=True).click()
            for page in pages:
                page.evaluate('releaseFrames()')
            for page in pages[1 if entry['controllers'] == 1 else 2:]:
                page.wait_for_function('proof.frames.at(-1)?.frame>=10', polling=20)
            host.wait_for_function('proof.frames.at(-1)?.frame>=180', polling=20)
            host.get_by_role('button', name='Pause', exact=True).click()
            before = paused_states(pages)
            assert all(page.evaluate('catalogProof.imports.length') > 0 for page in pages[1 if entry['controllers'] == 1 else 2:])
            host.screenshot(path=str(args.output.with_suffix(f".{entry['id']}.before.png")))
            role = 'player1' if entry['controllers'] == 1 else 'player2'
            promoted = pages[2].evaluate('proof.room.chatMembership')
            host.get_by_label('Slot 3 role', exact=True).select_option(role)
            host.wait_for_function("owner=>proof.room.game.status==='playing'&&proof.room.game.controllers.owners.includes(owner)", arg=promoted, polling=20)
            assert host.evaluate('proof.room.slots.map(s=>s.role)')[entry['controllers'] - 1] == 'observer'
            boundary = {'frame': before[0]['frame'], 'hash': before[0]['hash']}
            assert boundary in host.evaluate('catalogProof.starts')
            assert boundary in pages[2].evaluate('catalogProof.imports')
            host.wait_for_function('frame=>proof.frames.at(-1)?.frame>=frame+120', arg=boundary['frame'], polling=20)
            host.get_by_role('button', name='Pause', exact=True).click()
            after = paused_states(pages)
            assert after[0]['frame'] > before[0]['frame']
            host.screenshot(path=str(args.output.with_suffix(f".{entry['id']}.promoted.png")))
            # A same-origin tab may reuse the verified IndexedDB copy. Independent
            # contexts must acquire the actual immutable artifact through HTTP.
            assert 200 in downloads[0] and 200 in downloads[2], downloads
            results.append({'id': entry['id'], 'romSha256': entry['sha256'], 'controllers': entry['controllers'],
                'initialRoles': expected_roles, 'before': before, 'promotionBoundary': boundary, 'after': after,
                'catalogHttpStatusesByMember': downloads, 'verifiedCatalogAcquisition': True, 'nativeObserverImport': True, 'exactPromotionImport': True})
        except Exception:
            failure = []
            for index, page in enumerate(pages):
                page.screenshot(path=str(args.output.with_suffix(f".{entry['id']}.failure{index}.png")))
                failure.append(page.evaluate("""({status:document.querySelector('[data-testid=game-status]')?.textContent,
                  loaded:document.querySelector('[data-testid=player-status]')?.textContent,
                  catalog:proof.room?.catalogId,matches:proof.room?.matches,
                  acquisition:proof.room?.slots.map(s=>({role:s.role,phase:s.member?.acquisition})),
                  game:proof.room?.game.status,evidence:catalogProof})"""))
            args.output.write_text(json.dumps({'result': 'failed', 'completed': results, 'game': entry['id'], 'errors': errors, 'members': failure}, indent=2))
            raise
        finally:
            for context in contexts:
                context.close()
    assert not errors, errors
    result = {'result': 'pass', 'games': results, 'membersPerGame': 3, 'sameOriginTabs': True,
        'browserProcesses': 2, 'browser': browsers[0].version, 'errors': errors,
        'elapsedSeconds': round(time.monotonic() - started, 2)}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
