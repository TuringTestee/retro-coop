#!/usr/bin/env python3
"""Exercise fixed page navigation from the public room browser in Chromium."""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
from layout_geometry import GeometryRecorder, control_visibility

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(os.environ.get('RETRO_COOP_STATIC_ROOT', ROOT / 'apps/client/dist'))


def geometry(page, label):
    canvas = page.locator('canvas').bounding_box()
    room = page.locator('.room-panel').bounding_box()
    assert canvas and room, (label, canvas, room)
    overlap = not (canvas['x'] + canvas['width'] <= room['x'] or room['x'] + room['width'] <= canvas['x']
                   or canvas['y'] + canvas['height'] <= room['y'] or room['y'] + room['height'] <= canvas['y'])
    assert not overlap, (label, canvas, room)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), label
    assert page.locator('.room-panel').evaluate("node => getComputedStyle(node).position !== 'fixed'"), label
    if room['y'] + room['height'] > page.viewport_size['height']:
        page.evaluate('window.scrollTo(0, document.documentElement.scrollHeight)')
        assert page.evaluate('window.scrollY > 0'), (label, 'room is below the viewport but the page cannot scroll')
        page.evaluate('window.scrollTo(0, 0)')
    return {'viewport': label, 'canvas': canvas, 'room': room}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                               env=os.environ.copy(), stdout=subprocess.PIPE, text=True)
    try:
        assert service.stdout
        url = json.loads(service.stdout.readline())['url']
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            host = browser.new_page(viewport={'width': 1280, 'height': 720})
            errors = []
            host.on('pageerror', lambda error: errors.append(str(error)))
            host.goto(url)
            host.get_by_role('button', name='Settings', exact=True).click()
            host.wait_for_function("document.activeElement?.id === 'settings-title'")
            assert host.locator('dialog').count() == 0
            assert not host.locator('.directory-panel').is_visible()
            tool_proofs = []
            settings_layout = GeometryRecorder(host, 'settings-reset', '.tool-page [data-layout-region]')
            settings_layout.mark('idle')
            settings_layout.allow_user_scroll()
            host.get_by_role('button', name='Restore keyboard defaults').click()
            settings_layout.mark('confirmation')
            host.keyboard.press('Escape')
            settings_layout.mark('dismissed')
            host.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
            settings_layout.allow_user_scroll(False)
            assert host.get_by_role('button', name='Keep mappings').count() == 0
            tool_proofs.append(settings_layout.finish(args.output / 'settings-reset-layout.json',
                                                     required=('tool-heading', 'tool-content', 'mapping-dialog')))
            host.screenshot(path=str(args.output / 'settings.png'))
            host.get_by_role('button', name='Local data', exact=True).click()
            host.wait_for_function("document.activeElement?.id === 'local-data-title'")
            local_data_layout = GeometryRecorder(host, 'local-data-confirmation', '.tool-page [data-layout-region]')
            local_data_layout.mark('idle')
            local_data_layout.allow_user_scroll()
            host.get_by_role('button', name='Delete all local data').click()
            local_data_layout.mark('confirmation')
            host.keyboard.press('Escape')
            local_data_layout.mark('dismissed')
            host.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
            local_data_layout.allow_user_scroll(False)
            assert host.get_by_role('button', name='Confirm', exact=True).count() == 0
            tool_proofs.append(local_data_layout.finish(args.output / 'local-data-confirmation-layout.json',
                                                       required=('tool-heading', 'tool-content', 'tool-status',
                                                                 'tool-confirmation', 'tool-list', 'tool-actions')))
            host.screenshot(path=str(args.output / 'local-data.png'))
            host.get_by_role('button', name='Back', exact=True).click()
            host.wait_for_function("document.activeElement?.textContent === 'Local data'")
            host.get_by_role('button', name='Back', exact=True).click()
            host.wait_for_function("document.activeElement?.textContent === 'Settings'")
            host.get_by_role('button', name='Create game', exact=True).click()
            host.set_viewport_size({'width': 390, 'height': 500})
            host.wait_for_function("document.querySelector('.create-game')?.scrollHeight > innerHeight")
            assert host.locator('.create-game').evaluate("node => getComputedStyle(node).overflowY === 'visible'"), host.locator('.create-game').evaluate("node => ({overflow:getComputedStyle(node).overflowY,parent:node.parentElement.className})")
            assert host.evaluate('document.documentElement.scrollWidth <= innerWidth')
            host.get_by_role('button', name='Create room', exact=True).scroll_into_view_if_needed()
            assert host.evaluate('window.scrollY > 0'), 'Create room should be reached by page scroll'
            host.screenshot(path=str(args.output / 'create-narrow.png'), full_page=True)
            host.set_viewport_size({'width': 1280, 'height': 720})
            host.locator('input[type=file]').set_input_files(STATIC / 'generated/diagnostic.nes')
            host.get_by_role('button', name='Create room', exact=True).click()
            host.get_by_role('button', name='Start game', exact=True).wait_for(timeout=30000)
            host.get_by_role('button', name='Ready', exact=True).click()
            start_style = host.get_by_role('button', name='Start game', exact=True).evaluate('node => getComputedStyle(node).backgroundColor')
            invite_style = host.get_by_role('button', name='Copy invite', exact=True).evaluate('node => getComputedStyle(node).backgroundColor')
            assert start_style == 'rgb(181, 163, 255)' and start_style != invite_style, (start_style, invite_style)
            invite = host.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite")
            host.screenshot(path=str(args.output / 'waiting.png'))
            host.get_by_text('Room settings', exact=True).click()
            host.get_by_role('button', name='Protect room', exact=True).click()
            host.get_by_label('New room password', exact=True).fill('stable pages passphrase')
            host.get_by_role('button', name='Protect room', exact=True).last.click()
            host.get_by_text('Room access: Password protected', exact=True).wait_for()
            host.get_by_role('button', name='Make public', exact=True).wait_for()
            assert host.locator('dialog').count() == 0
            host.get_by_role('button', name='Make public', exact=True).click()
            host.get_by_role('button', name='Confirm public access', exact=True).wait_for()
            host.keyboard.press('Escape')
            host.wait_for_function("document.activeElement?.matches('[data-make-public]')")
            host.get_by_role('button', name='Make public', exact=True).click()
            host.get_by_role('button', name='Confirm public access', exact=True).click()
            host.get_by_text('Room access: Public', exact=True).wait_for()
            host.get_by_text('Room settings', exact=True).click()
            guest = browser.new_page(viewport={'width': 390, 'height': 700})
            guest.on('pageerror', lambda error: errors.append(str(error)))
            guest.goto(invite)
            guest.get_by_role('button', name='Join room', exact=True).wait_for(timeout=15000)
            assert guest.locator('.room-panel').is_visible()
            assert guest.locator('.room-panel').evaluate("node => getComputedStyle(node).position !== 'fixed'")
            assert guest.evaluate('document.documentElement.scrollWidth <= innerWidth')
            guest.screenshot(path=str(args.output / 'invitation.png'), full_page=True)
            guest.close()
            if host.get_by_role('button', name='Ready', exact=True).count():
                host.get_by_role('button', name='Ready', exact=True).click()
            host.get_by_role('button', name='Start game', exact=True).click()
            host.locator('main.playing.with-room').wait_for(timeout=15000)
            wide = geometry(host, '1280x720')
            host.screenshot(path=str(args.output / 'playing-wide.png'))
            # A room always owns a shared timeline now. Rewind remains a local-play
            # tool; preserve its fullscreen/focus journey in an independent local tab.
            room_host = host
            local = browser.new_page(viewport={'width': 1280, 'height': 720})
            local.on('pageerror', lambda error: errors.append(str(error)))
            local.goto(url)
            local.get_by_role('button', name='Create game', exact=True).click()
            local.locator('input[type=file]').set_input_files(STATIC / 'generated/diagnostic.nes')
            local.get_by_role('button', name='Play locally', exact=True).click()
            local.get_by_role('button', name='Resume', exact=True).click()
            for label, heading, filename in [('Saves', 'Saves on this device', 'saves.png'),
                                             ('Rewind', 'Rewind local game', 'rewind.png'),
                                             ('Game help', 'Game help', 'help.png')]:
                host = local if label == 'Rewind' else room_host
                host.locator('.panel').get_by_role('button', name='Fullscreen', exact=True).click()
                host.wait_for_function('!!document.fullscreenElement')
                slug = label.lower().replace(' ', '-')
                host.screenshot(path=str(args.output / f'fullscreen-before-{slug}.png'))
                host.locator('.panel').get_by_role('button', name=label, exact=True).click()
                host.wait_for_function('!document.fullscreenElement')
                host.get_by_role('heading', name=heading, exact=True).wait_for(state='visible')
                host.wait_for_function("document.activeElement?.tagName === 'H2'")
                assert host.get_by_role('button', name='Back', exact=True).is_visible()
                assert not host.locator('.room-panel').is_visible()
                assert host.locator('dialog').count() == 0
                if label == 'Saves':
                    saves_layout = GeometryRecorder(host, 'save-feedback', '.tool-page [data-layout-region]')
                    saves_layout.mark('empty slot')
                    saves_layout.allow_user_scroll()
                    host.get_by_role('button', name='Save current point', exact=True).click()
                    host.get_by_text('Saved in Slot 1 on this device.', exact=True).wait_for()
                    saves_layout.mark('saved slot')
                    host.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                    saves_layout.allow_user_scroll(False)
                    tool_proofs.append(saves_layout.finish(args.output / 'save-feedback-layout.json',
                                                          required=('tool-heading', 'tool-content', 'tool-list',
                                                                    'tool-status', 'tool-confirmation', 'tool-actions')))
                    delete_save = host.get_by_role('button', name='Delete Slot 1', exact=True)
                    delete_save.focus()
                    host.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                    control_visibility(delete_save, require_focus=True)
                if label == 'Game help':
                    help_layout = GeometryRecorder(host, 'help-details', '.tool-page [data-layout-region]')
                    help_layout.mark('closed')
                    help_layout.allow_user_scroll()
                    host.get_by_text('Technical details', exact=True).click()
                    expected = hashlib.sha256((STATIC / 'generated/diagnostic.nes').read_bytes()).hexdigest()
                    assert expected in host.get_by_test_id('fingerprint').inner_text()
                    help_layout.mark('open')
                    host.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                    help_layout.allow_user_scroll(False)
                    tool_proofs.append(help_layout.finish(args.output / 'help-details-layout.json',
                                                         required=('tool-heading', 'tool-content')))
                host.screenshot(path=str(args.output / filename))
                host.get_by_role('button', name='Back', exact=True).click()
                host.wait_for_function("label => document.activeElement?.textContent === label", arg=label)
                assert host.locator('.panel').is_visible()
                host.screenshot(path=str(args.output / f'fullscreen-return-{slug}.png'))
            host = room_host
            local.close()
            host.locator('.panel').get_by_role('button', name='Fullscreen', exact=True).click()
            host.wait_for_function('!!document.fullscreenElement')
            host.evaluate("()=>{window.savedExitFullscreen=document.exitFullscreen.bind(document);document.exitFullscreen=()=>Promise.reject(Error('Exit refused'));}")
            host.locator('.panel').get_by_role('button', name='Saves', exact=True).click()
            host.get_by_text('Could not exit fullscreen. Press Esc, then try again.', exact=True).wait_for()
            assert host.evaluate('!!document.fullscreenElement') and host.locator('.tool-page:visible').count() == 0
            host.evaluate('()=>{document.exitFullscreen=window.savedExitFullscreen;}')
            # Headless Chromium does not route browser-level Escape to fullscreen.
            host.evaluate('()=>document.exitFullscreen()')
            host.wait_for_function('!document.fullscreenElement')
            host.locator('.panel').get_by_role('button', name='Saves', exact=True).click()
            host.get_by_role('heading', name='Saves on this device', exact=True).wait_for(state='visible')
            host.get_by_role('button', name='Back', exact=True).click()
            host.wait_for_function("document.activeElement?.textContent === 'Saves'")
            assert host.get_by_text('Could not exit fullscreen. Press Esc, then try again.', exact=True).count() == 0
            host.set_viewport_size({'width': 390, 'height': 700})
            narrow = geometry(host, '390x700')
            host.screenshot(path=str(args.output / 'playing-narrow.png'), full_page=True)
            host.set_viewport_size({'width': 640, 'height': 360})
            zoom = geometry(host, '640x360 (200% zoom equivalent)')
            host.screenshot(path=str(args.output / 'playing-zoom.png'), full_page=True)
            host.get_by_role('button', name='Leave room', exact=True).click()
            host.get_by_role('button', name='Confirm leave', exact=True).wait_for()
            assert host.locator('dialog').count() == 0
            host.keyboard.press('Escape')
            host.wait_for_function("document.activeElement?.matches('[data-leave-room]')")
            host.get_by_role('button', name='Leave room', exact=True).click()
            host.get_by_role('button', name='Confirm leave', exact=True).click()
            host.get_by_test_id('directory').wait_for(state='visible')
            assert host.locator('.release-notice').count() == 0
            host.wait_for_timeout(1000)
            assert host.locator('.release-notice').count() == 0
            assert host.get_by_test_id('included-status').count() == 0
            assert not host.locator('.room-panel').is_visible()
            assert host.get_by_role('button', name='Resume local game', exact=True).count() == 0
            host.screenshot(path=str(args.output / 'voluntary-exit.png'))
            host.set_viewport_size({'width': 1280, 'height': 720})
            host.get_by_role('button', name='Create game', exact=True).click()
            assert host.locator('.selected-game').evaluate("node => getComputedStyle(node).visibility === 'hidden'"), 'Old room selection must not survive a fresh Create Game visit'
            with host.expect_file_chooser() as chooser:
                host.get_by_role('button', name='Add NES file', exact=True).click()
            chooser.value.set_files(STATIC / 'generated/diagnostic.nes')
            host.get_by_text('diagnostic.nes is loaded and ready.', exact=True).wait_for()
            host.get_by_role('button', name='Create room', exact=True).click()
            host.get_by_role('button', name='Start game', exact=True).wait_for(timeout=30000)
            service.terminate()
            host.get_by_role('button', name='Leave room', exact=True).click()
            host.get_by_role('button', name='Confirm leave', exact=True).click()
            host.get_by_text('Could not leave the room. Retry or stay here.', exact=True).wait_for(timeout=15000)
            assert host.locator('.release-notice').count() == 0
            host.screenshot(path=str(args.output / 'failed-close.png'), full_page=True)
            assert not errors, errors
            result = {'result': 'pass', 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                      'browser': browser.version, 'pages': ['Settings', 'Local data', 'Saves', 'Rewind', 'Game help', 'Invitation'],
                      'focus_return': True, 'fullscreen_tools': ['Saves', 'Rewind', 'Game help'], 'fullscreen_exit_failure': True,
                      'inline_confirmations': True, 'dialogs': 0, 'create_page_scroll': True,
                      'start_is_primary': True, 'voluntary_exit_clean': True, 'failed_close_has_retry': True,
                      'layout': [wide, narrow, zoom], 'tool_layout': tool_proofs, 'page_errors': errors}
            (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result))
            browser.close()
    finally:
        service.terminate()
        try:
            service.wait(timeout=5)
        except subprocess.TimeoutExpired:
            service.kill()
            service.wait()


if __name__ == '__main__':
    main()
