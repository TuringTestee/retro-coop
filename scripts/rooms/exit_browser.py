#!/usr/bin/env python3
"""Exercise directory exits through the public browser entry point."""
import json
import os
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(os.environ.get('RETRO_COOP_STATIC_ROOT', ROOT / 'apps/client/dist'))
SCREENSHOTS = os.environ.get('RETRO_EXIT_SCREENSHOT_DIR')


def main():
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                               env={**os.environ, 'COORDINATOR_EMPTY_OFFERS': 'super-tilt-bro-pal'},
                               stdout=subprocess.PIPE, text=True)
    try:
        assert service.stdout
        url = json.loads(service.stdout.readline())['url']
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'])
            def host_room():
                hosted = browser.new_page()
                hosted.context.grant_permissions(['microphone'])
                hosted.add_init_script("""(() => {
                    window.exitProof = {terminated: 0, rejectedClose: 0, posted: 0, captures: [], audioSources: []};
                    const capture = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
                    navigator.mediaDevices.getUserMedia = async (...args) => {
                        const stream = await capture(...args);
                        exitProof.captures.push(stream);
                        return stream;
                    };
                    const createSource = AudioContext.prototype.createBufferSource;
                    AudioContext.prototype.createBufferSource = function(...args) {
                        const source = createSource.apply(this, args);
                        const record = {stopped: false, ended: false};
                        exitProof.audioSources.push(record);
                        source.addEventListener('ended', () => { record.ended = true; });
                        const stop = source.stop.bind(source);
                        source.stop = (...stopArgs) => { record.stopped = true; return stop(...stopArgs); };
                        return source;
                    };
                    const send = WebSocket.prototype.send;
                    WebSocket.prototype.send = function(data) {
                        if (window.failClose && JSON.parse(data).type === 'close') {
                            exitProof.rejectedClose++;
                            throw Error('Injected close failure');
                        }
                        return send.call(this, data);
                    };
                    const terminate = Worker.prototype.terminate;
                    const post = Worker.prototype.postMessage;
                    Worker.prototype.postMessage = function(...args) {
                        exitProof.posted++;
                        return post.apply(this, args);
                    };
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
            room_name = page.locator('#room-heading').inner_text()
            guest = browser.new_page()
            guest.goto(page.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite"))
            guest.get_by_role('button', name='Join room', exact=True).click()
            guest.get_by_role('button', name='Ready', exact=True).click()
            page.locator('[data-slot-id="slot-2"] [data-slot-region="status"]').get_by_text('Ready', exact=True).wait_for()
            page.get_by_role('button', name='Ready', exact=True).click()
            page.get_by_role('button', name='Start game', exact=True).click()
            page.wait_for_function("Number(document.querySelector('canvas').dataset.frameCount)>30")
            page.get_by_role('button', name='Unmute', exact=True).click()
            page.wait_for_function('exitProof.audioSources.length>0')
            page.get_by_role('button', name='Enable voice', exact=True).click()
            try:
                page.wait_for_function('exitProof.captures.length>0 && exitProof.captures.at(-1).getTracks().every(track=>track.readyState===\"live\")', timeout=7000)
            except Exception:
                raise AssertionError(f"Voice capture did not start: {page.locator('.voice-card').inner_text()} / {page.evaluate('exitProof.captures.length')}")
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
            assert page.evaluate('exitProof.captures.at(-1).getTracks().every(track=>track.readyState===\"live\")')
            if SCREENSHOTS:
                Path(SCREENSHOTS).mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(Path(SCREENSHOTS) / 'host-close-retry.png'), full_page=True)
            page.evaluate('window.failClose=false')
            page.get_by_role('button', name='Confirm leave', exact=True).click()
            page.get_by_test_id('directory').wait_for()
            page.wait_for_function("!document.querySelector('[data-testid=room-view]') && !document.querySelector('.panel .controls button[aria-pressed]')")
            assert page.get_by_role('button', name='Resume local game', exact=True).count() == 0
            assert page.get_by_text('Your local game is still available.', exact=False).count() == 0
            assert page.locator('canvas').get_attribute('data-frame-count') == '0'
            assert page.evaluate('exitProof.terminated') >= 1
            assert page.evaluate('exitProof.captures.every(stream=>stream.getTracks().every(track=>track.readyState===\"ended\"))')
            assert page.evaluate('exitProof.audioSources.length>0 && exitProof.audioSources.every(source=>source.stopped||source.ended)')
            posted = page.evaluate('exitProof.posted')
            sources = page.evaluate('exitProof.audioSources.length')
            page.locator('canvas').focus()
            page.keyboard.down('ArrowUp')
            time.sleep(0.25)
            page.keyboard.up('ArrowUp')
            assert page.evaluate('exitProof.posted') == posted
            assert page.evaluate('exitProof.audioSources.length') == sources
            if SCREENSHOTS:
                page.screenshot(path=str(Path(SCREENSHOTS) / 'public-rooms-after-exit.png'), full_page=True)
            guest.get_by_test_id('room-view').wait_for(state='detached')
            observer = browser.new_page()
            observer.goto(url)
            observer.locator('[data-directory-status=live]').wait_for()
            assert observer.locator('.room-list li').filter(has_text=room_name).count() == 0
            member_host = host_room()
            member = browser.new_page()
            member.add_init_script("""(() => {
                window.rejectedLeave = 0;
                const send = WebSocket.prototype.send;
                WebSocket.prototype.send = function(data) {
                    if (window.failLeave && JSON.parse(data).type === 'leave') {
                        rejectedLeave++;
                        throw Error('Injected leave failure');
                    }
                    return send.call(this, data);
                };
            })()""")
            member.goto(member_host.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite"))
            member.get_by_role('button', name='Join room', exact=True).click()
            member.get_by_role('button', name='Ready', exact=True).click()
            member_host.locator('[data-slot-id="slot-2"] [data-slot-region="status"]').get_by_text('Ready', exact=True).wait_for()
            member_host.get_by_role('button', name='Ready', exact=True).click()
            member_host.get_by_role('button', name='Start game', exact=True).click()
            member.get_by_role('button', name='Public rooms', exact=True).click()
            member.get_by_role('group', name='Confirm leave').wait_for()
            member.evaluate('window.failLeave=true')
            member.get_by_role('button', name='Confirm leave', exact=True).click()
            member.get_by_role('alert').filter(has_text='Could not leave the room').wait_for()
            assert member.get_by_test_id('directory').count() == 0
            assert member.get_by_test_id('room-view').count() == 1
            assert member.evaluate('rejectedLeave') == 1
            if SCREENSHOTS:
                member.screenshot(path=str(Path(SCREENSHOTS) / 'member-leave-retry.png'), full_page=True)
            member.evaluate('window.failLeave=false')
            member.get_by_role('button', name='Confirm leave', exact=True).click()
            member.get_by_test_id('directory').wait_for()
            member_host.get_by_role('button', name='Players', exact=True).click()
            member_host.locator('[data-slot-id="slot-2"] [data-slot-region="status"]').get_by_text('Open', exact=True).wait_for()
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
        print(json.dumps({'host_close_before_directory': True, 'failed_close_keeps_playing_and_voice': True, 'successful_close_terminates_worker': True, 'successful_close_stops_audio_voice_and_input': True, 'server_membership_released': True, 'member_failed_leave_retries': True, 'stay_retains_room': True, 'back_exits_room': True, 'invitation_exits_room': True, 'local_game_ends_before_directory': True}))
    finally:
        service.terminate()
        service.wait(timeout=10)


if __name__ == '__main__':
    main()
