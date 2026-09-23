#!/usr/bin/env python3
"""Exercise the public room guest download, retry, cache list, and deletion."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--url', required=True)
parser.add_argument('--fixture', type=Path, default=Path('spikes/d02/fixture.local.nes'))
parser.add_argument('--rom-dir', type=Path)
parser.add_argument('--output', type=Path)
args = parser.parse_args()
rom = args.fixture.read_bytes()
if args.output:
    args.output.mkdir(parents=True, exist_ok=True)

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
    host.get_by_role('button', name='Create game', exact=True).click()
    host.set_input_files('input[type=file]', {'name': 'diagnostic.nes', 'mimeType': 'application/octet-stream', 'buffer': rom})
    host.get_by_role('button', name='Create room', exact=True).click()
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
    if args.output:
        guest.screenshot(path=str(args.output / 'guest-download-failed.png'))
    assert guest.get_by_role('button', name='Prepare to play', exact=True).count() == 0
    host.get_by_text('Guest download failed.', exact=False).wait_for(timeout=15000)
    guest.get_by_role('button', name='Retry download', exact=True).click()
    guest.get_by_role('button', name='Prepare to play', exact=True).wait_for(timeout=30000)
    if args.output:
        guest.screenshot(path=str(args.output / 'guest-game-ready.png'))
    assert guest.get_by_role('button', name='Choose matching NES file').count() == 0
    guest.get_by_role('button', name='Prepare to play', exact=True).click()
    host.get_by_text('Guest is prepared.', exact=False).wait_for(timeout=15000)
    # A second admission of the same exact game must use verified browser bytes.
    guest.get_by_role('button', name='Leave room', exact=True).click()
    guest.get_by_test_id('directory').wait_for()
    guest.unroute('**/rooms/*/rom', first_download)
    cache_requests = []
    def reject_cached_network(route):
        cache_requests.append(route.request.url)
        route.abort('failed')
    guest.route('**/rooms/*/rom', reject_cached_network)
    guest.get_by_role('searchbox').fill(code)
    guest.locator('.room-list li').filter(has_text=code).get_by_role('button', name='Join', exact=True).click()
    guest.get_by_role('button', name='Prepare to play', exact=True).wait_for(timeout=30000)
    assert not cache_requests, 'Repeat join downloaded instead of reusing the verified game'
    guest.unroute('**/rooms/*/rom', reject_cached_network)
    guest.get_by_role('button', name='Prepare to play', exact=True).click()
    host.get_by_text('Guest is prepared.', exact=False).wait_for(timeout=15000)
    guest.get_by_role('button', name='Settings', exact=True).click()
    guest.get_by_role('button', name='Local data', exact=True).click()
    guest.get_by_role('heading', name='Saved games').wait_for()
    if args.output:
        guest.screenshot(path=str(args.output / 'saved-game-list.png'))
    guest.get_by_role('button', name='Delete game', exact=True).focus()
    guest.keyboard.press('Enter')
    guest.get_by_role('button', name='Cancel', exact=True).click()
    guest.wait_for_function("document.activeElement?.textContent==='Delete game'")
    guest.keyboard.press('Enter')
    guest.get_by_role('button', name='Confirm', exact=True).focus()
    guest.keyboard.press('Enter')
    guest.get_by_text('No games saved in this browser.').wait_for()
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
    # Clear in another tab while the download response is held. The current
    # browser may play verified memory bytes but must not recreate the cache.
    clearer = guest_context.new_page()
    clearer.goto(args.url)
    clearer.get_by_role('button', name='Settings', exact=True).click()
    clearer.get_by_role('button', name='Local data', exact=True).click()
    cleared = []
    def clear_during_download(route):
        clearer.get_by_role('button', name='Delete all local data', exact=True).click()
        clearer.get_by_role('button', name='Confirm', exact=True).click()
        clearer.get_by_test_id('local-data-status').filter(has_text='Local data updated.').wait_for()
        cleared.append(True)
        route.continue_()
    guest.route('**/rooms/*/rom', clear_during_download)
    guest.get_by_role('searchbox').fill(code)
    guest.locator('.room-list li').filter(has_text=code).get_by_role('button', name='Join', exact=True).click()
    guest.get_by_role('button', name='Prepare to play', exact=True).wait_for(timeout=30000)
    assert cleared, 'The cross-tab Clear did not race with the room download'
    assert 'download again next time' in guest.locator('.guest-acquisition').inner_text().lower()
    if args.output:
        guest.screenshot(path=str(args.output / 'cross-tab-clear-memory-only.png'))
    clearer.get_by_role('button', name='Close local data').click()
    clearer.get_by_role('button', name='Local data', exact=True).click()
    clearer.get_by_text('No games saved in this browser.').wait_for()
    guest.unroute('**/rooms/*/rom', clear_during_download)
    guest.get_by_role('button', name='Leave room', exact=True).click()
    guest.get_by_test_id('directory').wait_for()
    redownloads = []
    def count_redownload(route):
        redownloads.append(route.request.url)
        route.continue_()
    guest.route('**/rooms/*/rom', count_redownload)
    guest.get_by_role('searchbox').fill(code)
    guest.locator('.room-list li').filter(has_text=code).get_by_role('button', name='Join', exact=True).click()
    guest.get_by_role('button', name='Prepare to play', exact=True).wait_for(timeout=30000)
    assert len(redownloads) == 1, 'Join after cross-tab Clear did not fetch the game again'
    guest.unroute('**/rooms/*/rom', count_redownload)
    guest.get_by_role('button', name='Leave room', exact=True).click()
    guest.get_by_test_id('directory').wait_for()
    # Same-length altered bytes must never show Prepare or enter the cache.
    altered_context = browser.new_context(viewport={'width': 800, 'height': 600})
    altered = altered_context.new_page()
    altered.goto(args.url)
    damaged = bytearray(rom)
    damaged[-1] ^= 1
    def corrupt_download(route):
        route.fulfill(status=200, content_type='application/octet-stream', body=bytes(damaged))
    altered.route('**/rooms/*/rom', corrupt_download)
    altered.get_by_role('searchbox').fill(code)
    altered.locator('.room-list li').filter(has_text=code).get_by_role('button', name='Join', exact=True).click()
    altered.get_by_role('button', name='Retry download', exact=True).wait_for(timeout=30000)
    assert altered.get_by_role('button', name='Prepare to play', exact=True).count() == 0
    assert 'did not match' in altered.locator('.guest-acquisition').inner_text()
    if args.output:
        altered.screenshot(path=str(args.output / 'altered-download-rejected.png'))
    altered.unroute('**/rooms/*/rom', corrupt_download)
    altered.get_by_role('button', name='Retry download', exact=True).click()
    altered.get_by_role('button', name='Prepare to play', exact=True).wait_for(timeout=30000)
    altered.get_by_role('button', name='Leave room', exact=True).click()
    altered.get_by_test_id('directory').wait_for()
    # A denied reservation is a new admission journey, not a retry of its GET.
    expired_context = browser.new_context(viewport={'width': 800, 'height': 600})
    expired = expired_context.new_page()
    expired.goto(args.url)
    expired.route('**/rooms/*/rom', lambda route: route.fulfill(status=403, content_type='application/json', body='{"error":"reservation_expired"}'))
    expired.get_by_role('searchbox').fill(code)
    expired.locator('.room-list li').filter(has_text=code).get_by_role('button', name='Join', exact=True).click()
    expired.get_by_role('button', name='Return to rooms', exact=True).wait_for(timeout=30000)
    assert expired.get_by_role('button', name='Retry download', exact=True).count() == 0
    assert expired.get_by_role('button', name='Prepare to play', exact=True).count() == 0
    assert expired.get_by_role('button', name='Leave room', exact=True).count() == 0
    if args.output:
        expired.screenshot(path=str(args.output / 'reservation-expired.png'))
    expired.get_by_role('button', name='Return to rooms', exact=True).focus()
    expired.keyboard.press('Enter')
    expired.get_by_test_id('directory').wait_for()
    assert expired.get_by_role('searchbox').evaluate('(node)=>node===document.activeElement')
    # A denied IndexedDB write must leave verified bytes playable for this tab.
    quota_context = browser.new_context(viewport={'width': 1280, 'height': 800})
    quota_context.add_init_script("""(() => {
      const original = IDBDatabase.prototype.transaction;
      IDBDatabase.prototype.transaction = function(names, mode, ...rest) {
        if (mode === 'readwrite' && (Array.isArray(names) ? names : [names]).includes('roms'))
          throw new DOMException('Storage full', 'QuotaExceededError');
        return original.call(this, names, mode, ...rest);
      };
    })();""")
    quota_guest = quota_context.new_page()
    quota_guest.goto(args.url)
    quota_guest.get_by_role('searchbox').fill(code)
    quota_guest.locator('.room-list li').filter(has_text=code).get_by_role('button', name='Join', exact=True).click()
    quota_guest.get_by_role('button', name='Prepare to play', exact=True).wait_for(timeout=30000)
    assert 'download again next time' in quota_guest.locator('.guest-acquisition').inner_text().lower()
    if args.output:
        quota_guest.screenshot(path=str(args.output / 'storage-full-memory-only.png'))
    quota_guest.get_by_role('button', name='Prepare to play', exact=True).click()
    host.get_by_text('Guest is prepared.', exact=False).wait_for(timeout=15000)
    quota_guest.get_by_role('button', name='Leave room', exact=True).click()
    quota_guest.get_by_test_id('directory').wait_for()
    if args.rom_dir:
        assert list(args.rom_dir.glob('blob-*')), 'Host upload did not create a private server blob'
    host.on('dialog', lambda dialog: dialog.accept())
    host.get_by_role('button', name='Leave room', exact=True).click()
    host.get_by_test_id('directory').wait_for()
    if args.rom_dir:
        assert not list(args.rom_dir.glob('blob-*')), 'Closing the room left a server ROM blob'
    assert not errors, errors
    result = {'result': 'pass', 'failed_download_retry': True, 'host_phase_failed': True,
                      'prepared_without_picker': True, 'individual_cache_deletion': True,
                      'repeat_join_uses_cache_without_get': True, 'cross_tab_clear_keeps_memory_only': True,
                      'join_after_clear_redownloads': len(redownloads) == 1,
                      'altered_bytes_rejected_then_retry': True, 'expired_reservation_returns_to_rooms': True,
                      'quota_denied_plays_in_memory': True, 'room_close_removes_blob': bool(args.rom_dir),
                      'keyboard_focus_after_single_and_all_deletion': True, 'narrow_width_no_overflow': True,
                      'leave_focus_search': True, 'page_errors': errors}
    if args.output:
        (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    browser.close()
