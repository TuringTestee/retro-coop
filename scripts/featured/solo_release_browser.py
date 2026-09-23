"""Prove a guest with a loaded ROM sees and can recover from solo release."""
import argparse
import json
import re
import subprocess
from pathlib import Path

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

            diagnostic = (root / "apps/client/dist/generated/diagnostic.nes").read_bytes()
            host = page()
            host.set_input_files("input[type=file]", {"name": "release-host.nes", "mimeType": "application/octet-stream", "buffer": diagnostic})
            host.get_by_role("button", name="Start game", exact=True).wait_for(timeout=30_000)
            code = re.search(r"Public · (\S+)", host.get_by_test_id("room-view").text_content()).group(1)
            guest = page(block_peer=True)
            guest.locator(".room-list [data-room-id]").filter(has_text=code).get_by_role("button", name="Join", exact=True).click()
            with guest.expect_file_chooser() as chooser:
                guest.get_by_role("button", name="Choose matching NES file", exact=True).click()
            chooser.value.set_files({"name": "release-guest.nes", "mimeType": "application/octet-stream", "buffer": diagnostic})
            guest.wait_for_function("proof.room?.matches === true", timeout=30_000, polling=50)
            guest.get_by_role("button", name="Resume", exact=True).wait_for(timeout=30_000)
            host.get_by_role("button", name="Start game", exact=True).click()
            host.locator(".room-start button").click()
            host.wait_for_function("proof.room?.started === 'solo'", timeout=30_000, polling=50)
            notice = guest.get_by_role("alert").filter(has_text="The host started alone")
            notice.wait_for(timeout=30_000)
            resume = notice.get_by_role("button", name="Resume local game")
            assert resume.is_visible()
            guest.screenshot(path=str(args.output / "loaded-guest-solo-release.png"), full_page=True)
            resume.click()
            notice.wait_for(state="detached")
            guest.wait_for_function("document.querySelector('[data-testid=player-status]')?.textContent?.includes('Playing locally')", timeout=15_000)
            assert not errors, errors
            result = {"result": "pass", "source": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(), "browser": browser.version, "journey": "loaded matching guest -> peer unavailable -> host starts solo -> guest sees release -> resumes local game", "errors": errors}
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
