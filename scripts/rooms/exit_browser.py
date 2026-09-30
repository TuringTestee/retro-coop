#!/usr/bin/env python3
"""Exercise directory exits through the public browser entry point."""
import json
import os
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(os.environ.get('RETRO_COOP_STATIC_ROOT', ROOT / 'apps/client/dist'))


def main():
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                               env={**os.environ, 'COORDINATOR_EMPTY_OFFERS': 'super-tilt-bro-pal'},
                               stdout=subprocess.PIPE, text=True)
    try:
        assert service.stdout
        url = json.loads(service.stdout.readline())['url']
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            def host_room():
                hosted = browser.new_page()
                hosted.add_init_script("""(() => {
                    window.exitProof = {terminated: 0, rejectedClose: 0};
                    const send = WebSocket.prototype.send;
                    WebSocket.prototype.send = function(data) {
                        if (window.failClose && JSON.parse(data).type === 'close') {
                            exitProof.rejectedClose++;
                            throw Error('Injected close failure');
                        }
                        return send.call(this, data);
                    };
                    const terminate = Worker.prototype.terminate;
                    Worker.prototype.terminate = function() {
                        exitProof.terminated++;
                        return terminate.call(this);
                    };
                })()""")
                hosted.goto(url)
                hosted.get_by_role('button', name='Create game', exact=True).click()
                hosted.locator('input[type=file]').set_input_files(STATIC / 'generated/diagnostic.nes')
                hosted.get_by_role('button', name='Create room', exact=True).click()
                hosted.get_by_test_id('room-view').wait_for(state='attached')
                return hosted
            page = host_room()
            page.get_by_role('button', name='Ready', exact=True).click()
            page.get_by_role('button', name='Start game', exact=True).click()
            page.wait_for_function("Number(document.querySelector('canvas').dataset.frameCount)>30")
            running_before = int(page.locator('canvas').get_attribute('data-frame-count'))
            page.get_by_role('button', name='Public rooms', exact=True).click()
            page.get_by_role('group', name='Confirm leave').wait_for()
            assert page.get_by_test_id('directory').count() == 0
            page.get_by_role('button', name='Stay in room', exact=True).click()
            assert page.locator('.room-panel').is_visible()
            page.get_by_role('button', name='Public rooms', exact=True).click()
            page.evaluate('window.failClose=true')
            page.get_by_role('button', name='Confirm leave', exact=True).click()
            page.get_by_role('alert').filter(has_text='Could not leave the room').wait_for()
            assert page.get_by_test_id('directory').count() == 0
            assert page.get_by_test_id('room-view').count() == 1
            page.wait_for_function("before=>Number(document.querySelector('canvas').dataset.frameCount)>before+20", arg=running_before)
            assert page.evaluate('exitProof.rejectedClose') == 1
            assert page.evaluate('exitProof.terminated') == 0
            page.evaluate('window.failClose=false')
            page.get_by_role('button', name='Confirm leave', exact=True).click()
            page.get_by_test_id('directory').wait_for()
            page.wait_for_function("!document.querySelector('[data-testid=room-view]') && !document.querySelector('.panel .controls button[aria-pressed]')")
            assert page.get_by_role('button', name='Resume local game', exact=True).count() == 0
            assert page.locator('canvas').get_attribute('data-frame-count') == '0'
            assert page.evaluate('exitProof.terminated') >= 1
            back = host_room()
            back.go_back()
            back.get_by_role('group', name='Confirm leave').wait_for()
            assert back.get_by_test_id('directory').count() == 0
            back.get_by_role('button', name='Confirm leave', exact=True).click()
            back.get_by_test_id('directory').wait_for()
            assert back.get_by_test_id('room-view').count() == 0
            invitation = host_room()
            invitation.evaluate("location.hash = '#invite=invalid-room'")
            invitation.get_by_role('group', name='Confirm leave').wait_for()
            invitation.get_by_role('button', name='Confirm leave', exact=True).click()
            invitation.get_by_test_id('directory').wait_for()
            assert invitation.get_by_test_id('room-view').count() == 0
            local = browser.new_page()
            local.goto(url)
            local.get_by_role('button', name='Create game', exact=True).click()
            local.locator('input[type=file]').set_input_files(STATIC / 'generated/diagnostic.nes')
            local.get_by_role('button', name='Play locally', exact=True).click()
            local.get_by_role('button', name='Resume', exact=True).wait_for()
            local.get_by_role('button', name='Public rooms', exact=True).click()
            local.get_by_test_id('directory').wait_for()
            assert local.get_by_role('button', name='Resume local game', exact=True).count() == 0
            assert local.evaluate("""() => {
                const canvas = document.querySelector('canvas');
                return [...canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data].every(value => value === 0);
            }""")
            browser.close()
        print(json.dumps({'host_close_before_directory': True, 'failed_close_keeps_playing': True, 'successful_close_terminates_worker': True, 'stay_retains_room': True, 'back_exits_room': True, 'invitation_exits_room': True, 'local_game_ends_before_directory': True}))
    finally:
        service.terminate()
        service.wait(timeout=10)


if __name__ == '__main__':
    main()
