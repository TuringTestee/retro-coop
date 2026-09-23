"""Prove a guest with a loaded ROM sees and can recover from solo release."""
import argparse
from hashlib import sha256
import json
import re
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
                    tab.add_init_script("window.RTCPeerConnection=class{constructor(){throw Error('Peer unavailable for release proof')}}")
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
            code = re.search(r"Public · (\S+)", host.get_by_test_id("room-view").text_content()).group(1)
            guest = page(block_peer=True)
            guest.locator(".room-list [data-room-id]").filter(has_text=code).get_by_role("button", name="Join", exact=True).click()
            guest.get_by_text("Game ready in this browser. Waiting for peer connection", exact=False).wait_for(timeout=30_000)
            assert guest.get_by_role("button", name="Prepare to play", exact=True).count() == 0
            assert guest.get_by_role("button", name="Choose matching NES file").count() == 0
            guest.wait_for_function("proof.room?.matches === true", timeout=30_000, polling=50)
            auth = guest.evaluate("""() => ({roomId:proof.room.id,membership:proof.room.chatMembership,token:sessionStorage.getItem('retro-coop-guest')})""")
            request = Request(f"{url}/coordinator/rooms/{auth['roomId']}/rom",headers={"Origin":url,"Authorization":f"Bearer {auth['token']}","X-Room-Membership":auth['membership']})
            with urlopen(request,timeout=5) as response:
                bytes_received=response.read()
                download={"status":response.status,"bytes":len(bytes_received),"sha256":sha256(bytes_received).hexdigest()}
            assert download == {"status": 200, "bytes": len(diagnostic), "sha256": sha256(diagnostic).hexdigest()}, download
            host.get_by_role("button", name="Start game", exact=True).click()
            host.wait_for_function("proof.room?.started === 'solo'", timeout=30_000, polling=50)
            host.get_by_test_id("player-status").filter(has_text="Playing locally. The game runs in this browser.").wait_for()
            notice = guest.get_by_role("alert").filter(has_text="The host started alone")
            notice.wait_for(timeout=30_000)
            resume = notice.get_by_role("button", name="Resume local game")
            assert resume.is_visible()
            guest.screenshot(path=str(args.output / "loaded-guest-solo-release.png"), full_page=True)
            resume.click()
            notice.wait_for(state="detached")
            guest.get_by_test_id("player-status").filter(has_text="Playing locally. The game runs in this browser.").wait_for(timeout=15_000)
            assert not errors, errors
            result = {"result": "pass", "source": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(), "browser": browser.version, "gateway_download": download, "journey": "automatically loaded guest -> peer unavailable -> host starts solo -> guest sees release -> resumes local game", "errors": errors}
            (args.output / "solo-release.json").write_text(json.dumps(result, indent=2) + "\n")
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
