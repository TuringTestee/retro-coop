#!/usr/bin/env python3
"""Check fixed waiting-room actions through file loading and slot management."""
import argparse
import json
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright
from layout_geometry import GeometryRecorder, browser_zoom, control_visibility, verify_zoom, zoom_context

ROOT = Path(__file__).resolve().parents[2]
ROM = ROOT / 'apps/client/dist/generated/diagnostic.nes'
REGIONS = ('.room-slots [data-slot-id], .room-slots [data-slot-region], '
           '[data-layout-region=readiness-actions], [data-layout-region=start-actions], '
           '[data-layout-region=invite-actions], [data-layout-region=leave-actions]')


def check(browser, url, output, label, viewport, zoom_worker=None):
    page = browser.new_page() if zoom_worker else browser.new_page(viewport=viewport)
    try:
        page.goto(url)
        zoom = browser_zoom(page, zoom_worker, 2) if zoom_worker else None
        page.get_by_role('button', name='Create game', exact=True).click()
        page.locator('input[type=file]').set_input_files(ROM)
        page.get_by_role('button', name='Create room', exact=True).click()
        page.get_by_test_id('room-view').wait_for(state='attached')
        room = GeometryRecorder(page, label, REGIONS)
        room.mark('waiting')

        page.evaluate('()=>{window.originalRead=FileReader.prototype.readAsArrayBuffer;FileReader.prototype.readAsArrayBuffer=function(){}}')
        page.locator('input[type=file]').set_input_files({
            'name': 'replacement.nes', 'mimeType': 'application/octet-stream',
            'buffer': ROM.read_bytes() + b'replacement'})
        cancel = page.get_by_role('button', name='Cancel loading', exact=True)
        cancel.wait_for(state='visible')
        room.mark('checking-file')
        room.allow_user_scroll(True)
        cancel.scroll_into_view_if_needed()
        control_visibility(cancel)
        page.screenshot(path=str(output / f'{label}-checking-file.png'))
        cancel.click()
        page.evaluate('()=>{FileReader.prototype.readAsArrayBuffer=window.originalRead}')
        page.get_by_role('button', name='Ready', exact=True).wait_for(state='visible')
        room.mark('cancelled-file')
        assert page.get_by_text('Waiting for you.', exact=True).count() == 1
        page.screenshot(path=str(output / f'{label}-cancelled-file.png'))

        manage = page.locator('[data-slot-id=slot-2] [data-manage-slot]')
        manage.click()
        dialog = page.get_by_role('dialog', name='Manage slot 2')
        before = dialog.bounding_box()
        dialog.get_by_role('button', name='Close slot', exact=True).click()
        dialog.get_by_role('button', name='Open slot', exact=True).wait_for(state='visible')
        after = dialog.bounding_box()
        assert before and after and all(abs(before[key] - after[key]) <= 1 for key in before), (before, after)
        page.screenshot(path=str(output / f'{label}-closed-slot.png'))
        modal_result = {'label': f'{label}-manage', 'before': before, 'after': after}
        dialog.get_by_role('button', name='Done', exact=True).click()
        assert manage.evaluate('node=>document.activeElement===node'), 'Manage focus did not return'
        control_visibility(manage, require_focus=True)
        page.screenshot(path=str(output / f'{label}-managed-slot.png'))
        room.allow_user_scroll(False)
        room.mark('managed-slot')
        room_result = room.finish(output / f'{label}-room.json', required=(
            'slot-1', 'slot-2', 'readiness-actions', 'start-actions', 'invite-actions', 'leave-actions'))

        page.get_by_role('button', name='Ready', exact=True).click()
        ready = page.get_by_role('button', name='Not ready', exact=True)
        ready.wait_for(state='visible')
        ready.focus()
        control_visibility(ready, require_focus=True)
        for action in ('Copy invite', 'Start game', 'Leave room'):
            page.keyboard.press('Tab')
            assert page.evaluate('document.activeElement?.textContent?.trim()') == action, (
                action, page.evaluate('document.activeElement?.outerHTML'))
            control_visibility(page.get_by_role('button', name=action, exact=True), require_focus=True)
        page.screenshot(path=str(output / f'{label}-keyboard-actions.png'))
        keyboard_manage = page.locator('[data-slot-id=slot-1] [data-manage-slot]')
        for _ in range(3):
            page.keyboard.press('Tab')
        control_visibility(keyboard_manage, require_focus=True)
        page.keyboard.press('Shift+Tab')
        assert page.locator('[data-slot-id=slot-1] [data-slot-region=status]').evaluate('node=>document.activeElement===node')
        page.keyboard.press('Tab')
        page.keyboard.press('Enter')
        page.get_by_role('dialog', name='Manage slot 1').wait_for(state='visible')
        page.keyboard.press('Escape')
        assert keyboard_manage.evaluate('node=>document.activeElement===node')
        control_visibility(keyboard_manage, require_focus=True)
        page.screenshot(path=str(output / f'{label}-keyboard-manage-return.png'))
        if zoom_worker:
            assert verify_zoom(zoom_worker, zoom) == 2
        keyboard_result = {'label': f'{label}-keyboard', 'tab_sequence':
            ['Not ready', 'Copy invite', 'Start game', 'Leave room', 'Slot 1 Manage'],
            'reverse_tab_and_dialog_focus_return': True, 'zoom': zoom}

        page.get_by_role('button', name='Start game', exact=True).click()
        page.locator('[data-layout-region=game-actions]').wait_for(state='visible')
        page.get_by_role('button', name='Pause', exact=True).wait_for(state='visible')
        playing = GeometryRecorder(page, f'{label}-playing',
                                   '.playing .screen, [data-layout-region=game-actions], '
                                   '[data-layout-region=shared-leave-actions]')
        playing.mark('playing')
        page.evaluate('()=>{window.originalRead=FileReader.prototype.readAsArrayBuffer;FileReader.prototype.readAsArrayBuffer=function(){}}')
        page.locator('input[type=file]').set_input_files({
            'name': 'replacement.nes', 'mimeType': 'application/octet-stream',
            'buffer': ROM.read_bytes() + b'replacement'})
        cancel = page.locator('[data-layout-region=player-primary-actions]').get_by_role(
            'button', name='Cancel loading', exact=True)
        cancel.wait_for(state='visible')
        playing.mark('checking-file')
        playing.allow_user_scroll(True)
        cancel.scroll_into_view_if_needed()
        control_visibility(cancel)
        page.screenshot(path=str(output / f'{label}-playing-checking.png'))
        cancel.click()
        page.evaluate('()=>{FileReader.prototype.readAsArrayBuffer=window.originalRead}')
        playing.allow_user_scroll(False)
        playing.mark('cancelled-file')
        playing_result = playing.finish(output / f'{label}-playing.json',
                                        required=('game-actions', 'shared-leave-actions'))
        return [room_result, modal_result, keyboard_result, playing_result]
    finally:
        page.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                               stdout=subprocess.PIPE, text=True)
    try:
        assert service.stdout
        url = json.loads(service.stdout.readline())['url']
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                results = []
                for label, viewport in [('desktop', {'width': 1280, 'height': 800}),
                                        ('short', {'width': 1024, 'height': 600}),
                                        ('narrow', {'width': 390, 'height': 700})]:
                    results.extend(check(browser, url, args.output, label, viewport))
            finally:
                browser.close()
            with zoom_context(playwright, {'width': 1280, 'height': 800}) as (context, worker):
                results.extend(check(context, url, args.output, 'zoom-200',
                                     {'width': 1280, 'height': 800}, worker))
        print(json.dumps({'result': 'pass', 'checks': results}))
    finally:
        service.terminate()
        service.wait(timeout=10)


if __name__ == '__main__':
    main()
