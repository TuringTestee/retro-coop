#!/usr/bin/env python3
"""Exercise public and password-protected lobby admission in the built app."""

import json
import os
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright
from ui_helpers import protect_lobby, rename_lobby


ROOT = Path(__file__).resolve().parents[2]
PASSWORD = '🦊' * 100
SCREENS = Path(os.environ['RETRO_COOP_ACCESS_OUTPUT']) if 'RETRO_COOP_ACCESS_OUTPUT' in os.environ else None


def create_lobby(page, url, name, protected=False):
    page.goto(url)
    page.get_by_role('button', name='Host a new game').click()
    rename_lobby(page, name)
    if protected:
        protect_lobby(page, PASSWORD)
    page.get_by_role('button', name='Load NES game').wait_for(timeout=15000)
    assert page.get_by_role('button', name='Start →').count() == 0


def browse(page, url, name):
    page.goto(url)
    page.locator('.rc-listing').wait_for()
    page.get_by_placeholder('Search lobbies').fill(name)
    card = page.locator('.rc-lobby-card').filter(has_text=name)
    card.wait_for(timeout=15000)
    return card


def hold_join(page):
    page.add_init_script("""(() => {
      const send = WebSocket.prototype.send;
      window.heldJoins = [];
      WebSocket.prototype.send = function(raw) {
        let command;
        try { command = JSON.parse(raw); } catch {}
        if (command?.type === 'join' || command?.type === 'joinCode') {
          window.heldJoins.push(() => send.call(this, raw));
          return;
        }
        return send.call(this, raw);
      };
      window.releaseHeldJoin = () => {
        for (const release of window.heldJoins.splice(0)) release();
      };
    })();""")


def main():
    if SCREENS:
        SCREENS.mkdir(parents=True, exist_ok=True)
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                               env={**os.environ, 'COORDINATOR_EMPTY_OFFERS': 'super-tilt-bro-pal'},
                               stdout=subprocess.PIPE, text=True)
    try:
        url = json.loads(service.stdout.readline())['url']
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            host = browser.new_context(permissions=['clipboard-read', 'clipboard-write'],
                                       viewport={'width': 1280, 'height': 800}).new_page()
            create_lobby(host, url, 'Private Arcade', protected=True)
            host.get_by_role('button', name='Copy invite').click()
            invite = host.evaluate('navigator.clipboard.readText()')
            assert '#invite=' in invite

            guest = browser.new_page(viewport={'width': 1280, 'height': 800})
            card = browse(guest, url, 'Private Arcade')
            assert 'Password' in card.inner_text()
            card.click()
            guest.get_by_label('Lobby password').fill('wrong-password')
            guest.get_by_role('button', name='Join lobby', exact=True).click()
            guest.locator('.rc-join-detail').get_by_role('alert').get_by_text(
                "Password didn't work. Try again.", exact=True).wait_for()
            assert guest.get_by_role('button', name='Load NES game').count() == 0
            if SCREENS:
                guest.screenshot(path=str(SCREENS / 'wrong-password.png'))
            guest.get_by_label('Lobby password').fill(PASSWORD)
            assert guest.locator('.rc-join-detail').get_by_role('alert').count() == 0
            guest.get_by_role('button', name='Join lobby', exact=True).click()
            guest.get_by_text('Waiting for the host to load a NES game').wait_for(timeout=15000)
            assert 'Private Arcade' in guest.locator('.rc-trail').inner_text()

            invited = browser.new_page(viewport={'width': 390, 'height': 700})
            invited.goto(invite)
            invited.get_by_role('heading', name='Private Arcade').wait_for(timeout=15000)
            invited.get_by_label('Lobby password').fill('wrong-password')
            invited.get_by_role('button', name='Join lobby', exact=True).click()
            invited.locator('.rc-status').get_by_text(
                "Password didn't work. Try again.", exact=True).wait_for()
            invited.get_by_label('Lobby password').fill(PASSWORD)
            invited.get_by_role('button', name='Join lobby', exact=True).click()
            invited.get_by_text('Waiting for the host to load a NES game').wait_for(timeout=15000)
            if SCREENS:
                invited.screenshot(path=str(SCREENS / 'joined-mobile.png'))

            pending = browser.new_page(viewport={'width': 1024, 'height': 600})
            hold_join(pending)
            browse(pending, url, 'Private Arcade').click()
            pending.get_by_label('Lobby password').fill(PASSWORD)
            pending.get_by_role('button', name='Join lobby', exact=True).click()
            pending.wait_for_function('window.heldJoins.length === 1')
            pending.locator('.rc-join-detail').get_by_role('button', name='Cancel').click()
            pending.evaluate('window.releaseHeldJoin()')
            pending.wait_for_timeout(500)
            assert pending.get_by_role('button', name='Load NES game').count() == 0
            assert pending.locator('.rc-listing').is_visible()
            pending.close()

            public_host = browser.new_page()
            create_lobby(public_host, url, 'Open Arcade')
            public_guest = browser.new_page()
            public_card = browse(public_guest, url, 'Open Arcade')
            assert 'Public' in public_card.inner_text()
            public_card.click()
            public_guest.get_by_text('Waiting for the host to load a NES game').wait_for(timeout=15000)
            assert public_guest.get_by_label('Lobby password').count() == 0
            print(json.dumps({'protected_creation_without_game': True,
                              'directory_and_invite_password_recovery': True,
                              'pending_protected_join_cancelled': True,
                              'public_join_without_password': True}))
            browser.close()
    finally:
        service.terminate()
        service.wait(timeout=10)


if __name__ == '__main__':
    main()
