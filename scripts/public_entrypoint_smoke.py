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
    from playwright.sync_api import sync_playwright

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
    result = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        tabs = browser.new_context(viewport={"width": 1280, "height": 800})
        host = tabs.new_page()
        host.goto(url)
        host.get_by_role("button", name="Join as host").first.wait_for(timeout=15000)
        rows = host.locator(".room-list li")
        assert rows.filter(has_text="0/2 · Waiting for host").count() == 2
        assert host.get_by_role("button", name="Choose NES file", exact=True).count() == 1
        if screenshot_dir:
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            host.screenshot(path=str(screenshot_dir / "directory.png"))
        host.get_by_role("button", name="Join as host").first.click()
        host.get_by_role("button", name="Start game", exact=True).wait_for()
        host.wait_for_function("!document.querySelector('.room-start button').disabled", timeout=30000)
        assert "Player 1 · Host" in host.locator(".room-slots").inner_text()
        assert host.get_by_role("button", name="Leave room", exact=True).count() == 1
        if screenshot_dir:
            host.screenshot(path=str(screenshot_dir / "waiting-room.png"))
        code = host.locator("#room-heading").inner_text().split(" · ")[-1]
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
        target = guest.locator(".room-list li").filter(has_text=code)
        assert target.count() == 1 and "1/2 · Waiting for guest" in target.inner_text()
        target.get_by_role("button", name="Join", exact=True).click()
        guest.get_by_role("button", name="Leave room", exact=True).wait_for()
        guest.get_by_label("Chat message").fill("Ready when you are")
        guest.get_by_role("button", name="Send message").click()
        host.get_by_text("Ready when you are", exact=True).wait_for(timeout=15000)
        guest.get_by_role("button", name="Prepare to play", exact=True).click()
        guest.get_by_text("Ready to play. Waiting for the host to start.", exact=True).wait_for(timeout=30000)
        host.get_by_text("Guest is prepared. Start together when you are ready.", exact=True).wait_for(timeout=30000)
        if screenshot_dir:
            guest.screenshot(path=str(screenshot_dir / "guest-ready.png"))
            host.screenshot(path=str(screenshot_dir / "host-ready.png"))
        result["duplicate_tab_guest_ready_visible_to_host"] = True
        result["included_claim_replenish_join_chat"] = True
        guest.get_by_role("button", name="Leave room", exact=True).click()
        guest.locator(".room-panel").wait_for(state="detached")
        assert guest.get_by_test_id("directory").is_visible()
        host.get_by_role("button", name="Start game", exact=True).click()
        host.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>10", timeout=30000)
        result["host_start_solo_after_guest_left"] = True
        solo_before = int(host.get_by_test_id("frames").inner_text().split(" ")[0])
        host.evaluate(throttle_window)
        assert not host.evaluate("document.hidden")
        host.wait_for_function("frames => Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>frames+60", arg=solo_before, timeout=5000)
        occluded_before = int(host.get_by_test_id("frames").inner_text().split(" ")[0])
        host.evaluate(hide_tab)
        host.wait_for_function("frames => Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>frames+60", arg=occluded_before, timeout=5000)
        assert host.get_by_test_id("player-status").inner_text().startswith("Playing locally")
        result["tab_switch_keeps_local_play_running"] = True
        fixture = ROOT / "apps/client/public/generated/diagnostic.nes"
        custom = browser.new_page(viewport={"width": 1280, "height": 800})
        custom.goto(url)
        custom.get_by_label("Room access").select_option("unlisted")
        custom.set_input_files("input[type=file]", fixture)
        custom.get_by_role("button", name="Start game", exact=True).wait_for(timeout=15000)
        assert "Unlisted" in custom.locator("#room-heading").inner_text()
        assert custom.get_by_role("button", name="Leave room", exact=True).count() == 1
        result["local_file_unlisted"] = True
        custom.on("dialog", lambda dialog: dialog.accept())
        custom.get_by_role("button", name="Leave room", exact=True).click()
        custom.locator(".room-panel").wait_for(state="detached")
        assert custom.get_by_test_id("directory").is_visible()
        shared_host = browser.new_page()
        shared_host.goto(url)
        shared_host.set_input_files("input[type=file]", fixture)
        shared_host.get_by_role("button", name="Start game", exact=True).wait_for(timeout=15000)
        shared_code = shared_host.locator("#room-heading").inner_text().split(" · ")[-1]
        shared_guest = browser.new_page()
        shared_guest.goto(url)
        shared_guest.get_by_role("searchbox", name="Search room, game, host, or code").fill(shared_code)
        shared_row = shared_guest.locator(".room-list li").filter(has_text=shared_code)
        assert "Host-shared NES" in shared_row.inner_text()
        file_choosers = []
        shared_guest.on("filechooser", lambda chooser: file_choosers.append(chooser))
        shared_row.get_by_role("button", name="Join", exact=True).click()
        shared_guest.get_by_role("button", name="Prepare to play", exact=True).wait_for(timeout=30000)
        assert not file_choosers
        assert shared_guest.get_by_role("button", name="Choose matching NES file").count() == 0
        shared_guest.get_by_role("button", name="Prepare to play", exact=True).click()
        shared_host.get_by_text("Guest is prepared. Start together when you are ready.", exact=False).wait_for(timeout=15000)
        shared_guest.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, value: true}); window.dispatchEvent(new Event('blur')); document.dispatchEvent(new Event('visibilitychange'))")
        shared_host.get_by_role("button", name="Start game", exact=True).click()
        for tab in (shared_host, shared_guest):
            tab.wait_for_function("Number(document.querySelector('[data-testid=game-frame]')?.textContent.split(' ')[0])>10", timeout=30000)
        before_switch = int(shared_host.get_by_test_id("game-frame").inner_text().split(" ")[0])
        guest_before_switch = int(shared_guest.get_by_test_id("game-frame").inner_text().split(" ")[0])
        shared_host.evaluate(throttle_window)
        shared_host.evaluate(hide_tab)
        for tab, before in ((shared_host, before_switch), (shared_guest, guest_before_switch)):
            tab.wait_for_function("frames => Number(document.querySelector('[data-testid=game-frame]')?.textContent.split(' ')[0])>frames+60", arg=before, timeout=15000)
            tab.wait_for_function("document.querySelector('[data-testid=game-status]')?.textContent === 'Playing together.'", timeout=5000)
        result["local_file_public_discovery_and_shared_play"] = True
        result["tab_switch_keeps_shared_play_running"] = True
        failed_download = browser.new_page()
        failed_download.route("**/catalog/super-tilt-bro-*.nes", lambda route: route.abort())
        failed_download.goto(url)
        failed_download.get_by_role("searchbox", name="Search room, game, host, or code").fill("Super Tilt Bro")
        failed_download.get_by_role("button", name="Join as host").first.click()
        failed_download.get_by_role("button", name="Retry download").wait_for(timeout=15000)
        assert "could not download. Retry download." in failed_download.get_by_test_id("included-status").inner_text()
        assert failed_download.get_by_role("button", name="Choose local NES file").count() == 0
        if screenshot_dir:
            failed_download.screenshot(path=str(screenshot_dir / "included-download-failure.png"))
        failed_download.unroute("**/catalog/super-tilt-bro-*.nes")
        failed_download.get_by_role("button", name="Retry download").click()
        failed_download.wait_for_function("!document.querySelector('.room-start button').disabled", timeout=30000)
        result["included_download_failure_and_retry"] = True
        offline = browser.new_page()
        offline.add_init_script("""window.nativeRoomsSocket=WebSocket;
          window.WebSocket=function(){throw Error('Rooms temporarily offline')};""")
        offline.goto(url)
        offline.set_input_files("input[type=file]", fixture)
        offline.get_by_role("button", name="Retry upload").wait_for(timeout=15000)
        assert offline.get_by_role("button", name="Choose NES file", exact=True).is_visible()
        offline.evaluate("()=>{window.WebSocket=window.nativeRoomsSocket}")
        offline.get_by_role("button", name="Retry upload").click()
        offline.get_by_role("button", name="Start game", exact=True).wait_for(timeout=15000)
        result["room_creation_failure_and_retry"] = True
        invalid = browser.new_page()
        invalid.goto(url)
        invalid.set_input_files("input[type=file]", {"name": "bad.nes", "mimeType": "application/octet-stream", "buffer": b"invalid"})
        invalid.locator(".selection-status").wait_for()
        assert invalid.get_by_role("button", name="Choose NES file", exact=True).is_visible()
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
            assert b"Host your NES file" in source and b"Join as host" in (ROOT / "apps/client/src/DirectoryPanel.tsx").read_bytes()
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--screenshot-dir", type=Path)
    args = parser.parse_args()
    source_check()
    result = {"result": "pass", "source_ownership": True}
    if not args.source_only:
        result.update(runtime_check(args.browser, args.screenshot_dir))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
