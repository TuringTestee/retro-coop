#!/usr/bin/env python3
"""Exercise five-slot admission and kick decisions through the current lobby UI."""

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from ui_helpers import choose_panel, choose_section, rename_lobby
from layout_geometry import GeometryRecorder, control_visibility


ROOT = Path(__file__).resolve().parents[2]


def slot_action(page, slot_id, name):
    slot = page.locator(f'[data-slot-id="{slot_id}"]')
    row = slot.locator('.slot-row')
    expect(row).to_be_enabled(timeout=15000)
    row.click()
    slot.get_by_role('menuitem', name=name).click()
    return row


def slot_name(page, slot_id):
    return page.locator(f'[data-slot-id="{slot_id}"] .slot-row strong').inner_text()


def menu_target(item, focused=False):
    """Full label and inset hit areas must remain inside the visible control."""
    visibility = control_visibility(item, require_focus=focused)
    measured = item.evaluate("""node => {
      const box=node.getBoundingClientRect(),range=document.createRange();
      range.selectNodeContents(node);
      return {text:node.textContent.trim(),textFits:[...range.getClientRects()].every(r=>
        r.left>=box.left-1&&r.right<=box.right+1&&r.top>=box.top-1&&r.bottom<=box.bottom+1),
        hitTarget:[2,box.width/2,box.width-2].every(x=>[2,box.height/2,box.height-2].every(y=>
          node.contains(document.elementFromPoint(box.left+x,box.top+y))))};
    }""")
    assert measured['textFits'] and measured['hitTarget'], (measured, visibility)
    return measured


def landscape_moderation(host, guests, output):
    receipts = []
    width, height = 568, 320
    host.set_viewport_size({'width': width, 'height': height})
    choose_panel(host, 'Players')
    recorder = GeometryRecorder(host, f'moderation-{width}x{height}',
                                '.rc-header,.rc-status,.rc-players,.rc-footer')
    for number in range(1, 6):
        slot_id = f'slot-{number}'
        slot = host.locator(f'[data-slot-id="{slot_id}"]')
        row, items = slot.locator('.slot-row'), slot.get_by_role('menuitem')
        expect(row).to_be_enabled()
        row.click()
        expect(row).to_have_attribute('aria-expanded', 'true')
        expect(items).to_have_count(4 if number == 1 else 5)
        labels = [menu_target(items.nth(i)) for i in range(items.count())]
        recorder.mark(f'{slot_id}-open')
        if number == 5:
            host.screenshot(path=str(output.with_name(f'{output.stem}-{width}x{height}.png')))
        # Closing by the same row proves the menu does not cover its trigger.
        menu_target(row)
        row.click()
        expect(items).to_have_count(0)
        expect(row).to_have_attribute('aria-expanded', 'false')
        keyboard = []
        swapped = False
        if number == 5:
            row.focus()
            row.press('ArrowDown')
            expect(items).to_have_count(5)
            for i in range(5):
                item = items.nth(i)
                expect(item).to_be_focused()
                keyboard.append(menu_target(item, focused=True)['text'])
                item.press('ArrowDown')
            expect(items.first).to_be_focused()
            items.first.press('End')
            expect(items.last).to_be_focused()
            items.last.press('Home')
            expect(items.first).to_be_focused()
            items.first.press('Escape')
            expect(row).to_be_focused()
            expect(items).to_have_count(0)
            # One actual player/spectator swap tests the coordinator transition.
            source_name, target_name = slot_name(host, slot_id), slot_name(host, 'slot-2')
            slot_action(host, slot_id, re.compile('Swap with .* · Player 2$'))
            expect(host.locator('[data-slot-id="slot-2"] .slot-row strong')).to_have_text(
                'P2 · ' + source_name)
            expect(slot.locator('.slot-row strong')).to_have_text(target_name.split(' · ', 1)[1])
            slot_action(host, slot_id, re.compile('Swap with .* · Player 2$'))
            expect(slot.locator('.slot-row strong')).to_have_text(source_name)
            expect(host.locator('[data-slot-id="slot-2"] .slot-row strong')).to_have_text(target_name)
            swapped = True
            slot_action(host, slot_id, f'Kick {source_name}')
            dialog = host.get_by_role('alertdialog', name=f'Kick {source_name}?')
            expect(dialog).to_be_visible()
            dialog.get_by_role('button', name='Cancel', exact=True).click()
            expect(dialog).to_have_count(0)
            expect(slot.locator('.slot-row strong')).to_have_text(source_name)
            expect(host.locator('.rc-players .rc-section-head small')).to_have_text('5/5')
            for guest in guests:
                expect(guest.locator('[data-page="lobby"]')).to_have_count(1)
        recorder.mark(f'{slot_id}-restored')
        receipts.append({'size': [width, height], 'slot': slot_id, 'labels': labels,
                         'keyboard': keyboard, 'row_toggle': True,
                         'player_spectator_swap_restored': swapped, 'kick_cancel': number == 5})
    geometry = recorder.finish(output.with_name(f'{output.stem}-{width}x{height}-geometry.json'),
                               required=('rc-header', 'rc-players', 'rc-footer'))
    assert host.evaluate('scrollX === 0 && scrollY === 0')
    receipts[-1]['fixed_regions'] = geometry
    return receipts


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

            choose_section(guest, 'Profile')
            guest.get_by_role('button', name='Edit your name:', exact=False).click()
            guest.get_by_role('textbox', name='Your name').fill('Landscape Moderation Guest Name')
            guest.get_by_role('button', name='Save name', exact=True).click()
            expect(host.locator('[data-slot-id="slot-2"] .slot-row strong')).to_have_text(
                'P2 · Landscape Moderation Guest Name')
            host.set_viewport_size({'width': 568, 'height': 320})
            choose_panel(host, 'Players')
            slot_action(host, 'slot-3', 'Open slot')
            member_name = slot_name(host, 'slot-2').split(' · ', 1)[1]
            slot_action(host, 'slot-2', 'Move as Spectator 3')
            expect(host.locator('[data-slot-id="slot-3"] .slot-row strong')).to_have_text(member_name)
            expect(host.locator('[data-slot-id="slot-2"] .slot-row strong')).to_have_text('Open Slot 2')
            slot_action(host, 'slot-3', 'Move as Player 2')
            expect(host.locator('[data-slot-id="slot-2"] .slot-row strong')).to_have_text(f'P2 · {member_name}')
            host.set_viewport_size({'width': 1280, 'height': 800})
            guests = [guest]
            for slot_id in ('slot-3', 'slot-4', 'slot-5'):
                if slot_id != 'slot-3':
                    slot_action(host, slot_id, 'Open slot')
                joiner = browser.new_page(viewport={'width': 1024, 'height': 600})
                joiner.on('pageerror', lambda error: errors.append(str(error)))
                joiner.goto(invite)
                joiner.get_by_role('button', name='Join lobby').click()
                expect(joiner.locator('[data-page="lobby"]')).to_have_count(1)
                expect(host.locator(f'[data-slot-id="{slot_id}"] .slot-row')).not_to_have_class(re.compile('slot-empty'))
                guests.append(joiner)
            expect(host.locator('.rc-players .rc-section-head small')).to_have_text('5/5')
            moderation = landscape_moderation(host, guests, output)
            host.set_viewport_size({'width': 1280, 'height': 800})

            member_name = host.locator('[data-slot-id="slot-2"] .slot-row strong').inner_text().split(' · ', 1)[1]
            slot_action(host, 'slot-2', f'Kick {member_name}')
            host.get_by_role('alertdialog', name=f'Kick {member_name}?').wait_for()
            host.get_by_role('button', name='Cancel', exact=True).click()
            assert guest.locator('[data-page="lobby"]').count() == 1
            slot_action(host, 'slot-2', f'Kick {member_name}')
            host.get_by_role('button', name='Kick player', exact=True).click()
            expect(host.locator('.rc-players .rc-section-head small')).to_have_text('4/5')
            guest.locator('.rc-listing').wait_for(timeout=15000)
            assert host.get_by_test_id('room-slot').count() == 5
            assert not errors, errors
            result = {'result': 'pass', 'five_slots_fixed': True, 'full_lobby_blocks_join': True,
                      'reopened_slot_admits_guest': True, 'kick_cancel_keeps_guest': True,
                      'kick_confirm_releases_guest': True, 'empty_slot_move_observed_and_restored': True,
                      'landscape_moderation': moderation, 'page_errors': errors,
                      'seconds': round(time.monotonic() - started, 2)}
            output.write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result))
            browser.close()
    finally:
        service.terminate()
        service.wait(timeout=10)


if __name__ == '__main__':
    main()
