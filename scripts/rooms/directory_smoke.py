"""Verify the current one-row host, whole-row join, and protected-lobby flow."""

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--chrome', action='store_true')
parser.add_argument('--output', default='directory.local.json')
args = parser.parse_args()
started = time.monotonic()
service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                           stdout=subprocess.PIPE, text=True)


def new_page(browser, url):
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    page.goto(url, wait_until='domcontentloaded')
    page.locator('.rc-listing').wait_for()
    return page


def create(page, label, nickname=None):
    page.get_by_role('button', name='Host a new game').click()
    page.get_by_role('button', name='Back to Main Page', exact=True).wait_for()
    if nickname:
        page.get_by_role('button', name='Edit your name:', exact=False).click()
        page.get_by_role('textbox', name='Your name').fill(nickname)
        page.get_by_role('textbox', name='Your name').press('Enter')
    page.locator('.rc-trail .rc-header-edit').click()
    page.get_by_role('textbox', name='Lobby name').fill(label)
    page.get_by_role('textbox', name='Lobby name').press('Enter')
    page.locator('.rc-trail .rc-header-edit', has_text=label).wait_for()
    assert page.get_by_role('button', name='Load NES game').count() == 1


def leave(page, host=False):
    page.get_by_role('button', name='Back to Main Page', exact=True).click()
    page.get_by_role('button', name='Close lobby' if host else 'Leave lobby').click()
    page.locator('.rc-listing').wait_for()


try:
    assert service.stdout
    url = json.loads(service.stdout.readline())['url']
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            ignore_default_args=['--mute-audio'],
            **({'channel': 'chrome'} if args.chrome else {}),
        )
        try:
            viewer = new_page(browser, url)
            viewer.get_by_text('No lobbies yet.', exact=True).wait_for()
            assert viewer.get_by_role('button', name='Host a new game').count() == 1
            hosts = [new_page(browser, url), new_page(browser, url)]
            for host in hosts:
                create(host, 'Duplicate Arcade', 'Alex')
            search = viewer.get_by_role('searchbox', name='Search lobbies')
            search.fill('Duplicate Arcade')
            viewer.wait_for_function('document.querySelectorAll(".rc-lobby-card").length === 2')
            cards = viewer.locator('.rc-lobby-card')
            codes = cards.locator('.rc-card-disambiguator').all_text_contents()
            assert len(codes) == 2 and codes[0] != codes[1], codes
            assert cards.first.locator('.rc-card-count').inner_text() == '1/5'
            cards.first.click()
            viewer.locator('[data-page="lobby"]').wait_for()
            assert 'You' in viewer.locator('[data-slot-id="slot-2"]').inner_text()
            leave(viewer)
            search = viewer.get_by_role('searchbox', name='Search lobbies')
            search.fill('Duplicate Arcade')
            viewer.wait_for_function('document.querySelectorAll(".rc-lobby-card").length === 2')

            protected = new_page(browser, url)
            create(protected, 'Secret Arcade')
            protected.get_by_role('button', name='Require password').click()
            protected.get_by_role('textbox', name='New lobby password').fill('arcade passphrase')
            protected.get_by_role('button', name='Save password').click()
            protected.get_by_text('Password protected', exact=True).wait_for()
            search.fill('Secret Arcade')
            card = viewer.locator('.rc-lobby-card', has_text='Secret Arcade')
            card.wait_for()
            assert 'Password' in card.inner_text()
            card.click()
            viewer.get_by_role('textbox', name='Lobby password').fill('wrong-password')
            viewer.get_by_role('button', name='Join lobby', exact=True).click()
            viewer.get_by_text("Password didn't work. Try again.", exact=True).wait_for()
            viewer.get_by_role('textbox', name='Lobby password').fill('arcade passphrase')
            viewer.get_by_role('button', name='Join lobby', exact=True).click()
            viewer.locator('[data-page="lobby"]').wait_for()
            assert 'You' in viewer.locator('[data-slot-id="slot-2"]').inner_text()
            leave(viewer)
            for host in hosts:
                leave(host, host=True)
            leave(protected, host=True)
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps({'result': 'pass', 'duplicate_codes': codes,
                'protected_join': True, 'duration_s': round(time.monotonic()-started, 2)}) + '\n')
            print(json.dumps({'result': 'pass', 'duplicate_codes': codes,
                'protected_join': True, 'duration_s': round(time.monotonic()-started, 2)}), flush=True)
        finally:
            browser.close()
finally:
    service.terminate()
    service.wait(timeout=10)
