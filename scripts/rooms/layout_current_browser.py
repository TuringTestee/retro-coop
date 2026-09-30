#!/usr/bin/env python3
"""Check current room, password, and directory bounds during real transitions.

The recorder begins before each action and compares every animation frame. A new
recorder is made after navigation or zoom, when a new layout is expected.
"""
import argparse
import json
import os
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

from layout_geometry import GeometryRecorder, browser_zoom, control_visibility, zoom_context

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(os.environ.get('RETRO_COOP_STATIC_ROOT', ROOT / 'apps/client/dist'))
SLOTS = '.room-slots [data-slot-id], .room-slots [data-slot-region]'
ROOM_ACTIONS = '[data-layout-region=readiness-actions], [data-layout-region=start-actions], [data-layout-region=invite-actions], [data-layout-region=leave-actions], [data-layout-region=connection-recovery]'
PASSWORD = '.room-password-dialog, .room-password-dialog h3, .room-password-dialog [role=alert], [data-layout-region=password-join], [data-layout-region=password-back]'
DIRECTORY = '.directory-panel, .directory-panel [data-layout-region], .directory-title button'


def record(page, output, label, selector, required):
    return GeometryRecorder(page, label, selector), output / f'{label}.json', required


def finish(check):
    recorder, path, required = check
    return recorder.finish(path, required=required)


def room_host(browser, url, viewport):
    context = browser.new_context(viewport=viewport, permissions=['clipboard-read', 'clipboard-write'])
    context.add_init_script('window.layoutSockets=[];const OriginalSocket=WebSocket;window.WebSocket=class extends OriginalSocket{constructor(...args){super(...args);layoutSockets.push(this)}};')
    page = context.new_page()
    page.goto(url)
    page.get_by_role('button', name='Create game', exact=True).click()
    page.locator('input[type=file]').set_input_files(STATIC / 'generated/diagnostic.nes')
    page.get_by_label('Room access').select_option('protected')
    page.get_by_label('Room password').fill('blue-sky-room')
    page.get_by_role('button', name='Create room', exact=True).click()
    page.get_by_test_id('room-view').wait_for(state='attached')
    return context, page


def check_profile(browser, url, output, label, viewport, directory_check=None):
    context, host = room_host(browser, url, viewport)
    try:
        checks = []
        if directory_check:
            viewer, check = directory_check
            viewer.locator('.room-list li').filter(has_text='Password required').first.wait_for()
            check[0].mark('protected-room-listed')
            checks.append(finish(check))
        host.get_by_role('button', name='Copy invite', exact=True).click()
        invite = host.evaluate('navigator.clipboard.readText()')
        assert host.get_by_label('Room invitation', exact=True).count() == 0

        # Host actions and slot cells survive final-slot admission, readiness,
        # leave confirmation and connection recovery without moving.
        slot = record(host, output, f'{label}-slots', SLOTS + ', ' + ROOM_ACTIONS,
                      ['slot-1', 'slot-2', 'slot-2/status', 'readiness-actions', 'start-actions', 'invite-actions', 'leave-actions', 'connection-recovery'])
        guest = context.new_page()
        guest.goto(invite)
        guest.get_by_role('button', name='Join room', exact=True).click()
        dialog = guest.locator('.room-password-dialog')
        dialog.wait_for(state='visible')
        password = record(guest, output, f'{label}-password', PASSWORD,
                          ['room-password-dialog', 'H3', 'P', 'password-join', 'password-back'])
        guest.get_by_label('Room password').fill('wrong-password')
        guest.locator('.room-password-dialog').get_by_role('button', name='Join room', exact=True).click()
        guest.get_by_role('alert').get_by_text("Password didn't work. Try again.", exact=True).wait_for()
        password[0].mark('wrong-password')
        checks.append(finish(password))
        guest.get_by_label('Room password').fill('blue-sky-room')
        guest.locator('.room-password-dialog').get_by_role('button', name='Join room', exact=True).click()
        guest.get_by_test_id('room-view').wait_for(state='attached')
        guest_actions = record(guest, output, f'{label}-guest-actions', SLOTS + ', ' + ROOM_ACTIONS + ', [data-layout-region=preparation-recovery]',
                               ['slot-1', 'slot-2', 'readiness-actions', 'preparation-recovery', 'leave-actions'])
        slot[0].mark('member-joined')
        assert host.get_by_role('button', name='Start game', exact=True).is_disabled()
        guest_actions[0].allow_user_scroll(True)
        guest.get_by_role('button', name='Ready', exact=True).click()
        host.wait_for_function("() => document.querySelector('[data-slot-id=slot-2] [data-slot-region=status]')?.textContent?.includes('Ready')")
        guest.wait_for_timeout(80)
        guest_actions[0].allow_user_scroll(False)
        slot[0].mark('member-ready')
        guest_actions[0].mark('member-ready')
        for index in range(3, 6):
            additional = context.new_page()
            additional.goto(invite)
            additional.get_by_role('button', name='Join room', exact=True).click()
            additional.get_by_label('Room password').fill('blue-sky-room')
            additional.locator('.room-password-dialog').get_by_role('button', name='Join room', exact=True).click()
            additional.get_by_test_id('room-view').wait_for(state='attached')
            host.wait_for_function('count=>[...document.querySelectorAll("[data-testid=room-slot]")].filter(row=>row.querySelector("[data-slot-region=identity] span")?.textContent?.trim()).length===count', arg=index)
            slot[0].mark(f'{index}-occupied-slots')
        assert host.get_by_role('button', name='Copy invite', exact=True).count() == 0
        slot[0].allow_user_scroll(True)
        host.locator('[data-slot-id=slot-5] [data-manage-slot]').click()
        manage = host.get_by_role('dialog', name='Manage slot 5')
        manage.get_by_role('button', name='Remove member', exact=True).click()
        manage.get_by_role('button', name='Confirm removal', exact=True).click()
        host.get_by_role('button', name='Copy invite', exact=True).wait_for()
        slot[0].mark('final-slot-reopened')
        host.get_by_role('button', name='Leave room', exact=True).click()
        host.get_by_role('button', name='Stay in room', exact=True).wait_for()
        slot[0].mark('leave-confirmation')
        host.screenshot(path=str(output / f'{label}-leave-confirmation.png'))
        host.get_by_role('button', name='Stay in room', exact=True).click()
        host.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        slot[0].allow_user_scroll(False)
        slot[0].mark('stay-in-room')
        checks.append(finish(slot))

        guest.evaluate('layoutSockets.forEach(socket=>socket.close())')
        guest.get_by_role('button', name='Reconnect rooms', exact=True).wait_for()
        guest_actions[0].mark('connection-lost')
        guest_actions[0].allow_user_scroll(True)
        guest.get_by_role('button', name='Reconnect rooms', exact=True).scroll_into_view_if_needed()
        control_visibility(guest.get_by_role('button', name='Reconnect rooms', exact=True))
        guest.screenshot(path=str(output / f'{label}-connection-recovery.png'))
        guest.get_by_role('button', name='Reconnect rooms', exact=True).click()
        guest.get_by_role('button', name='Ready', exact=True).wait_for()
        guest.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        guest_actions[0].allow_user_scroll(False)
        guest_actions[0].mark('connection-restored')
        checks.append(finish(guest_actions))
        start = host.get_by_role('button', name='Start game', exact=True)
        start.scroll_into_view_if_needed()
        control_visibility(start)
        return checks
    finally:
        context.close()


def check_zoom_room(context, worker, host, url, output, label):
    host.get_by_role('button', name='Clear search', exact=True).click()
    host.get_by_role('button', name='Create game', exact=True).click()
    host.locator('input[type=file]').set_input_files(STATIC / 'generated/diagnostic.nes')
    host.get_by_label('Room access').select_option('protected')
    host.get_by_label('Room password').fill('blue-sky-room')
    host.get_by_role('button', name='Create room', exact=True).click()
    room = host.get_by_test_id('room-view')
    room.wait_for(state='attached')
    invite = room.get_attribute('data-invite')
    actions = record(host, output, f'{label}-zoom-200-room-actions', ROOM_ACTIONS + ', ' + SLOTS,
                     ['readiness-actions', 'start-actions', 'invite-actions', 'leave-actions', 'connection-recovery', 'slot-1', 'slot-2'])
    guest = context.new_page()
    guest.goto(f'{url}#invite={invite}')
    browser_zoom(guest, worker)
    guest.get_by_role('button', name='Join room', exact=True).click()
    guest.locator('.room-password-dialog').wait_for(state='visible')
    password = record(guest, output, f'{label}-zoom-200-password', PASSWORD,
                      ['room-password-dialog', 'password-join', 'password-back'])
    password[0].allow_user_scroll(True)
    guest.get_by_label('Room password').fill('wrong-password')
    guest.locator('.room-password-dialog').get_by_role('button', name='Join room', exact=True).click()
    guest.get_by_role('alert').get_by_text("Password didn't work. Try again.", exact=True).wait_for()
    guest.wait_for_timeout(80)
    password[0].allow_user_scroll(False)
    password[0].mark('wrong-password')
    result = [finish(password)]
    guest.get_by_label('Room password').fill('blue-sky-room')
    guest.locator('.room-password-dialog').get_by_role('button', name='Join room', exact=True).click()
    guest.get_by_test_id('room-view').wait_for(state='attached')
    actions[0].mark('member-joined')
    guest.get_by_role('button', name='Ready', exact=True).click()
    host.wait_for_function("() => document.querySelector('[data-slot-id=slot-2] [data-slot-region=status]')?.textContent?.includes('Ready')")
    actions[0].mark('member-ready')
    actions[0].allow_user_scroll(True)
    host.get_by_role('button', name='Leave room', exact=True).click()
    host.get_by_role('button', name='Stay in room', exact=True).wait_for()
    actions[0].mark('leave-confirmation')
    host.screenshot(path=str(output / f'{label}-zoom-200-leave-confirmation.png'))
    host.get_by_role('button', name='Stay in room', exact=True).click()
    host.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
    actions[0].allow_user_scroll(False)
    actions[0].mark('stay-in-room')
    result.append(finish(actions))
    guest.close()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                               env={**os.environ, 'COORDINATOR_EMPTY_OFFERS': 'super-tilt-bro-pal'},
                               stdout=subprocess.PIPE, text=True)
    try:
        assert service.stdout
        url = json.loads(service.stdout.readline())['url']
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                viewer = browser.new_page(viewport={'width': 1280, 'height': 800})
                viewer.goto(url)
                viewer.get_by_test_id('directory').wait_for()
                viewer.locator('[data-directory-status=live]').wait_for()
                directory = record(viewer, args.output, 'desktop-directory', DIRECTORY,
                                   ['directory-panel', 'directory-heading', 'directory-search', 'directory-feedback', 'directory-list', 'directory-actions', 'BUTTON'])
                results = check_profile(browser, url, args.output, 'desktop',
                                        {'width': 1280, 'height': 800}, (viewer, directory))
                results += check_profile(browser, url, args.output, 'mobile', {'width': 390, 'height': 700})
            finally:
                browser.close()
            # Real Chromium zoom also covers a mobile-width layout. A small
            # viewport alone would not exercise zoom and devicePixelRatio.
            zoom = []
            for label, backing in [('desktop', {'width': 1280, 'height': 800}),
                                   ('mobile', {'width': 780, 'height': 1400})]:
                with zoom_context(playwright, backing) as (context, worker):
                    page = context.pages[0]
                    page.goto(url)
                    page.get_by_test_id('directory').wait_for()
                    page.locator('[data-directory-status=live]').wait_for()
                    zoom.append(browser_zoom(page, worker))
                    page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                    directory = record(page, args.output, f'{label}-zoom-200-directory', DIRECTORY,
                                       ['directory-panel', 'directory-heading', 'directory-search', 'directory-feedback', 'directory-list', 'directory-actions', 'BUTTON'])
                    page.get_by_role('searchbox').fill('no-matching-room')
                    page.get_by_text('No matching public rooms.').wait_for()
                    directory[0].mark('empty-search')
                    results.append(finish(directory))
                    results += check_zoom_room(context, worker, page, url, args.output, label)
        print(json.dumps({'result': 'pass', 'zoom': zoom, 'checks': results}))
    finally:
        service.terminate()
        service.wait(timeout=10)


if __name__ == '__main__':
    main()
