#!/usr/bin/env python3
"""Exercise fixed page navigation from the public room browser in Chromium."""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
from layout_geometry import GeometryRecorder, browser_zoom, control_visibility, verify_zoom, zoom_context

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


def settle_copy(page, index, success):
    page.evaluate('''async ({index,success})=>{
      const pending=window.pendingCopies[index];
      if(success)pending.resolve();else pending.reject(Error('Clipboard denied'));
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    }''', {'index': index, 'success': success})


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
            probe = browser.new_page()
            probe.set_content('<div class="scroll-owner" style="height:50px;overflow:auto"><div data-layout-region="scroll-sentinel" style="height:200px">Scroll sentinel</div></div>')
            scroll_check = GeometryRecorder(probe, 'unprompted-scroll-jump', '[data-layout-region=scroll-sentinel]')
            probe.evaluate("document.querySelector('.scroll-owner').scrollTop=30")
            try:
                scroll_check.finish(args.output / 'scroll-jump-rejection.json', required=('scroll-sentinel',))
            except AssertionError:
                rejection = json.loads((args.output / 'scroll-jump-rejection.json').read_text())
                assert any('scroll changed outside user-input interval' in failure for failure in rejection['failures']), rejection['failures']
            else:
                raise AssertionError('The geometry recorder accepted an unprompted scroll jump')
            probe.close()
            host = browser.new_page(viewport={'width': 1280, 'height': 720})
            errors = []
            host.on('pageerror', lambda error: errors.append(str(error)))
            host.goto(url)
            host.get_by_role('button', name='Settings', exact=True).click()
            host.wait_for_function("document.activeElement?.id === 'settings-title'")
            assert host.locator('dialog').count() == 0
            assert not host.locator('.directory-panel').is_visible()
            tool_proofs = []
            host.get_by_role('button', name='Restore keyboard defaults').scroll_into_view_if_needed()
            settings_layout = GeometryRecorder(host, 'settings-reset', '.tool-page [data-layout-region]')
            settings_layout.mark('idle')
            host.get_by_role('button', name='Restore keyboard defaults').click()
            settings_layout.mark('confirmation')
            host.keyboard.press('Escape')
            settings_layout.mark('dismissed')
            assert host.get_by_role('button', name='Keep mappings').count() == 0
            tool_proofs.append(settings_layout.finish(args.output / 'settings-reset-layout.json',
                                                     required=('tool-heading', 'tool-content', 'mapping-dialog')))
            host.screenshot(path=str(args.output / 'settings.png'))
            host.get_by_role('button', name='Local data', exact=True).click()
            host.wait_for_function("document.activeElement?.id === 'local-data-title'")
            host.get_by_role('button', name='Delete all local data').scroll_into_view_if_needed()
            local_data_layout = GeometryRecorder(host, 'local-data-confirmation', '.tool-page [data-layout-region]')
            local_data_layout.mark('idle')
            local_data_layout.allow_user_scroll()
            host.get_by_role('button', name='Delete all local data').click()
            host.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
            local_data_layout.allow_user_scroll(False)
            local_data_layout.mark('confirmation')
            local_data_layout.allow_user_scroll()
            host.keyboard.press('Escape')
            host.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
            local_data_layout.allow_user_scroll(False)
            local_data_layout.mark('dismissed')
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
            for action in ('Ready', 'Start game', 'Leave room'):
                control_visibility(host.get_by_role('button', name=action, exact=True))
            host.get_by_role('button', name='Ready', exact=True).click()
            start_style = host.get_by_role('button', name='Start game', exact=True).evaluate('node => getComputedStyle(node).backgroundColor')
            invite_style = host.get_by_role('button', name='Copy invite', exact=True).evaluate('node => getComputedStyle(node).backgroundColor')
            assert start_style == 'rgb(181, 163, 255)' and start_style != invite_style, (start_style, invite_style)
            for action in ('Not ready', 'Start game', 'Leave room'):
                control_visibility(host.get_by_role('button', name=action, exact=True))
            for slot in host.locator('.room-slots [data-slot-id]').all():
                control_visibility(slot)
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
            control_visibility(host.get_by_role('button', name='Players', exact=True))
            assert host.locator('.play-bindings').count() == 0
            assert host.get_by_role('button', name='Copy invite', exact=True).count() == 0
            host.screenshot(path=str(args.output / 'playing-wide.png'))
            host.get_by_role('button', name='Players', exact=True).click()
            host.locator('.room-slots').wait_for(state='visible')
            copy_invite = host.get_by_role('button', name='Copy invite', exact=True)
            control_visibility(copy_invite)
            copy_invite.click()
            host.wait_for_function("() => /Invitation copied|Copy unavailable/.test(document.querySelector('.room-invite')?.textContent || '')")
            control_visibility(copy_invite)
            host.get_by_role('button', name='Close players', exact=True).wait_for(state='visible')
            host.screenshot(path=str(args.output / 'playing-players-open.png'))
            host.get_by_role('button', name='Close players', exact=True).click()
            assert host.get_by_role('button', name='Copy invite', exact=True).count() == 0
            host.get_by_role('button', name='Players', exact=True).click()
            assert host.locator('.room-invite').get_by_role('status').count() == 0
            host.get_by_role('button', name='Close players', exact=True).click()
            host.wait_for_function("document.activeElement?.matches('[data-players-toggle]')")
            host.evaluate('''() => {
              window.pendingCopies=[];
              Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:()=>new Promise(
                (resolve,reject)=>window.pendingCopies.push({resolve,reject}))}});
            }''')
            for index, success in enumerate((True, False)):
                host.get_by_role('button', name='Players', exact=True).click()
                host.get_by_role('button', name='Copy invite', exact=True).click()
                host.wait_for_function('count=>window.pendingCopies.length===count', arg=index+1)
                host.get_by_role('button', name='Close players', exact=True).click()
                host.wait_for_function("document.activeElement?.matches('[data-players-toggle]')")
                host.get_by_role('button', name='Players', exact=True).click()
                settle_copy(host, index, success)
                assert host.locator('.room-invite').get_by_role('status').count() == 0
                assert host.get_by_label('Room invitation', exact=True).count() == 0
                host.get_by_role('button', name='Close players', exact=True).click()
            players_toggle = host.get_by_role('button', name='Players', exact=True)
            players_toggle.click()
            host.get_by_role('button', name='Copy invite', exact=True).wait_for(state='visible')
            players_toggle.focus()
            copy_state = host.locator('.room-invite').evaluate("node=>({html:node.outerHTML,visibility:getComputedStyle(node).visibility,display:getComputedStyle(node).display})")
            assert host.get_by_role('button', name='Copy invite', exact=True).count() == 1, copy_state
            focus_trail = []
            for _ in range(30):
                host.keyboard.press('Tab')
                focus_trail.append(host.evaluate("document.activeElement?.outerHTML?.slice(0,180)"))
                if host.evaluate("document.activeElement?.textContent?.trim()==='Copy invite'"):
                    break
            else:
                raise AssertionError(('Copy invite was not reachable by Tab from Players', copy_state, focus_trail))
            copy_invite = host.get_by_role('button', name='Copy invite', exact=True)
            control_visibility(copy_invite, require_focus=True)
            host.keyboard.press('Enter')
            host.wait_for_function('window.pendingCopies.length===3')
            settle_copy(host, 2, False)
            host.get_by_text('Copy unavailable. Select the invitation below.', exact=True).wait_for()
            fallback = host.get_by_label('Room invitation', exact=True)
            host.wait_for_function("document.activeElement?.getAttribute('aria-label')==='Room invitation'")
            control_visibility(fallback, require_focus=True)
            assert fallback.evaluate('element=>element.selectionStart===0&&element.selectionEnd===element.value.length')
            host.screenshot(path=str(args.output / 'playing-invite-keyboard-fallback.png'))
            host.get_by_role('button', name='Close players', exact=True).click()
            host.wait_for_function("document.activeElement?.matches('[data-players-toggle]')")
            host.get_by_role('button', name='Controls', exact=True).click()
            host.get_by_role('heading', name='Local settings', exact=True).wait_for(state='visible')
            host.locator('.mapping-list').wait_for(state='visible')
            host.screenshot(path=str(args.output / 'playing-controls-settings.png'))
            host.get_by_role('button', name='Back', exact=True).click()
            assert host.evaluate("document.activeElement?.textContent === 'Controls'")
            control_visibility(host.get_by_role('button', name='Controls', exact=True), require_focus=True)
            host.screenshot(path=str(args.output / 'playing-controls-return.png'))
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
                host.get_by_role('button', name='Tools', exact=True).click()
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
                if label == 'Rewind':
                    control_visibility(host.get_by_role('button', name='Rewind 1 second', exact=True))
                if label == 'Saves':
                    saves_layout = GeometryRecorder(host, 'save-feedback', '.tool-page [data-layout-region]')
                    saves_layout.mark('empty slot')
                    host.get_by_role('button', name='Save current point', exact=True).click()
                    host.get_by_text('Saved in Slot 1 on this device.', exact=True).wait_for()
                    saves_layout.mark('saved slot')
                    tool_proofs.append(saves_layout.finish(args.output / 'save-feedback-layout.json',
                                                          required=('tool-heading', 'tool-content', 'tool-list',
                                                                    'tool-status', 'tool-confirmation', 'tool-actions')))
                    delete_save = host.get_by_role('button', name='Delete Slot 1', exact=True)
                    delete_save.focus()
                    host.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                    control_visibility(delete_save, require_focus=True)
                if label == 'Game help':
                    host.get_by_text('Technical details', exact=True).scroll_into_view_if_needed()
                    help_layout = GeometryRecorder(host, 'help-details', '.tool-page [data-layout-region]')
                    help_layout.mark('closed')
                    host.get_by_text('Technical details', exact=True).click()
                    expected = hashlib.sha256((STATIC / 'generated/diagnostic.nes').read_bytes()).hexdigest()
                    assert expected in host.get_by_test_id('fingerprint').inner_text()
                    help_layout.mark('open')
                    tool_proofs.append(help_layout.finish(args.output / 'help-details-layout.json',
                                                         required=('tool-heading', 'tool-content')))
                host.screenshot(path=str(args.output / filename))
                host.get_by_role('button', name='Back', exact=True).click()
                host.wait_for_function("label => document.activeElement?.textContent === label", arg=label)
                assert host.locator('.panel').is_visible()
                host.screenshot(path=str(args.output / f'fullscreen-return-{slug}.png'))
            host = room_host
            local.close()
            host.get_by_role('button', name='Tools', exact=True).click()
            host.locator('.panel').get_by_role('button', name='Fullscreen', exact=True).click()
            host.wait_for_function('!!document.fullscreenElement')
            host.evaluate("()=>{window.savedExitFullscreen=document.exitFullscreen.bind(document);document.exitFullscreen=()=>Promise.reject(Error('Exit refused'));}")
            host.get_by_role('button', name='Tools', exact=True).click()
            host.locator('.panel').get_by_role('button', name='Saves', exact=True).click()
            host.get_by_text('Could not exit fullscreen. Press Esc, then try again.', exact=True).wait_for()
            assert host.evaluate('!!document.fullscreenElement') and host.locator('.tool-page:visible').count() == 0
            host.evaluate('()=>{document.exitFullscreen=window.savedExitFullscreen;}')
            # Headless Chromium does not route browser-level Escape to fullscreen.
            host.evaluate('()=>document.exitFullscreen()')
            host.wait_for_function('!document.fullscreenElement')
            host.get_by_role('button', name='Tools', exact=True).click()
            host.locator('.panel').get_by_role('button', name='Saves', exact=True).click()
            host.get_by_role('heading', name='Saves on this device', exact=True).wait_for(state='visible')
            host.get_by_role('button', name='Back', exact=True).click()
            host.wait_for_function("document.activeElement?.textContent === 'Saves'")
            assert host.get_by_text('Could not exit fullscreen. Press Esc, then try again.', exact=True).count() == 0
            if host.locator('.player-tools-back:visible').count():
                host.locator('.player-tools-back').click()
            host.set_viewport_size({'width': 390, 'height': 700})
            narrow = geometry(host, '390x700')
            control_visibility(host.get_by_role('button', name='Players', exact=True))
            assert host.get_by_role('button', name='Copy invite', exact=True).count() == 0
            host.screenshot(path=str(args.output / 'playing-narrow.png'), full_page=True)
            host.get_by_role('button', name='Players', exact=True).click()
            narrow_invite = host.get_by_role('button', name='Copy invite', exact=True)
            narrow_invite.scroll_into_view_if_needed()
            control_visibility(narrow_invite)
            host.screenshot(path=str(args.output / 'playing-narrow-invite.png'))
            narrow_invite.click()
            host.wait_for_function('window.pendingCopies.length===4')
            settle_copy(host, 3, False)
            host.get_by_text('Copy unavailable. Select the invitation below.', exact=True).wait_for()
            host.wait_for_function("document.activeElement?.getAttribute('aria-label')==='Room invitation'")
            control_visibility(host.get_by_label('Room invitation', exact=True), require_focus=True)
            host.screenshot(path=str(args.output / 'playing-narrow-invite-fallback.png'))
            host.get_by_role('button', name='Players', exact=True).click()
            host.set_viewport_size({'width': 640, 'height': 360})
            zoom = geometry(host, '640x360 (200% zoom equivalent)')
            host.screenshot(path=str(args.output / 'playing-zoom.png'), full_page=True)
            zoom_players = host.get_by_role('button', name='Players', exact=True)
            zoom_players.scroll_into_view_if_needed()
            control_visibility(zoom_players)
            assert host.get_by_role('button', name='Copy invite', exact=True).count() == 0
            zoom_players.click()
            zoom_invite = host.get_by_role('button', name='Copy invite', exact=True)
            zoom_invite.scroll_into_view_if_needed()
            control_visibility(zoom_invite)
            host.screenshot(path=str(args.output / 'playing-zoom-invite.png'))
            zoom_players.click()
            host.screenshot(path=str(args.output / 'playing-zoom-controls.png'), full_page=True)
            zoom_players.click()
            host.get_by_role('button', name='Copy invite', exact=True).click()
            host.wait_for_function('window.pendingCopies.length===5')
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
            assert host.get_by_role('button', name='Create room', exact=True).is_disabled(), 'Old room selection must not survive a fresh Create Game visit'
            assert host.get_by_role('button', name='Play locally', exact=True).is_hidden()
            with host.expect_file_chooser() as chooser:
                host.get_by_role('button', name='Add NES file', exact=True).click()
            chooser.value.set_files(STATIC / 'generated/diagnostic.nes')
            host.get_by_text('diagnostic.nes is loaded and ready.', exact=True).wait_for()
            host.get_by_role('button', name='Create room', exact=True).click()
            host.get_by_role('button', name='Start game', exact=True).wait_for(timeout=30000)
            settle_copy(host, 4, True)
            assert host.locator('.room-invite').get_by_role('status').count() == 0
            assert host.get_by_label('Room invitation', exact=True).count() == 0
            host.screenshot(path=str(args.output / 'new-room-no-old-copy-feedback.png'))
            with zoom_context(playwright, {'width': 1280, 'height': 800}) as (context, worker):
                zoom_page = context.new_page()
                zoom_page.on('pageerror', lambda error: errors.append(str(error)))
                zoom_page.goto(url)
                real_zoom = browser_zoom(zoom_page, worker, 2)
                zoom_page.get_by_role('button', name='Create game', exact=True).click()
                zoom_page.locator('input[type=file]').set_input_files(STATIC / 'generated/diagnostic.nes')
                zoom_page.get_by_role('button', name='Create room', exact=True).click()
                zoom_page.get_by_role('button', name='Ready', exact=True).click()
                zoom_page.get_by_role('button', name='Start game', exact=True).click()
                zoom_page.locator('main.playing.with-room').wait_for()
                players = zoom_page.get_by_role('button', name='Players', exact=True)
                players.focus()
                control_visibility(players, require_focus=True)
                zoom_page.keyboard.press('Enter')
                zoom_copy = zoom_page.get_by_role('button', name='Copy invite', exact=True)
                zoom_copy.wait_for(state='visible')
                zoom_focus_trail = []
                for _ in range(30):
                    zoom_page.keyboard.press('Tab')
                    zoom_focus_trail.append(zoom_page.evaluate("document.activeElement?.outerHTML?.slice(0,180)"))
                    if zoom_page.evaluate("document.activeElement?.textContent?.trim()==='Copy invite'"):
                        break
                else:
                    raise AssertionError(('Zoomed Copy invite was not reachable by Tab', zoom_focus_trail))
                control_visibility(zoom_copy, require_focus=True)
                zoom_page.evaluate('''() => Object.defineProperty(navigator,'clipboard',
                  {configurable:true,value:{writeText:()=>Promise.reject(Error('Clipboard denied'))}})''')
                zoom_page.keyboard.press('Enter')
                zoom_page.get_by_text('Copy unavailable. Select the invitation below.', exact=True).wait_for()
                zoom_fallback = zoom_page.get_by_label('Room invitation', exact=True)
                zoom_page.wait_for_function("document.activeElement?.getAttribute('aria-label')==='Room invitation'")
                control_visibility(zoom_fallback, require_focus=True)
                assert zoom_fallback.evaluate('element=>element.selectionStart===0&&element.selectionEnd===element.value.length')
                zoom_page.screenshot(path=str(args.output / 'playing-real-zoom-invite-fallback.png'))
                zoom_page.get_by_role('button', name='Close players', exact=True).click()
                zoom_page.wait_for_function("document.activeElement?.matches('[data-players-toggle]')")
                control_visibility(players, require_focus=True)
                assert zoom_page.get_by_role('button', name='Copy invite', exact=True).count() == 0
                zoom_page.screenshot(path=str(args.output / 'playing-real-zoom-return.png'))
                assert verify_zoom(worker, real_zoom) == 2
                zoom_page.get_by_role('button', name='Leave room', exact=True).click()
                zoom_page.get_by_role('button', name='Confirm leave', exact=True).click()
                zoom_page.get_by_test_id('directory').wait_for()
                zoom_page.close()
            service.terminate()
            host.get_by_role('button', name='Leave room', exact=True).click()
            host.get_by_role('button', name='Confirm leave', exact=True).click()
            host.locator('.room-confirm [role=alert]').wait_for(timeout=15000)
            assert host.locator('.release-notice').count() == 0
            host.screenshot(path=str(args.output / 'failed-close.png'), full_page=True)
            assert not errors, errors
            result = {'result': 'pass', 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                      'browser': browser.version, 'pages': ['Settings', 'Local data', 'Saves', 'Rewind', 'Game help', 'Invitation'],
                      'focus_return': True, 'fullscreen_tools': ['Saves', 'Rewind', 'Game help'], 'fullscreen_exit_failure': True,
                      'inline_confirmations': True, 'dialogs': 0, 'create_page_scroll': True,
                      'start_is_primary': True, 'voluntary_exit_clean': True, 'failed_close_has_retry': True,
                      'play_transitions': {'players_open': True, 'controls_settings': True,
                                           'controls_focus_return': True, 'narrow_players_visible': True,
                                           'zoom_players_visible_after_scroll': True,
                                           'copy_races_and_keyboard': True, 'real_zoom_invite': True},
                      'layout': [wide, narrow, zoom, real_zoom], 'tool_layout': tool_proofs,
                      'scroll_probe_rejected_jump': True, 'page_errors': errors}
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
