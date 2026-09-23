"""Prove a public included-game host is discovered and joined through the directory."""
import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    started = time.monotonic()
    service = subprocess.Popen(
        ["node", "scripts/rooms/browser-server.ts"],
        cwd=root,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert service.stdout
        url = json.loads(service.stdout.readline())["url"]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", ignore_default_args=["--mute-audio"])
            errors, wire = [], []

            def page():
                tab = browser.new_page(viewport={"width": 1280, "height": 800})
                tab.set_default_timeout(15_000)
                tab.on("pageerror", lambda error: errors.append(str(error)))
                tab.on("websocket", lambda socket: socket.on("framesent", lambda raw: wire.append(raw)))
                tab.add_init_script(path=root / "scripts/gameplay/fixture.js")
                tab.goto(url)
                tab.get_by_test_id("directory").wait_for()
                return tab

            host = page()
            host.get_by_role("button", name="Play Super Tilt Bro", exact=True).click()
            host.get_by_role("button", name="Start game", exact=True).wait_for(timeout=30_000)
            host.get_by_role("button", name="Start game", exact=True).click()
            host.get_by_role("button", name="Copy invite", exact=True).wait_for()
            assert host.get_by_test_id("frames").inner_text() == "0 frames"
            host_room_text = host.get_by_test_id("room-view").text_content()
            code = re.search(r"Public · (\S+)", host_room_text).group(1)

            friend = page()
            row = friend.locator(".room-list [data-room-id]").filter(has_text=code)
            row.wait_for()
            room_id = row.get_attribute("data-room-id")
            assert row.locator("strong").inner_text() == "Super Tilt Bro"
            assert row.get_by_text("Included game", exact=True).is_visible()
            expected_host = row.locator("span").nth(1).inner_text()
            assert expected_host.strip()
            assert row.get_by_text("1/2 · waiting", exact=True).is_visible()
            join = row.get_by_role("button", name="Join", exact=True)
            assert join.is_enabled()
            directory_text = row.inner_text()
            friend.screenshot(path=str(args.output / "public-built-in-directory.png"), full_page=True)

            file_choosers = []
            friend.on("filechooser", lambda chooser: file_choosers.append(chooser))
            join.click()
            friend.get_by_test_id("room-view").wait_for(state="attached")
            host.wait_for_function("proof.room?.game?.ready?.includes('guest')", timeout=30_000, polling=50)
            host.locator(".room-start button").click()
            for tab in (host, friend):
                tab.wait_for_function(
                    "proof.room?.established && proof.room?.game?.status === 'playing'",
                    timeout=30_000,
                    polling=50,
                )
            assert not file_choosers, "The included-game join unexpectedly opened a ROM picker"
            assert friend.evaluate("proof.room.catalogId") == "super-tilt-bro-pal"
            assert friend.evaluate("proof.room.fingerprint.romSha256") == "847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d"

            for tab in (host, friend):
                tab.evaluate("releaseFrames()")
                tab.wait_for_function("proof.frameCount >= 360", timeout=30_000, polling=50)
            hashes = [tab.evaluate("proof.hashes.at(-1)") for tab in (host, friend)]
            assert hashes[0] and hashes[0] == hashes[1], hashes

            def layout(tab):
                result = tab.evaluate(
                    """()=>{const c=document.querySelector('canvas'),b=c.getBoundingClientRect();return {
                      viewport:{width:innerWidth,height:innerHeight},canvas:{width:b.width,height:b.height},
                      document:{width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight}
                    }}"""
                )
                assert result["document"]["width"] <= result["viewport"]["width"], result
                assert result["document"]["height"] <= result["viewport"]["height"], result
                assert result["canvas"]["height"] >= result["viewport"]["height"] * 0.68, result
                return result

            def overlay_layout(tab):
                result = tab.evaluate(
                    """()=>{const room=document.querySelector('.room-panel');return {
                      viewport:{width:innerWidth,height:innerHeight},
                      document:{width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight},
                      room:{scrollHeight:room.scrollHeight,clientHeight:room.clientHeight}
                    }}"""
                )
                assert result["document"] == result["viewport"], result
                assert result["room"]["scrollHeight"] <= result["room"]["clientHeight"], result
                return result

            layouts = [layout(tab) for tab in (host, friend)]
            friend.screenshot(path=str(args.output / "public-built-in-playing.png"), full_page=True)

            # Public arbitrary-ROM rooms reserve through the directory, then ask the guest
            # for the exact local file. Only fingerprints and room metadata cross the socket.
            diagnostic = (root / "apps/client/dist/generated/diagnostic.nes").read_bytes()
            arbitrary_host = page()
            arbitrary_host.set_input_files(
                "input[type=file]",
                {"name": "UJS7-HOST-PRIVATE.nes", "mimeType": "application/octet-stream", "buffer": diagnostic},
            )
            arbitrary_host.get_by_role("button", name="Start game", exact=True).wait_for(timeout=30_000)
            arbitrary_host.get_by_role("button", name="Start game", exact=True).click()
            arbitrary_host.get_by_role("button", name="Copy invite", exact=True).wait_for()
            arbitrary_text = arbitrary_host.get_by_test_id("room-view").text_content()
            arbitrary_code = re.search(r"Public · (\S+)", arbitrary_text).group(1)
            arbitrary_guest = page()
            arbitrary_row = arbitrary_guest.locator(".room-list [data-room-id]").filter(has_text=arbitrary_code)
            arbitrary_row.wait_for()
            assert arbitrary_row.get_by_text("Host-provided game", exact=True).is_visible()
            arbitrary_row.get_by_role("button", name="Join", exact=True).click()
            arbitrary_guest.get_by_text("needs your exact matching local NES file", exact=False).wait_for()
            assert arbitrary_guest.get_by_text("ROM bytes are never transferred", exact=False).is_visible()
            assert arbitrary_guest.get_by_role("button", name="Choose matching NES file", exact=True).is_visible()
            arbitrary_pending_layout = overlay_layout(arbitrary_guest)
            arbitrary_guest.screenshot(path=str(args.output / "public-arbitrary-match-required.png"), full_page=True)
            with arbitrary_guest.expect_file_chooser() as chooser_info:
                arbitrary_guest.get_by_role("button", name="Choose matching NES file", exact=True).click()
            chooser_info.value.set_files(
                {"name": "UJS7-GUEST-PRIVATE.nes", "mimeType": "application/octet-stream", "buffer": diagnostic}
            )
            arbitrary_host.wait_for_function("proof.room?.game?.ready?.includes('guest')", timeout=30_000, polling=50)
            arbitrary_host.locator(".room-start button").click()
            for tab in (arbitrary_host, arbitrary_guest):
                tab.wait_for_function("proof.room?.matches && proof.room?.established", timeout=30_000, polling=50)

            # An unlisted arbitrary room never enters a fresh directory, while its copied
            # invitation reaches the same exact-local-file admission step.
            unlisted_viewer = page()
            listed_before = unlisted_viewer.locator(".room-list [data-room-id]").evaluate_all("rows=>rows.map(row=>row.dataset.roomId)")
            unlisted_host = page()
            unlisted_host.get_by_label("Unlisted", exact=True).check()
            unlisted_host.set_input_files(
                "input[type=file]",
                {"name": "UJS7-UNLISTED-PRIVATE.nes", "mimeType": "application/octet-stream", "buffer": diagnostic},
            )
            unlisted_host.get_by_role("button", name="Start game", exact=True).wait_for(timeout=30_000)
            unlisted_host.get_by_role("button", name="Start game", exact=True).click()
            unlisted_host.get_by_role("button", name="Copy invite", exact=True).wait_for()
            assert unlisted_host.get_by_text("Unlisted lobby · invite only", exact=True).is_visible()
            unlisted_invite = unlisted_host.get_by_label("Room invitation", exact=True).input_value()
            unlisted_viewer.wait_for_timeout(300)
            listed_ids = unlisted_viewer.locator(".room-list [data-room-id]").evaluate_all("rows=>rows.map(row=>row.dataset.roomId)")
            assert listed_ids == listed_before
            unlisted_viewer.goto(unlisted_invite)
            unlisted_viewer.reload()
            unlisted_viewer.get_by_text("Bring your own matching local game file.", exact=False).wait_for()
            unlisted_viewer.get_by_role("button", name="Retry join / Join", exact=True).wait_for()
            unlisted_invitation_layout = overlay_layout(unlisted_viewer)
            unlisted_viewer.screenshot(path=str(args.output / "unlisted-invitation-entry.png"), full_page=True)
            unlisted_viewer.get_by_role("button", name="Retry join / Join", exact=True).click()
            unlisted_viewer.get_by_text("needs your exact matching local NES file", exact=False).wait_for()
            assert unlisted_viewer.get_by_text("ROM bytes are never transferred", exact=False).is_visible()
            with unlisted_viewer.expect_file_chooser() as chooser_info:
                unlisted_viewer.get_by_role("button", name="Choose matching NES file", exact=True).click()
            chooser_info.value.set_files(
                {"name": "UJS7-UNLISTED-GUEST.nes", "mimeType": "application/octet-stream", "buffer": diagnostic}
            )
            unlisted_host.wait_for_function("proof.room?.game?.ready?.includes('guest')", timeout=30_000, polling=50)
            unlisted_host.locator(".room-start button").click()
            for tab in (unlisted_host, unlisted_viewer):
                tab.wait_for_function("proof.room?.matches && proof.room?.established", timeout=30_000, polling=50)

            wire_text = "\n".join(frame if isinstance(frame, str) else str(frame) for frame in wire)
            assert "UJS7-" not in wire_text
            assert len(diagnostic) > max((len(frame) for frame in wire if isinstance(frame, str)), default=0)
            assert not errors, errors
            source = {
                key: subprocess.check_output(["git", "rev-parse", ref], cwd=root, text=True).strip()
                for key, ref in (("commit", "HEAD"), ("tree", "HEAD^{tree}"))
            }
            result = {
                "result": "pass",
                "source": source,
                "browser": browser.version,
                "journey": "public built-in host -> second-browser directory -> one Join -> shared play",
                "entry_route": "All public lobbies",
                "room_id": room_id,
                "directory_row": directory_text.splitlines(),
                "join_clicks": 1,
                "rom_picker_opened": False,
                "catalog_id": "super-tilt-bro-pal",
                "rom_sha256": friend.evaluate("proof.room.fingerprint.romSha256"),
                "synchronized_hash": hashes[0],
                "frames": [tab.evaluate("proof.frameCount") for tab in (host, friend)],
                "layouts": layouts,
                "arbitrary_public": {
                    "entry_route": "All public lobbies",
                    "source_label": "Host-provided game",
                    "exact_local_file_prompt": True,
                    "visible_file_action_opened_picker": True,
                    "matching_file_proceeded_to_shared_play": True,
                    "host_and_guest_filenames_absent_from_wire": True,
                    "rom_bytes_transferred": False,
                    "sha256": hashlib.sha256(diagnostic).hexdigest(),
                    "pending_layout": arbitrary_pending_layout,
                },
                "unlisted": {
                    "absent_from_directory": True,
                    "directory_room_ids_unchanged": listed_ids,
                    "invitation_entry": True,
                    "exact_local_file_prompt": True,
                    "visible_file_action_opened_picker": True,
                    "matching_file_proceeded_to_shared_play": True,
                    "invitation_layout": unlisted_invitation_layout,
                },
                "page_errors": errors,
                "duration_seconds": round(time.monotonic() - started, 2),
                "limits": "Local same-origin coordinator and two desktop Chrome pages; public-Internet routing is outside this journey proof.",
            }
            (args.output / "public-built-in-join.json").write_text(json.dumps(result, indent=2) + "\n")
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
