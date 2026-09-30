"""Prove a late disconnected observer cannot interrupt play and exits cleanly."""
import argparse
from hashlib import sha256
import json
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    service = subprocess.Popen(["node", "scripts/rooms/browser-server.ts"], cwd=root, stdout=subprocess.PIPE, text=True)
    try:
        assert service.stdout
        url = json.loads(service.stdout.readline())["url"]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            errors = []

            def page(block_peer=False):
                tab = browser.new_page(viewport={"width": 1280, "height": 800})
                tab.set_default_timeout(15_000)
                tab.on("pageerror", lambda error: errors.append(str(error)))
                if block_peer:
                    tab.add_init_script("window.RTCPeerConnection=class{constructor(){throw Error('Peer unavailable for observer isolation proof')}}")
                tab.add_init_script(path=root / "scripts/gameplay/fixture.js")
                tab.goto(url)
                tab.get_by_test_id("directory").wait_for()
                return tab

            diagnostic = (root / "spikes/d02/fixture.local.nes").read_bytes()
            host = page()
            host.get_by_role("button", name="Create game", exact=True).click()
            host.set_input_files("input[type=file]", {"name": "release-host.nes", "mimeType": "application/octet-stream", "buffer": diagnostic})
            host.get_by_role("button", name="Create room", exact=True).click()
            host.get_by_role("button", name="Start game", exact=True).wait_for(timeout=30_000)
            code = host.evaluate('proof.room.id')
            host.locator('[data-slot-id=slot-2] [data-manage-slot]').click()
            host.get_by_label('Slot 2 role', exact=True).select_option('observer')
            host.get_by_role('button', name='Done', exact=True).click()
            host.get_by_role('button', name='Ready', exact=True).click()
            host.get_by_role('button', name='Start game', exact=True).click()
            host.evaluate('releaseFrames()')
            host.wait_for_function('proof.frameCount>=30', polling=50)
            guest = page(block_peer=True)
            guest.locator(f'.room-list [data-room-id="{code}"]').get_by_role("button", name="Join", exact=True).click()
            try:
                guest.wait_for_function("proof.room?.slots.find(s=>s.member?.id===proof.room.chatMembership)?.member.acquisition==='loaded'", timeout=30_000, polling=50)
            except Exception:
                print(json.dumps(guest.evaluate('({room:proof.room,text:document.body.innerText})')),flush=True)
                raise
            assert guest.get_by_role("button", name="Observe game", exact=True).is_disabled()
            assert guest.get_by_role("button", name="Choose matching NES file").count() == 0
            guest.wait_for_function("proof.room?.matches === true", timeout=30_000, polling=50)
            auth = guest.evaluate("""() => ({roomId:proof.room.id,membership:proof.room.chatMembership,token:sessionStorage.getItem('retro-coop-guest')})""")
            request = Request(f"{url}/coordinator/rooms/{auth['roomId']}/rom",headers={"Origin":url,"Authorization":f"Bearer {auth['token']}","X-Room-Membership":auth['membership']})
            with urlopen(request,timeout=5) as response:
                bytes_received=response.read()
                download={"status":response.status,"bytes":len(bytes_received),"sha256":sha256(bytes_received).hexdigest()}
            assert download == {"status": 200, "bytes": len(diagnostic), "sha256": sha256(diagnostic).hexdigest()}, download
            guest.wait_for_function("proof.room?.slots.find(s=>s.member?.id===proof.room.chatMembership)?.role==='observer'", polling=50)
            host.wait_for_function("proof.room?.game.status==='playing'", timeout=30_000, polling=50)
            before = host.evaluate('proof.frameCount')
            host.wait_for_function('n=>proof.frameCount>=n+30', arg=before, timeout=15_000, polling=50)
            assert guest.evaluate('proof.room.id') == auth['roomId']
            assert guest.evaluate('proof.room.chatMembership') == auth['membership']
            guest.get_by_role('button', name='Players', exact=True).click()
            assert guest.get_by_test_id("room-slot").count() == 5
            guest.screenshot(path=str(args.output / "loaded-observer-connection-failed.png"), full_page=True)
            guest.get_by_role("button", name="Leave room", exact=True).click()
            if guest.get_by_role("button", name="Confirm leave", exact=True).is_visible():
                guest.get_by_role("button", name="Confirm leave", exact=True).click()
            guest.get_by_test_id("room-view").wait_for(state='detached')
            guest.get_by_test_id('directory').wait_for(state='visible')
            assert guest.locator('canvas').get_attribute('data-frame-count') == '0'
            assert guest.get_by_role('button', name='Resume local game', exact=True).count() == 0
            assert not errors, errors
            result = {"result": "pass", "source": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(), "browser": browser.version, "gateway_download": download, "journey": "host starts with everyone ready -> late observer cannot connect -> host keeps playing -> guest leaves and local game ends", "errors": errors}
            (args.output / "observer-isolation.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result, indent=2))
            browser.close()
    finally:
        service.terminate()
        try:
            service.wait(timeout=5)
        except subprocess.TimeoutExpired:
            service.kill()
            service.wait()


if __name__ == "__main__":
    main()
