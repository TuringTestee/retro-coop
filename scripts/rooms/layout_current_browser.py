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
PASSWORD = '.room-password-dialog, .room-password-dialog h3, .room-password-dialog [role=alert]'
DIRECTORY = '.directory-panel, .directory-title, .directory-search, .directory-feedback, .room-list, .pagination-region'


def record(page, output, label, selector, required):
    return GeometryRecorder(page, label, selector), output / f'{label}.json', required


def finish(check):
    recorder, path, required = check
    return recorder.finish(path, required=required)


def room_host(browser, url, viewport):
    context = browser.new_context(viewport=viewport, permissions=['clipboard-read', 'clipboard-write'])
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

        # Slot rows and their cells must keep their bounds when a member arrives,
        # changes readiness, and leaves. The host stays on the same room view.
        slot = record(host, output, f'{label}-slots', SLOTS,
                      ['slot-1', 'slot-2', 'slot-2/status'])
        guest = context.new_page()
        guest.goto(invite)
        guest.get_by_role('button', name='Join room', exact=True).click()
        dialog = guest.locator('.room-password-dialog')
        dialog.wait_for(state='visible')
        password = record(guest, output, f'{label}-password', PASSWORD,
                          ['room-password-dialog', 'H3', 'P'])
        guest.get_by_label('Room password').fill('wrong-password')
        guest.locator('.room-password-dialog').get_by_role('button', name='Join room', exact=True).click()
        guest.get_by_role('alert').get_by_text("Password didn't work. Try again.", exact=True).wait_for()
        password[0].mark('wrong-password')
        checks.append(finish(password))
        guest.get_by_label('Room password').fill('blue-sky-room')
        guest.locator('.room-password-dialog').get_by_role('button', name='Join room', exact=True).click()
        guest.get_by_test_id('room-view').wait_for(state='attached')
        slot[0].mark('member-joined')
        assert host.get_by_role('button', name='Start game', exact=True).is_disabled()
        guest.get_by_role('button', name='Ready', exact=True).click()
        host.wait_for_function("() => document.querySelector('[data-slot-id=slot-2] [data-slot-region=status]')?.textContent?.includes('Ready')")
        slot[0].mark('member-ready')
        checks.append(finish(slot))
        start = host.get_by_role('button', name='Start game', exact=True)
        start.scroll_into_view_if_needed()
        control_visibility(start)
        return checks
    finally:
        context.close()


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
                                   ['directory-panel', 'directory-title', 'directory-search', 'directory-feedback', 'room-list', 'pagination-region'])
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
                                       ['directory-panel', 'directory-title', 'directory-search', 'directory-feedback', 'room-list', 'pagination-region'])
                    page.get_by_role('searchbox').fill('no-matching-room')
                    page.get_by_text('No matching public rooms.').wait_for()
                    directory[0].mark('empty-search')
                    results.append(finish(directory))
        print(json.dumps({'result': 'pass', 'zoom': zoom, 'checks': results}))
    finally:
        service.terminate()
        service.wait(timeout=10)


if __name__ == '__main__':
    main()
