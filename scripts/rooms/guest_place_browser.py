#!/usr/bin/env python3
"""Exercise five-slot admission and kick decisions through the current lobby UI."""

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from ui_helpers import rename_lobby


ROOT = Path(__file__).resolve().parents[2]


def slot_action(page, slot_id, name):
    slot = page.locator(f'[data-slot-id="{slot_id}"]')
    row = slot.locator('.slot-row')
    expect(row).to_be_enabled(timeout=15000)
    row.click()
    slot.get_by_role('menuitem', name=name).click()
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='/tmp/guest-place.json')
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                               stdout=subprocess.PIPE, text=True)
    try:
        url = json.loads(service.stdout.readline())['url']
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            errors = []
            context = browser.new_context(permissions=['clipboard-read', 'clipboard-write'],
                                          viewport={'width': 1280, 'height': 800})
            host = context.new_page()
            guest = browser.new_page(viewport={'width': 1024, 'height': 600})
            for page in (host, guest):
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.set_default_timeout(10000)

            host.goto(url)
            host.get_by_role('button', name='Host a new game').click()
            rename_lobby(host, 'Five Places')
            host.get_by_role('button', name='Load NES game').wait_for(timeout=15000)
            assert host.get_by_test_id('room-slot').count() == 5
            assert host.get_by_role('button', name='Start →').count() == 0
            host.get_by_role('button', name='Copy invite').click()
            invite = host.evaluate('navigator.clipboard.readText()')

            for slot_id in ('slot-2', 'slot-3', 'slot-4', 'slot-5'):
                row = slot_action(host, slot_id, 'Close slot')
                expect(row).to_have_attribute('aria-label', re.compile('Closed Slot'), timeout=15000)
            expect(host.locator('.rc-players .rc-section-head small')).to_have_text('1/5')

            guest.goto(url)
            guest.locator('.rc-listing').wait_for()
            guest.get_by_placeholder('Search lobbies').fill('Five Places')
            card = guest.locator('.rc-lobby-card').filter(has_text='Five Places')
            card.wait_for(timeout=15000)
            assert card.is_disabled() and card.get_attribute('title') == 'No open places'
            guest.goto(invite)
            guest.get_by_role('heading', name='Five Places').wait_for(timeout=15000)
            guest.get_by_text('No open places. Browse other lobbies or wait for the host.').wait_for()
            assert guest.get_by_role('button', name='Join lobby').is_disabled()
            slot_action(host, 'slot-2', 'Open slot')
            expect(host.locator('[data-slot-id="slot-2"] .slot-row')).to_have_attribute(
                'aria-label', re.compile('Open Slot 2'), timeout=15000)
            expect(guest.get_by_role('button', name='Join lobby')).to_be_enabled(timeout=15000)
            guest.get_by_role('button', name='Join lobby').click()
            guest.get_by_text('Waiting for the host to load a NES game').wait_for(timeout=15000)
            expect(host.locator('.rc-players .rc-section-head small')).to_have_text('2/5')
            expect(host.locator('[data-slot-id="slot-2"] .slot-row')).to_have_attribute(
                'aria-label', re.compile('P2 ·'), timeout=15000)

            member_name = host.locator('[data-slot-id="slot-2"] .slot-row strong').inner_text().split(' · ', 1)[1]
            slot_action(host, 'slot-2', f'Kick {member_name}')
            host.get_by_role('alertdialog', name=f'Kick {member_name}?').wait_for()
            host.get_by_role('button', name='Cancel', exact=True).click()
            assert guest.locator('[data-page="lobby"]').count() == 1
            slot_action(host, 'slot-2', f'Kick {member_name}')
            host.get_by_role('button', name='Kick player', exact=True).click()
            expect(host.locator('.rc-players .rc-section-head small')).to_have_text('1/5')
            guest.locator('.rc-listing').wait_for(timeout=15000)
            assert host.get_by_test_id('room-slot').count() == 5
            assert not errors, errors
            result = {'result': 'pass', 'five_slots_fixed': True, 'full_lobby_blocks_join': True,
                      'reopened_slot_admits_guest': True, 'kick_cancel_keeps_guest': True,
                      'kick_confirm_releases_guest': True, 'page_errors': errors,
                      'seconds': round(time.monotonic() - started, 2)}
            output.write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result))
            browser.close()
    finally:
        service.terminate()
        service.wait(timeout=10)


if __name__ == '__main__':
    main()
