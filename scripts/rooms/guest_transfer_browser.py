#!/usr/bin/env python3
"""Exercise the public room guest download, retry, cache list, and deletion."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--url', required=True)
parser.add_argument('--fixture', type=Path, default=Path('spikes/d02/fixture.local.nes'))
args = parser.parse_args()
rom = args.fixture.read_bytes()

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    host_context = browser.new_context(viewport={'width': 1280, 'height': 800})
    guest_context = browser.new_context(viewport={'width': 800, 'height': 600})
    host = host_context.new_page()
    guest = guest_context.new_page()
    errors = []
    for page in (host, guest):
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(args.url)
    host.set_input_files('input[type=file]', {'name': 'diagnostic.nes', 'mimeType': 'application/octet-stream', 'buffer': rom})
    host.get_by_role('button', name='Start game', exact=True).wait_for(timeout=30000)
    code = host.locator('#room-heading').inner_text().split(' · ')[-1]
    guest.get_by_role('searchbox').fill(code)
    row = guest.locator('.room-list li').filter(has_text=code)
    assert 'Host-shared NES' in row.inner_text() and 'download' in row.inner_text()
    failed = {'once': False}
    def first_download(route):
        if not failed['once']:
            failed['once'] = True
            route.abort('failed')
        else:
            route.continue_()
    guest.route('**/rooms/*/rom', first_download)
    row.get_by_role('button', name='Join', exact=True).click()
    guest.get_by_role('button', name='Retry download', exact=True).wait_for(timeout=30000)
    assert guest.get_by_role('button', name='Prepare to play', exact=True).count() == 0
    host.get_by_text('Guest download failed.', exact=False).wait_for(timeout=15000)
    guest.get_by_role('button', name='Retry download', exact=True).click()
    guest.get_by_role('button', name='Prepare to play', exact=True).wait_for(timeout=30000)
    assert guest.get_by_role('button', name='Choose matching NES file').count() == 0
    guest.get_by_role('button', name='Prepare to play', exact=True).click()
    host.get_by_text('Guest is prepared.', exact=False).wait_for(timeout=15000)
    guest.get_by_role('button', name='Settings', exact=True).click()
    guest.get_by_role('button', name='Local data', exact=True).click()
    guest.get_by_role('heading', name='Downloaded games').wait_for()
    guest.get_by_role('button', name='Delete game', exact=True).focus()
    guest.keyboard.press('Enter')
    guest.get_by_role('button', name='Cancel', exact=True).click()
    guest.wait_for_function("document.activeElement?.textContent==='Delete game'")
    guest.keyboard.press('Enter')
    guest.get_by_role('button', name='Confirm', exact=True).focus()
    guest.keyboard.press('Enter')
    guest.get_by_text('No downloaded games saved in this browser.').wait_for()
    assert guest.get_by_role('button', name='Close local data').evaluate('(node)=>node===document.activeElement')
    guest.get_by_role('button', name='Delete all local data', exact=True).focus()
    guest.keyboard.press('Enter')
    guest.get_by_role('button', name='Confirm', exact=True).focus()
    guest.keyboard.press('Enter')
    guest.get_by_test_id('local-data-status').filter(has_text='Local data updated.').wait_for()
    assert guest.get_by_role('button', name='Delete all local data', exact=True).evaluate('(node)=>node===document.activeElement')
    assert guest.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth')
    guest.get_by_role('button', name='Close local data').click()
    guest.get_by_role('button', name='Close settings').click()
    guest.get_by_role('button', name='Leave room', exact=True).click()
    guest.get_by_test_id('directory').wait_for()
    assert guest.get_by_role('searchbox').evaluate('(node)=>node===document.activeElement')
    assert not errors, errors
    print(json.dumps({'result': 'pass', 'failed_download_retry': True, 'host_phase_failed': True,
                      'prepared_without_picker': True, 'individual_cache_deletion': True,
                      'keyboard_focus_after_single_and_all_deletion': True, 'narrow_width_no_overflow': True,
                      'leave_focus_search': True, 'page_errors': errors}))
    browser.close()
