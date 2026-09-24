"""Capture the directory, waiting room, and both included games from the real client."""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[2]
started = time.monotonic()
service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=root,
    env={**os.environ, 'COORDINATOR_EMPTY_OFFERS': 'super-tilt-bro-pal,from-below-1.0'}, stdout=subprocess.PIPE, text=True)
try:
    url = json.loads(service.stdout.readline())['url']
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        errors = []
        def page(width, height):
            tab = browser.new_page(viewport={'width': width, 'height': height})
            tab.on('pageerror', lambda error: errors.append(str(error)))
            tab.goto(url)
            tab.get_by_role('button', name='Join as host').first.wait_for()
            return tab
        def fit(tab):
            bounds = tab.evaluate('({width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,viewportWidth:innerWidth,viewportHeight:innerHeight})')
            assert bounds['width'] <= bounds['viewportWidth'] and bounds['height'] <= bounds['viewportHeight'], bounds
            return bounds
        def claim(tab, title):
            row = tab.locator('.room-list li').filter(has_text=title).filter(has_text='0/2 · Waiting for host').first
            row.get_by_role('button', name='Join as host').click()
            tab.get_by_role('button', name='Start game', exact=True).wait_for()
            tab.wait_for_function("!document.querySelector('.room-start button').disabled", timeout=30000)
            assert 'Player 1 · Host' in tab.locator('.room-slots').inner_text()
        wide = page(1280, 800)
        assert wide.locator('.room-list li').filter(has_text='0/2 · Waiting for host').count() == 2
        fit(wide)
        wide.screenshot(path=str(args.output / 'directory-wide.png'))
        claim(wide, 'Super Tilt Bro')
        fit(wide)
        wide.screenshot(path=str(args.output / 'waiting-room.png'))
        wide.get_by_role('button', name='Start game', exact=True).click()
        wide.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>30", timeout=30000)
        wide.screenshot(path=str(args.output / 'super-tilt-playing.png'))
        wide.get_by_role('button', name='Public rooms', exact=True).click()
        before = int(wide.get_by_test_id('frames').inner_text().split()[0])
        wide.locator('.room-list li').first.wait_for()
        assert wide.locator('.room-list li button').count() == 0
        wide.wait_for_timeout(200)
        assert int(wide.get_by_test_id('frames').inner_text().split()[0]) > before
        wide.get_by_role('button', name='Return to room', exact=True).click()
        assert wide.locator('.room-panel').is_visible()
        narrow = page(760, 680)
        fit(narrow)
        assert 'One controller; share turns' in narrow.locator('.room-list li').filter(has_text='From Below').first.inner_text()
        narrow.screenshot(path=str(args.output / 'directory-narrow.png'))
        claim(narrow, 'From Below')
        assert 'Both players must agree to a handoff' in narrow.locator('.room-panel').inner_text()
        fit(narrow)
        narrow.screenshot(path=str(args.output / 'from-below-waiting.png'))
        narrow.get_by_role('button', name='Start game', exact=True).click()
        narrow.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>120", timeout=30000)
        narrow.wait_for_function("()=>{const c=document.querySelector('canvas'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;return d.some((v,i)=>i%4!==3&&v!==0)}", timeout=30000)
        narrow.screenshot(path=str(args.output / 'from-below-playing.png'))
        assert narrow.locator('.room-panel').is_visible()
        fit(narrow)
        narrow.screenshot(path=str(args.output / 'room-region.png'))
        assert not errors, errors
        proof = {'result': 'pass', 'included_rooms': 2, 'claim_and_replenish': True, 'both_games_rendered': True, 'narrow_and_wide_fit': True, 'browser': browser.version, 'seconds': round(time.monotonic() - started, 2), 'page_errors': errors}
        (args.output / 'browser.json').write_text(json.dumps(proof, indent=2) + '\n')
        print(json.dumps(proof, indent=2))
        browser.close()
finally:
    service.terminate()
    service.wait(timeout=5)
