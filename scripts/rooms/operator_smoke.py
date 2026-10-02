#!/usr/bin/env python3
"""Check operator closure and temporary access recovery in the unified lobby UI."""

import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(os.environ.get('RETRO_COOP_STATIC_ROOT', ROOT / 'apps/client/dist'))
ROM = STATIC / 'generated/diagnostic.nes'
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=Path('operator.local.json'))
args = parser.parse_args()
assert ROM.exists(), 'Build the client and diagnostic NES fixture first.'
started = time.monotonic()
errors = []

with tempfile.TemporaryDirectory(prefix='retro-operator-browser-') as directory:
    service = subprocess.Popen(
        ['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
        env={**os.environ, 'TURN_URLS': '', 'TURN_SECRET': '',
             'COORDINATOR_OPERATOR_DIR': directory},
        stdout=subprocess.PIPE, text=True)

    def request(command):
        result = subprocess.run(
            ['node', '--input-type=module', '-e',
             "import {operatorRequest} from './apps/coordinator/src/operator.ts';"
             "const a=JSON.parse(process.argv[1]);"
             "console.log(JSON.stringify(await operatorRequest(a.directory,a.command)));",
             json.dumps({'directory': directory, 'command': command})],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=5)
        return json.loads(result.stdout)

    def confirm(action, target, seconds=None):
        command = ['node', 'apps/coordinator/src/operator-cli.ts', directory,
                   action, target]
        if seconds is not None:
            command.append(str(seconds))
        result = subprocess.run(command, input='CONFIRM\n', cwd=ROOT,
                                capture_output=True, text=True, check=True, timeout=5)
        assert 'Type CONFIRM' in result.stdout and 'Done.' in result.stdout
        return result.stdout

    try:
        assert service.stdout
        url = json.loads(service.stdout.readline())['url']
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                channel='chromium', ignore_default_args=['--mute-audio'],
                args=['--use-fake-device-for-media-stream',
                      '--use-fake-ui-for-media-stream'])

            def page(address):
                tab = browser.new_page(viewport={'width': 1280, 'height': 800})
                tab.context.grant_permissions(
                    ['microphone', 'clipboard-read', 'clipboard-write'])
                tab.on('pageerror', lambda error: errors.append(str(error)))
                tab.add_init_script((ROOT / 'scripts/voice/fixtures.js').read_text())
                tab.add_init_script('''(() => {
                  const terminate=Worker.prototype.terminate;
                  window.terminatedWorkers=0;
                  Worker.prototype.terminate=function(...args){
                    window.terminatedWorkers++;return terminate.apply(this,args);
                  };
                })()''')
                tab.goto(address)
                return tab

            def voice(tab):
                tab.get_by_role('button', name='Voice', exact=True).click()
                tab.get_by_role('button', name='Enable voice').click()
                tab.wait_for_function(
                    "captures.length>0 && captures.at(-1).getAudioTracks().some(t=>t.enabled&&t.readyState==='live')")

            def pair():
                host = page(url)
                host.get_by_role('button', name='Host a new game').click()
                host.locator('[data-page="lobby"]').wait_for(timeout=15000)
                host.get_by_role('button', name='Copy invite').click()
                invitation = host.evaluate('navigator.clipboard.readText()')
                guest = page(invitation)
                guest.get_by_role('button', name='Join lobby').click()
                guest.locator('[data-page="lobby"]').wait_for(timeout=15000)
                for tab in (host, guest):
                    voice(tab)
                    tab.wait_for_function("pcs.some(pc=>pc.connectionState==='connected')")
                return host, guest

            def stopped(tab, message):
                tab.locator('.rc-listing').wait_for(timeout=15000)
                tab.locator('.rc-status').get_by_text(
                    message, exact=False).wait_for(timeout=15000)
                assert tab.locator('[data-page="lobby"], [data-page="playing"]').count() == 0
                tab.wait_for_function(
                    "pcs.every(pc=>pc.connectionState==='closed') && "
                    "captures.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")

            host, guest = pair()
            host.locator('input[aria-label="NES cartridge file"]').set_input_files(ROM)
            for tab in (host, guest):
                expect(tab.get_by_role('button', name='Ready', exact=True)).to_be_enabled(
                    timeout=30000)
                tab.get_by_role('button', name='Ready', exact=True).click()
            expect(host.get_by_role('button', name='Start →')).to_be_enabled(
                timeout=30000)
            host.get_by_role('button', name='Start →').click()
            for tab in (host, guest):
                tab.locator('[data-page="playing"]').wait_for(timeout=30000)
            workers_before = host.evaluate('window.terminatedWorkers')
            writes_before = host.evaluate('timelineWrites')
            args.output.parent.mkdir(parents=True, exist_ok=True)
            host.screenshot(path=str(args.output.with_suffix('.playing.png')))
            active = request({'type': 'list'})['rooms']
            assert len(active) == 1 and active[0]['occupancy'] == 2
            removal = confirm('remove-room', active[0]['id'])
            for tab in (host, guest):
                stopped(tab, 'An operator closed this lobby.')
            host.wait_for_function('before => window.terminatedWorkers > before',
                                   arg=workers_before)
            assert host.evaluate('timelineWrites') == writes_before
            assert request({'type': 'list'})['rooms'] == []
            host.screenshot(path=str(args.output.with_suffix('.removed.png')))
            host.close()
            guest.close()

            host, guest = pair()
            subjects = request({'type': 'list'})['subjects']
            subject = next(item for item in subjects if item['connections'] == 2)
            assert subject['address'] == '127.0.0.1'
            block = confirm('block-address', subject['id'], 5)
            for tab in (host, guest):
                stopped(tab, 'Access is temporarily restricted')
            assert request({'type': 'list'})['rooms'] == []
            host.set_viewport_size({'width': 390, 'height': 700})
            assert host.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert host.evaluate('document.scrollingElement.scrollHeight <= innerHeight + 1')
            host.screenshot(path=str(args.output.with_suffix('.blocked.png')))

            fresh = page(url)
            fresh.locator('.rc-listing').wait_for()
            fresh.locator('.rc-status').get_by_text('Access to lobbies is temporarily restricted. Retry later.').wait_for(
                timeout=15000)
            fresh.locator('.rc-join-detail').get_by_text(
                'Access is temporarily restricted', exact=False).wait_for()
            fresh.reload()
            fresh.locator('.rc-listing').wait_for()
            fresh.locator('.rc-status').get_by_text('Access to lobbies is temporarily restricted. Retry later.').wait_for()
            deadline = time.monotonic() + 10
            while any(item.get('blockedUntil') for item in
                      request({'type': 'list'})['subjects']):
                assert time.monotonic() < deadline, 'Temporary block did not expire.'
                time.sleep(.05)
            fresh.locator('.rc-status-action').click()
            fresh.get_by_text('No lobbies yet.').wait_for(timeout=15000)
            fresh.get_by_role('button', name='Host a new game').click()
            fresh.locator('[data-page="lobby"]').wait_for(timeout=15000)
            assert fresh.get_by_role('button', name='Load NES game').is_visible()
            fresh.screenshot(path=str(args.output.with_suffix('.restored.png')))
            assert not errors, errors
            result = {
                'result': 'pass', 'browser': browser.version,
                'private_cli_confirmation': [removal, block],
                'operator_removal_stops_game_and_voice': True,
                'blocked_tabs_lose_lobby_and_voice': True,
                'restriction_explained_on_fresh_and_reloaded_page': True,
                'expired_block_allows_empty_lobby_creation': True,
                'seconds': round(time.monotonic() - started, 2),
                'page_errors': errors,
            }
            args.output.write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result))
            browser.close()
    finally:
        service.terminate()
        try:
            service.wait(timeout=5)
        except subprocess.TimeoutExpired:
            service.kill()
            service.wait()
