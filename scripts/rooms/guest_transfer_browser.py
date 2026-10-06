#!/usr/bin/env python3
"""Exercise guest game download recovery in the current lobby UI."""

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from ui_helpers import rename_lobby


def bounds(page):
    return page.evaluate("""() => Object.fromEntries([
      '.rc-shell','.rc-stage','.rc-players','.rc-game-zone','.rc-chat','.rc-footer'
    ].map(selector => {
      const rect = document.querySelector(selector).getBoundingClientRect();
      return [selector, [rect.x, rect.y, rect.width, rect.height]];
    }))""")


def same_bounds(before, after):
    assert all(all(abs(a - b) <= 1 for a, b in zip(rect, after[selector]))
               for selector, rect in before.items()), (before, after)


def browse_join(page, url):
    page.goto(url)
    page.locator('.rc-listing').wait_for()
    page.get_by_placeholder('Search lobbies').fill('Transfer Lab')
    card = page.locator('.rc-lobby-card').filter(has_text='Transfer Lab')
    card.wait_for(timeout=15000)
    card.click()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--fixture', type=Path, default=Path('spikes/d02/fixture.local.nes'))
    parser.add_argument('--rom-dir', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    rom = args.fixture.read_bytes()
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        host_context = browser.new_context(viewport={'width': 1280, 'height': 800})
        guest_context = browser.new_context(viewport={'width': 1024, 'height': 600})
        host = host_context.new_page()
        guest = guest_context.new_page()
        errors = []
        for page in (host, guest):
            page.on('pageerror', lambda error: errors.append(str(error)))

        host.goto(args.url)
        host.get_by_role('button', name='Host a new game').click()
        rename_lobby(host, 'Transfer Lab')
        host.get_by_role('button', name='Load NES game').wait_for(timeout=15000)
        host.locator('input[aria-label="NES cartridge file"]').set_input_files({
            'name': 'diagnostic.nes', 'mimeType': 'application/octet-stream', 'buffer': rom})
        host.get_by_role('button', name='Change game').wait_for(timeout=30000)
        assert host.get_by_role('button', name='Start →').count() == 0

        failed = [False]
        def first_download(route):
            if not failed[0]:
                failed[0] = True
                route.abort('failed')
            else:
                route.continue_()
        guest.route('**/rooms/*/rom', first_download)
        browse_join(guest, args.url)
        guest.get_by_role('button', name='Retry game').wait_for(timeout=30000)
        before = bounds(guest)
        expect(guest.get_by_role('button', name='Prepare', exact=True)).to_have_count(0)
        host.locator('[data-slot-id="slot-2"] .slot-state').get_by_text('Game failed').wait_for(timeout=15000)
        if args.output:
            guest.screenshot(path=str(args.output / 'guest-download-failed.png'))
        guest.get_by_role('button', name='Retry game').click()
        expect(guest.get_by_role('button', name='Prepare', exact=True)).to_be_enabled(timeout=30000)
        same_bounds(before, bounds(guest))
        guest.set_viewport_size({'width': 390, 'height': 700})
        assert guest.evaluate('document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight')
        if args.output:
            guest.screenshot(path=str(args.output / 'guest-game-ready.png'))
        guest.unroute('**/rooms/*/rom', first_download)

        guest.get_by_role('button', name='Back to Main Page').click()
        guest.get_by_role('button', name='Leave lobby').click()
        guest.locator('.rc-listing').wait_for(timeout=15000)
        cache_requests = []
        def reject_cached_network(route):
            cache_requests.append(route.request.url)
            route.abort('failed')
        guest.route('**/rooms/*/rom', reject_cached_network)
        browse_join(guest, args.url)
        expect(guest.get_by_role('button', name='Prepare', exact=True)).to_be_enabled(timeout=30000)
        assert not cache_requests, 'Rejoining downloaded instead of using verified browser bytes'
        guest.unroute('**/rooms/*/rom', reject_cached_network)

        altered = browser.new_page(viewport={'width': 1024, 'height': 600})
        damaged = bytearray(rom)
        damaged[-1] ^= 1
        altered.route('**/rooms/*/rom', lambda route: route.fulfill(
            status=200, content_type='application/octet-stream', body=bytes(damaged)))
        browse_join(altered, args.url)
        altered.get_by_role('button', name='Retry game').wait_for(timeout=30000)
        expect(altered.get_by_role('button', name='Prepare', exact=True)).to_have_count(0)
        assert 'did not match' in altered.locator('.rc-status').inner_text().lower()
        if args.output:
            altered.screenshot(path=str(args.output / 'altered-download-rejected.png'))
        altered.unroute('**/rooms/*/rom')
        altered.get_by_role('button', name='Retry game').click()
        altered.locator('.rc-preview img').wait_for(timeout=30000)
        assert altered.get_by_role('button', name='Retry game').count() == 0
        assert altered.get_by_role('button', name='Prepare', exact=True).count() == 0, \
            'A third participant observes this game and does not claim a controller.'

        if args.rom_dir:
            assert list(args.rom_dir.glob('blob-*')), 'Host upload did not create a private server blob'
        host.get_by_role('button', name='Back to Main Page').click()
        host.get_by_role('button', name='Close lobby').click()
        host.locator('.rc-listing').wait_for(timeout=15000)
        if args.rom_dir:
            assert not list(args.rom_dir.glob('blob-*')), 'Closing the lobby left a server ROM blob'
        assert not errors, errors
        result = {'result': 'pass', 'source_commit': subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], text=True).strip(),
            'seconds': round(time.monotonic() - started, 2),
            'failed_download_retry': True, 'host_sees_failed_preparation': True,
            'stable_regions_during_retry': True, 'narrow_width_no_overflow': True,
            'repeat_join_uses_verified_cache': True,
            'altered_bytes_rejected_then_retry': True,
            'room_close_removes_blob': bool(args.rom_dir), 'page_errors': errors}
        if args.output:
            (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        browser.close()


if __name__ == '__main__':
    main()
