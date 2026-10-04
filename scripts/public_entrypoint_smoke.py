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
    """Exercise the public lobby journey in the built application."""
    from playwright.sync_api import sync_playwright

    def fits(page):
        result = page.evaluate("""() => {
          const names = ['.rc-shell', '.rc-stage', '.rc-footer', '.rc-main-page',
            '.rc-listing', '.rc-create', '.rc-session', '.rc-players',
            '.rc-game-zone', '.rc-chat'];
          const regions = Object.fromEntries(names.map(name => {
            const node = document.querySelector(name);
            if (!node || node.getClientRects().length === 0) return [name, true];
            return [name, node.scrollWidth <= node.clientWidth && node.scrollHeight <= node.clientHeight];
          }));
          const chat = document.querySelector('.rc-chat-history');
          return {document: document.documentElement.scrollWidth <= innerWidth &&
              document.documentElement.scrollHeight <= innerHeight,
              ...regions,
              chat: !chat || getComputedStyle(chat).overflowY === 'auto'};
        }""")
        assert all(result.values()), result

    sizes = ({"width": 1440, "height": 900}, {"width": 1024, "height": 600},
             {"width": 390, "height": 700}, {"width": 320, "height": 568})

    def responsive(page):
        for size in sizes:
            page.set_viewport_size(size)
            fits(page)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        host_context = browser.new_context(viewport={"width": 1280, "height": 800})
        guest_context = browser.new_context(viewport={"width": 1024, "height": 600})
        host = host_context.new_page()
        host.add_init_script("""(() => {
          window.__terminatedWorkers = 0;
          const terminate = Worker.prototype.terminate;
          Worker.prototype.terminate = function() {
            window.__terminatedWorkers++;
            return terminate.call(this);
          };
        })()""")
        guest = guest_context.new_page()
        host.goto(url)
        responsive(host)
        host.get_by_role("button", name="Host a new game").click()
        responsive(host)
        host.get_by_role("button", name="Load NES game").wait_for(timeout=15000)
        assert host.get_by_role("button", name="Start →").count() == 0
        assert host.get_by_test_id("room-slot").count() == 5
        responsive(host)
        if screenshot_dir:
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            host.screenshot(path=str(screenshot_dir / "empty-lobby.png"))
        guest.goto(url)
        guest.locator('.rc-lobby-card').first.click()
        guest.get_by_text("Waiting for the host to load a NES game").wait_for(timeout=15000)
        from playwright.sync_api import expect
        for sender, receiver, text in ((guest, host, "Ready when you are"),
                                       (host, guest, "Hosting and chatting")):
            field = sender.get_by_label("Message everyone")
            field.press_sequentially(text)
            expect(field).to_have_value(text)
            field.press("Enter")
            expect(receiver.get_by_role("log", name="Lobby messages")).to_contain_text(text)
            expect(field).to_have_value("")
        assert host.get_by_role("button", name="Start →").count() == 0
        host.get_by_role("button", name="Load NES game").click()
        host.get_by_role("button", name="Super Tilt Bro", exact=False).click()
        host.get_by_role("button", name="Ready", exact=True).wait_for(timeout=30000)
        guest.get_by_role("button", name="Ready", exact=True).wait_for(timeout=30000)
        host.get_by_role("button", name="Ready", exact=True).click()
        assert host.get_by_role("button", name="Start →").count() == 0
        guest.get_by_role("button", name="Ready", exact=True).click()
        host.get_by_role("button", name="Start →").wait_for(state="visible")
        host.get_by_role("button", name="Start →").click(timeout=15000)
        host.get_by_text("Game starts in", exact=False).wait_for(timeout=15000)
        host.wait_for_function("Number(document.querySelector('canvas')?.dataset.frameCount) > 5", timeout=30000)
        guest.wait_for_function("Number(document.querySelector('canvas')?.dataset.frameCount) > 5", timeout=30000)
        field = guest.get_by_label("Message everyone")
        field.press_sequentially("Chat while playing Z C A D P Q E")
        expect(field).to_have_value("Chat while playing Z C A D P Q E")
        field.press("Enter")
        expect(host.get_by_role("log", name="Lobby messages")).to_contain_text("Chat while playing Z C A D P Q E")
        expect(field).to_have_value("")
        for page, size in ((host, {"width": 390, "height": 700}), (guest, {"width": 320, "height": 568})):
            page.set_viewport_size(size)
            fits(page)
        if screenshot_dir:
            host.screenshot(path=str(screenshot_dir / "playing-mobile.png"))
        host.get_by_role("button", name="Back to Main Page").click()
        host.get_by_role("button", name="Close lobby").click()
        host.locator('.rc-listing').wait_for(timeout=15000)
        assert host.evaluate("window.__terminatedWorkers >= 1"), 'The emulator worker survived the lobby exit.'
        assert host.locator('canvas[aria-label="NES game screen"]').get_attribute('data-frame-count') == '0'
        assert host.locator('canvas[aria-label="NES game screen"]').evaluate("""canvas =>
          [...canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data]
            .every(value => value === 0)"""), 'The previous game frame survived the lobby exit.'
        fits(host)
        browser.close()
    return {"empty_lobby_before_game": True, "guest_chat_and_readiness": True, "incremental_chat_and_enter": True,
            "synchronized_start": True, "mobile_shell": True, "exit_to_main": True,
            "game_worker_and_frame_cleared": True}

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
            source_status, source = fetch("http://127.0.0.1:8765/src/RoomController.tsx")
            catalog = {
                "super_tilt_bro": fetch("http://127.0.0.1:8765/catalog/super-tilt-bro-e-847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d.nes", "HEAD")[0],
                "from_below": fetch("http://127.0.0.1:8765/catalog/from-below-1.0-1a3ac4faf4b35640505344059ae5d91dae07cd47e1fb4d9d2a33c76391f1c555.nes", "HEAD")[0],
            }
            assert old_status == coordinator_status == source_status == 200
            assert b'/src/main.tsx' in home and b'/src/main.tsx' in old_route
            screens = (ROOT / "apps/client/src/UnifiedScreens.tsx").read_bytes()
            assert b"createLobby" in source and b"All lobbies" in screens and b"Host a new game" in screens
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
