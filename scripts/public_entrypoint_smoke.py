#!/usr/bin/env python3
"""Check that the documented command owns the current lobby-first application."""

import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def source_check():
    readme = (ROOT / "README.md").read_text()
    launcher = (ROOT / "scripts/demo.sh").read_text()
    assert "sh scripts/demo.sh" in readme
    assert "http://127.0.0.1:8765/" in readme
    assert "PUBLIC_CATALOG_GAMES=super-tilt-bro-pal,from-below-1.0" in launcher
    assert "COORDINATOR_EMPTY_OFFERS=super-tilt-bro-pal,from-below-1.0" in launcher
    assert "node apps/coordinator/src/main.ts" in launcher and "node ../../node_modules/vite/bin/vite.js" in launcher
    assert "spikes/d02" not in launcher and "/demo/" not in launcher
    for obsolete in ["index.html", "app.js", "style.css", "demo_smoke.py"]:
        assert not (ROOT / "spikes/d02/demo" / obsolete).exists(), obsolete
    for guide in ["d05-local-play.md", "d08-rooms.md", "d10-peer-connectivity.md"]:
        text = (ROOT / "docs/implementation" / guide).read_text()
        assert "sh scripts/demo.sh" in text


def fetch(url, method="GET"):
    with urlopen(Request(url, method=method), timeout=1) as response:
        return response.status, response.read()


def wait_closed(port):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)):
                return
        time.sleep(.05)
    raise AssertionError(f"port {port} remained open after the launcher exited")


def browser_check(screenshot_dir=None, url="http://127.0.0.1:8765/"):
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

    # Headless Chromium disables real background throttling. Clamp its window
    # timers to Chrome's documented background cadence while keeping audio worklet
    # callbacks live; the game must advance without relying on window timers.
    throttle_window = """() => {
      const timeout = window.setTimeout, interval = window.setInterval;
      window.setTimeout = (fn, ms, ...args) => timeout(fn, Math.max(ms ?? 0, 1000), ...args);
      window.setInterval = (fn, ms, ...args) => interval(fn, Math.max(ms ?? 0, 1000), ...args);
      window.requestAnimationFrame = () => 0;
    }"""
    hide_tab = """() => {
      Object.defineProperty(document, 'hidden', {configurable: true, value: true});
      window.dispatchEvent(new Event('blur'));
      document.dispatchEvent(new Event('visibilitychange'));
    }"""
    def prepared(member, host):
        try:
            member.get_by_role("button", name="Not ready", exact=True).wait_for(timeout=30000)
            host.locator("[data-slot-id=slot-2] [data-slot-region=status]").filter(has_text="Ready").wait_for(timeout=15000)
        except PlaywrightTimeoutError as error:
            state = [page.locator('.room-start, [data-slot-region=status], [data-testid=player-status], [data-testid=game-status]').all_text_contents() for page in (host, member)]
            raise AssertionError(f"Member preparation did not reach Ready: {state}") from error

    result = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        tabs = browser.new_context(viewport={"width": 1280, "height": 800})
        host = tabs.new_page()
        host.goto(url)
        host.get_by_role("button", name="Join as host").first.wait_for(timeout=15000)
        rows = host.locator(".room-list li")
        assert rows.filter(has_text="5 places open").count() == 2
        assert host.get_by_role("button", name="Create game", exact=True).count() == 1
        if screenshot_dir:
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            host.screenshot(path=str(screenshot_dir / "directory.png"))
        host.get_by_role("button", name="Join as host").first.click()
        host.get_by_role("button", name="Start game", exact=True).wait_for()
        host.get_by_role("button", name="Ready", exact=True).wait_for(timeout=30000)
        host.get_by_role("button", name="Ready", exact=True).click()
        host.get_by_role("button", name="Not ready", exact=True).wait_for(timeout=30000)
        assert host.get_by_test_id("room-slot").count() == 5
        assert "Player 1" in host.locator("[data-slot-id=slot-1]").inner_text()
        assert "Host" in host.locator("[data-slot-id=slot-1]").inner_text()
        assert host.get_by_role("button", name="Leave room", exact=True).count() == 1
        if screenshot_dir:
            host.set_viewport_size({"width": 1280, "height": 1100})
            host.evaluate("document.querySelector('.room-panel').scrollTop=0")
            host.screenshot(path=str(screenshot_dir / "waiting-room.png"), full_page=True)
            host.set_viewport_size({"width": 390, "height": 800})
            assert host.evaluate('document.documentElement.scrollWidth<=innerWidth')
            host.evaluate("document.querySelector('.room-panel').scrollTop=0")
            host.screenshot(path=str(screenshot_dir / "waiting-room-mobile.png"), full_page=True)
            host.set_viewport_size({"width": 1280, "height": 800})
        code = host.locator("#room-heading").inner_text()
        # Duplicating a browser tab copies sessionStorage. The new tab must get its
        # own guest identity instead of silently taking over the host connection.
        host_token = host.evaluate("sessionStorage.getItem('retro-coop-guest')")
        assert host_token
        # The source tab may be busy emulating. Its silence must not let a copy
        # reuse the host token and replace the original room connection.
        host.evaluate("setTimeout(() => { window.__busyStarted = true; const end = performance.now() + 3000; while (performance.now() < end) {} }, 0)")
        guest = tabs.new_page()
        guest.set_viewport_size({"width": 760, "height": 680})
        guest.add_init_script(f"sessionStorage.setItem('retro-coop-guest', {json.dumps(host_token)})")
        guest.goto(url)
        guest.get_by_role("button", name="Join as host").first.wait_for()
        guest.wait_for_function("old => sessionStorage.getItem('retro-coop-guest') !== old", arg=host_token)
        assert host.get_by_role("button", name="Start game", exact=True).is_enabled()
        result["duplicate_tab_gets_independent_guest_session"] = True
        guest.get_by_role("searchbox", name="Search room, game, host, or code").fill(code)
        target = guest.locator(".room-list li").filter(has_text=code).filter(has_text="4 places open")
        assert target.count() == 1 and "4 places open" in target.inner_text()
        target.get_by_role("button", name="Join", exact=True).click()
        guest.get_by_role("button", name="Leave room", exact=True).wait_for()
        guest.locator('details.chat-disclosure summary').click()
        host.locator('details.chat-disclosure summary').click()
        guest.get_by_label("Chat message").fill("Ready when you are")
        guest.get_by_role("button", name="Send message").click()
        host.get_by_text("Ready when you are", exact=True).wait_for(timeout=15000)
        guest.get_by_role("button", name="Ready", exact=True).click()
        prepared(guest, host)
        if screenshot_dir:
            guest.screenshot(path=str(screenshot_dir / "guest-ready.png"))
            host.screenshot(path=str(screenshot_dir / "host-ready.png"))
        result["duplicate_tab_guest_ready_visible_to_host"] = True
        result["included_claim_replenish_join_chat"] = True
        guest.get_by_role("button", name="Leave room", exact=True).click()
        guest.locator(".room-panel").wait_for(state="detached")
        guest.get_by_test_id("directory").wait_for(state="visible")
        host.get_by_role("button", name="Ready", exact=True).click()
        host.get_by_role("button", name="Start game", exact=True).click()
        host.wait_for_function("Number(document.querySelector('canvas').dataset.frameCount)>10", timeout=30000)
        assert host.locator('details.session-settings').count() == 0
        host.get_by_role("button", name="Players", exact=True).click()
        host.locator('details.session-settings').wait_for(state='visible')
        host.get_by_role("button", name="Close players", exact=True).click()
        result["host_start_solo_after_guest_left"] = True
        # One-member rooms use the shared timeline too. Leave explicitly to verify local playback.
        host.get_by_role("button", name="Leave room", exact=True).click()
        if screenshot_dir:
            host.screenshot(path=str(screenshot_dir / "confirm-leave.png"))
        host.get_by_role("button", name="Confirm leave", exact=True).click()
        host.get_by_test_id("room-view").wait_for(state="detached")
        host.get_by_role("button", name="Create game", exact=True).click()
        host.set_input_files("input[type=file]", ROOT / "apps/client/public/generated/diagnostic.nes")
        host.get_by_role("button", name="Play locally", exact=True).click()
        host.get_by_role("button", name="Resume", exact=True).click()
        solo_before = int(host.locator("canvas").get_attribute("data-frame-count").split(" ")[0])
        host.evaluate(throttle_window)
        assert not host.evaluate("document.hidden")
        host.wait_for_function("frames => Number(document.querySelector('canvas').dataset.frameCount)>frames+60", arg=solo_before, timeout=5000)
        occluded_before = int(host.locator("canvas").get_attribute("data-frame-count").split(" ")[0])
        host.evaluate(hide_tab)
        host.wait_for_function("frames => Number(document.querySelector('canvas').dataset.frameCount)>frames+60", arg=occluded_before, timeout=5000)
        assert int(host.locator('canvas').get_attribute('data-frame-count')) > occluded_before + 60
        result["tab_switch_keeps_local_play_running"] = True
        fixture = ROOT / "apps/client/public/generated/diagnostic.nes"
        custom = browser.new_page(viewport={"width": 1280, "height": 800})
        custom.goto(url)
        custom.get_by_role("button", name="Create game", exact=True).click()
        custom.get_by_label("Room access").select_option("protected")
        custom.get_by_label("Room password").fill("entrypoint-room-password")
        custom.set_input_files("input[type=file]", fixture)
        custom.get_by_role("button", name="Create room", exact=True).click()
        custom.get_by_role("button", name="Start game", exact=True).wait_for(timeout=15000)
        assert custom.get_by_test_id("room-view").count() == 1
        assert custom.get_by_role("button", name="Leave room", exact=True).count() == 1
        result["local_file_password_protected"] = True
        custom.get_by_role("button", name="Leave room", exact=True).click()
        custom.get_by_role("button", name="Confirm leave", exact=True).click()
        custom.locator(".room-panel").wait_for(state="detached")
        custom.get_by_test_id("directory").wait_for(state="visible")
        shared_host = browser.new_page()
        shared_host.goto(url)
        shared_host.get_by_role("button", name="Create game", exact=True).click()
        shared_host.set_input_files("input[type=file]", fixture)
        shared_host.get_by_role("button", name="Create room", exact=True).click()
        shared_host.get_by_role("button", name="Start game", exact=True).wait_for(timeout=15000)
        shared_code = shared_host.locator("#room-heading").inner_text()
        shared_guest = browser.new_page()
        shared_guest.goto(url)
        shared_guest.get_by_role("searchbox", name="Search room, game, host, or code").fill(shared_code)
        shared_row = shared_guest.locator(".room-list li").filter(has_text=shared_code).filter(has_text="4 places open")
        assert "4 places open" in shared_row.inner_text()
        file_choosers = []
        shared_guest.on("filechooser", lambda chooser: file_choosers.append(chooser))
        shared_row.get_by_role("button", name="Join", exact=True).click()
        shared_guest.get_by_role("button", name="Ready", exact=True).wait_for(timeout=30000)
        assert not file_choosers
        assert shared_guest.get_by_role("button", name="Choose matching NES file").count() == 0
        shared_guest.get_by_role("button", name="Ready", exact=True).click()
        prepared(shared_guest, shared_host)
        shared_host.get_by_role("button", name="Ready", exact=True).click()
        shared_guest.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, value: true}); window.dispatchEvent(new Event('blur')); document.dispatchEvent(new Event('visibilitychange'))")
        shared_host.get_by_role("button", name="Start game", exact=True).click()
        for tab in (shared_host, shared_guest):
            tab.wait_for_function("Number(document.querySelector('canvas')?.dataset.frameCount)>10", timeout=30000)
        before_switch = int(shared_host.locator("canvas").get_attribute("data-frame-count"))
        guest_before_switch = int(shared_guest.locator("canvas").get_attribute("data-frame-count"))
        shared_host.evaluate(throttle_window)
        shared_host.evaluate(hide_tab)
        for tab, before in ((shared_host, before_switch), (shared_guest, guest_before_switch)):
            tab.wait_for_function("frames => Number(document.querySelector('canvas')?.dataset.frameCount)>frames+60", arg=before, timeout=15000)
        result["local_file_public_discovery_and_shared_play"] = True
        result["tab_switch_keeps_shared_play_running"] = True
        failed_download = browser.new_page()
        failed_download.route("**/catalog/super-tilt-bro-*.nes", lambda route: route.abort())
        failed_download.goto(url)
        failed_download.get_by_role("searchbox", name="Search room, game, host, or code").fill("Super Tilt Bro")
        failed_download.get_by_role("button", name="Join as host").first.click()
        failed_download.get_by_test_id("included-status").filter(has_text="could not download. Retry download.").wait_for(timeout=15000)
        failed_download.get_by_role("button", name="Retry download").wait_for()
        assert failed_download.get_by_role("button", name="Choose local NES file").count() == 0
        if screenshot_dir:
            failed_download.screenshot(path=str(screenshot_dir / "included-download-failure.png"))
        failed_download.unroute("**/catalog/super-tilt-bro-*.nes")
        failed_download.get_by_role("button", name="Retry download").click()
        failed_download.get_by_role("button", name="Ready", exact=True).wait_for(timeout=30000)
        result["included_download_failure_and_retry"] = True
        claim_retry = browser.new_page(viewport={"width": 1280, "height": 1050})
        claim_retry.add_init_script("""(() => { const send = WebSocket.prototype.send;
          WebSocket.prototype.send = function(data) { const command = JSON.parse(data);
            if (command.type === 'claimCode' && !window.failedClaimInjected) {
              window.failedClaimInjected = true; command.code = 'ZZZZZZZZ';
              return send.call(this, JSON.stringify(command));
            }
            return send.call(this, data);
          };
        })();""")
        claim_retry.goto(url)
        claim_retry.get_by_role("button", name="Create game", exact=True).click()
        claim_retry.locator(".create-library li").filter(has_text="Super Tilt Bro").get_by_role("button").click()
        claim_retry.get_by_role("button", name="Create room", exact=True).wait_for()
        claim_retry.get_by_role("button", name="Create room", exact=True).click()
        claim_retry.get_by_text("Retry Create room or choose another game.", exact=False).wait_for(timeout=15000)
        assert claim_retry.evaluate("failedClaimInjected") and claim_retry.get_by_test_id("room-view").count() == 0
        assert claim_retry.get_by_text("Included offer ready:", exact=False).count() == 0
        assert claim_retry.get_by_role("button", name="Create room", exact=True).is_enabled()
        if screenshot_dir:
            claim_retry.screenshot(path=str(screenshot_dir / "included-claim-failure.png"), full_page=True)
        claim_retry.get_by_role("button", name="Create room", exact=True).click()
        claim_retry.get_by_role("button", name="Start game", exact=True).wait_for(timeout=15000)
        if screenshot_dir:
            claim_retry.screenshot(path=str(screenshot_dir / "included-claim-retry-success.png"), full_page=True)
        result["included_claim_failure_and_retry"] = True
        for mode in ("add", "drop"):
            changing = browser.new_page(viewport={"width": 1280, "height": 1050})
            changing.add_init_script("""(() => { const Native = WebSocket;
              window.WebSocket = class extends Native {
                set onmessage(handler) { super.onmessage = event => {
                  let message; try { message = JSON.parse(event.data); } catch {}
                  if (message?.type === 'result' && message.ok && message.data?.room?.role === 'host' && message.data.room.catalogId && !window.releaseClaim) {
                    window.heldInvite = message.data.room.invite;
                    window.releaseClaim = () => { handler(event); window.claimReleased = true; };
                  } else handler(event);
                }; }
              };
            })();""")
            changing.goto(url)
            changing.get_by_role("button", name="Create game", exact=True).click()
            changing.locator(".create-library li").filter(has_text="Super Tilt Bro").get_by_role("button").click()
            changing.get_by_role("button", name="Create room", exact=True).click()
            changing.wait_for_function("typeof releaseClaim === 'function'", timeout=15000)
            new_name = f"{mode}-new.nes"
            if mode == "add":
                with changing.expect_file_chooser() as chooser:
                    changing.get_by_role("button", name="Add NES file", exact=True).click()
                chooser.value.set_files({"name": new_name, "mimeType": "application/octet-stream", "buffer": fixture.read_bytes()})
            else:
                import base64
                changing.locator(".create-library").evaluate("(node, value) => { const bytes = Uint8Array.from(atob(value), char => char.charCodeAt(0)); const transfer = new DataTransfer(); transfer.items.add(new File([bytes], 'drop-new.nes', {type:'application/octet-stream'})); node.dispatchEvent(new DragEvent('drop', {bubbles:true,cancelable:true,dataTransfer:transfer})); }", base64.b64encode(fixture.read_bytes()).decode())
            changing.wait_for_function("name => document.querySelector('.create-library li button.selected strong')?.textContent === name && !document.querySelector('.create-actions button')?.disabled", arg=new_name, timeout=15000)
            if screenshot_dir and mode == "add":
                changing.screenshot(path=str(screenshot_dir / "claim-superseded-add.png"), full_page=True)
            if mode == "add":
                changing.get_by_role("button", name="Create room", exact=True).click()
                changing.get_by_role("button", name="Start game", exact=True).wait_for(timeout=15000)
                newer_invite = changing.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite")
                assert newer_invite != changing.evaluate("heldInvite")
            changing.evaluate("releaseClaim()")
            changing.wait_for_function("claimReleased")
            changing.wait_for_timeout(300)
            assert changing.locator('.release-notice').count() == 0
            if mode == "add":
                assert changing.get_by_test_id("room-view").count() == 1
                assert changing.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite") == newer_invite
                changing.get_by_role("button", name="Ready", exact=True).click()
                changing.get_by_role("button", name="Start game", exact=True).click()
                changing.get_by_role("button", name="Tools", exact=True).click()
                changing.get_by_role("button", name="Game help", exact=True).wait_for(timeout=15000)
                changing.get_by_role("button", name="Game help", exact=True).click()
                changing.get_by_text("Technical details", exact=True).click()
                assert __import__('hashlib').sha256(fixture.read_bytes()).hexdigest() in changing.get_by_test_id("fingerprint").text_content()
                changing.get_by_role("button", name="Back", exact=True).click()
            else:
                assert changing.get_by_test_id("room-view").count() == 0
                assert changing.get_by_test_id("create-game").is_visible()
                assert changing.locator(".create-library li button.selected strong").inner_text() == new_name
                if screenshot_dir:
                    changing.screenshot(path=str(screenshot_dir / "claim-superseded-drop.png"), full_page=True)
            observer = browser.new_page()
            observer.goto(url + "#invite=" + changing.evaluate("heldInvite"))
            observer.get_by_test_id("room-status").filter(has_text="closed, unavailable").wait_for(timeout=15000)
            observer.close()
            changing.close()
        result["included_claim_superseded_by_add_and_drop"] = True
        offline = browser.new_page()
        offline.add_init_script("""window.nativeRoomsSocket=WebSocket;
          window.WebSocket=function(){throw Error('Rooms temporarily offline')};""")
        offline.goto(url)
        offline.get_by_role("button", name="Create game", exact=True).click()
        offline.set_input_files("input[type=file]", fixture)
        offline.get_by_role("button", name="Create room", exact=True).click()
        offline.get_by_text("Rooms temporarily offline", exact=False).wait_for(timeout=15000)
        assert offline.get_by_role("button", name="Add NES file", exact=True).is_visible()
        offline.evaluate("()=>{window.WebSocket=window.nativeRoomsSocket}")
        offline.get_by_role("button", name="Create room", exact=True).click()
        offline.get_by_role("button", name="Start game", exact=True).wait_for(timeout=15000)
        result["room_creation_failure_and_retry"] = True
        recovering = browser.new_page(viewport={"width": 1280, "height": 1050})
        recovering.route("**/rooms/*/rom", lambda route: route.abort())
        recovering.goto(url)
        recovering.get_by_role("button", name="Create game", exact=True).click()
        recovering.set_input_files("input[type=file]", fixture)
        recovering.get_by_role("button", name="Create room", exact=True).click()
        feedback = recovering.locator('.create-options p[aria-live="polite"]')
        feedback.filter(has_text="Upload connection failed").wait_for(timeout=15000)
        assert recovering.get_by_test_id("room-view").count() == 0
        recovering.set_input_files("input[type=file]", {"name": "invalid-after-upload.nes", "mimeType": "application/octet-stream", "buffer": b"invalid"})
        feedback.filter(has_text="NES").wait_for(timeout=15000)
        assert "Upload connection failed" not in feedback.inner_text()
        assert recovering.get_by_test_id("room-view").count() == 0
        if screenshot_dir:
            recovering.screenshot(path=str(screenshot_dir / "upload-failure-new-invalid.png"), full_page=True)
        saved_hash = __import__('hashlib').sha256(fixture.read_bytes()).hexdigest()
        recovering.locator(".create-library li").filter(has_text=fixture.name).get_by_role("button").wait_for()
        recovering.evaluate("hash => new Promise((resolve, reject) => { const request = indexedDB.open('retro-coop-local'); request.onerror = () => reject(request.error); request.onsuccess = () => { const db = request.result; const tx = db.transaction('roms','readwrite'); tx.objectStore('roms').delete(hash); tx.oncomplete = () => { db.close(); resolve(); }; tx.onerror = () => reject(tx.error); }; })", saved_hash)
        recovering.locator(".create-library li").filter(has_text=fixture.name).get_by_role("button").click()
        feedback.filter(has_text="saved game is missing or damaged").wait_for(timeout=15000)
        assert "Upload connection failed" not in feedback.inner_text()
        assert recovering.get_by_test_id("room-view").count() == 0
        if screenshot_dir:
            recovering.screenshot(path=str(screenshot_dir / "upload-failure-missing-saved.png"), full_page=True)
        result["upload_failure_followed_by_new_selection_errors"] = True
        invalid = browser.new_page()
        invalid.goto(url)
        invalid.get_by_role("button", name="Create game", exact=True).click()
        invalid.set_input_files("input[type=file]", {"name": "bad.nes", "mimeType": "application/octet-stream", "buffer": b"invalid"})
        invalid.get_by_role("button", name="Add NES file", exact=True).wait_for()
        assert invalid.get_by_role("button", name="Create room", exact=True).is_disabled()
        result["invalid_file_recovery"] = True
        browser.close()
    return result

def occupied_port_check(environment):
    blockers = []
    for port in (8765, 8787):
        blocker = socket.socket()
        blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        blocker.bind(("127.0.0.1", port))
        blocker.listen()
        blockers.append(blocker)
    log_path = Path("/tmp/retro-coop-occupied-ports.log")
    service, log = start_launcher(environment, log_path)
    try:
        wait_ready(service, log_path, 8766)
        assert fetch("http://127.0.0.1:8788/health")[0] == 200
        assert "Open http://127.0.0.1:8766/" in log_path.read_text()
        stop_launcher(service, signal.SIGTERM, 8766, 8788)
    finally:
        log.close()
        if service.poll() is None:
            os.killpg(service.pid, signal.SIGKILL)
            service.wait()
        for blocker in blockers:
            blocker.close()
    return {"client": 8766, "coordinator": 8788}


def start_launcher(environment, log_path):
    log = log_path.open("w")
    service = subprocess.Popen(
        ["sh", "scripts/demo.sh"], cwd=ROOT, env=environment,
        stdout=log, stderr=subprocess.STDOUT, text=True, start_new_session=True,
    )
    return service, log


def wait_ready(service, log_path, client_port=8765):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if service.poll() is not None:
            raise AssertionError("Documented launcher exited early: " + log_path.read_text())
        try:
            if fetch(f"http://127.0.0.1:{client_port}/")[0] == 200 and f"Open http://127.0.0.1:{client_port}/" in log_path.read_text():
                return
        except OSError:
            time.sleep(.1)
    raise AssertionError("Documented application URL did not become ready: " + log_path.read_text())


def stop_launcher(service, signum, client_port=8765, coordinator_port=8787):
    service.send_signal(signum)
    try:
        return_code = service.wait(timeout=5)
    except subprocess.TimeoutExpired as error:
        os.killpg(service.pid, signal.SIGKILL)
        service.wait()
        raise AssertionError(f"launcher ignored signal {signum}") from error
    assert return_code in (-signum, 128 + signum), return_code
    wait_closed(client_port)
    wait_closed(coordinator_port)


def signal_lifecycle_check(environment):
    results = {}
    for name, signum in (("sigterm", signal.SIGTERM), ("ctrl_c", signal.SIGINT)):
        log_path = Path(f"/tmp/retro-coop-{name}.log")
        service, log = start_launcher(environment, log_path)
        try:
            wait_ready(service, log_path)
            stop_launcher(service, signum)
            results[name] = "ports released; immediate next launch allowed"
        finally:
            log.close()
            if service.poll() is None:
                os.killpg(service.pid, signal.SIGKILL)
                service.wait()
    return results


def runtime_check(with_browser=False, screenshot_dir=None):
    environment = dict(os.environ, RETRO_COOP_SKIP_INSTALL="1", RETRO_COOP_SKIP_PREPARE="1")
    fallback = occupied_port_check(environment)
    lifecycle = signal_lifecycle_check(environment)
    log_path = Path("/tmp/retro-coop-public-entrypoint.log")
    service, log = start_launcher(environment, log_path)
    result = None
    try:
        wait_ready(service, log_path)
        try:
            status, home = fetch("http://127.0.0.1:8765/")
            old_status, old_route = fetch("http://127.0.0.1:8765/demo/")
            coordinator_status, health = fetch("http://127.0.0.1:8787/health")
            source_status, source = fetch("http://127.0.0.1:8765/src/RoomPanel.tsx")
            catalog = {
                "super_tilt_bro": fetch("http://127.0.0.1:8765/catalog/super-tilt-bro-e-847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d.nes", "HEAD")[0],
                "from_below": fetch("http://127.0.0.1:8765/catalog/from-below-1.0-1a3ac4faf4b35640505344059ae5d91dae07cd47e1fb4d9d2a33c76391f1c555.nes", "HEAD")[0],
            }
            assert old_status == coordinator_status == source_status == 200
            assert b'/src/main.tsx' in home and b'/src/main.tsx' in old_route
            directory = (ROOT / "apps/client/src/DirectoryPanel.tsx").read_bytes()
            assert b"onCreate" in source and b"Create game" in directory and b"Join as host" in directory
            assert b"GOOD GAMES" not in old_route and b"Make yourself at home" not in old_route
            assert catalog == {"super_tilt_bro": 200, "from_below": 200}
            assert json.loads(health)["status"] == "ok"
            subprocess.run([
                "node", "--input-type=module", "-e",
                "import{WebSocket}from'ws';const w=new WebSocket('ws://127.0.0.1:8787/ws',{headers:{origin:'http://127.0.0.1:8765'}});w.on('open',()=>{w.close();process.exit(0)});w.on('error',e=>{console.error(e.message);process.exit(1)});setTimeout(()=>process.exit(2),3000)",
            ], cwd=ROOT, check=True, timeout=5)
            assert status == 200
            result = {"result": "pass", "url": "http://127.0.0.1:8765/",
                      "legacy_url_serves_current_app": True, "coordinator": "websocket accepted",
                      "catalog": catalog, "occupied_ports_select_next_available": fallback,
                      "launcher_signals": lifecycle}
            if with_browser:
                result["browser"] = browser_check(screenshot_dir)
        finally:
            if service.poll() is None:
                stop_launcher(service, signal.SIGTERM)
    finally:
        log.close()
        if service.poll() is None:
            os.killpg(service.pid, signal.SIGKILL)
            service.wait()
    assert result is not None
    return result


def main():
    global ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=ROOT)
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--screenshot-dir", type=Path)
    args = parser.parse_args()
    ROOT = args.runtime_root.resolve()
    source_check()
    result = {"result": "pass", "source_ownership": True}
    if not args.source_only:
        result.update(runtime_check(args.browser, args.screenshot_dir))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
