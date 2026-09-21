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


def browser_check(screenshot_dir=None):
    from playwright.sync_api import sync_playwright

    result = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.add_init_script("""window.entrySockets=[];const Native=WebSocket;
          window.WebSocket=class extends Native {constructor(...args){super(...args);entrySockets.push(this)}};""")
        page.goto("http://127.0.0.1:8765/")
        page.get_by_text("No public lobbies yet. Start a game above.", exact=True).wait_for()
        assert page.get_by_role("button", name="Play Super Tilt Bro", exact=True).count() == 1
        assert page.get_by_role("button", name="Play From Below", exact=True).count() == 1
        assert page.locator(".catalog-launcher h2").all_text_contents() == ["Super Tilt Bro", "From Below"]
        choose = page.get_by_role("button", name="Choose NES file", exact=True)
        choose.focus()
        assert choose.evaluate("node => node === document.activeElement")
        assert page.evaluate("document.documentElement.scrollHeight <= innerHeight && document.documentElement.scrollWidth <= innerWidth")
        result["viewport_without_page_scroll"] = True
        page.locator(".catalog-launcher").nth(1).get_by_role("button", name="Show lobbies").click()
        page.get_by_role("heading", name="From Below lobbies", exact=True).wait_for()
        page.get_by_role("button", name="Show all lobbies", exact=True).click()

        catalog_url = "**/catalog/super-tilt-bro-*.nes"
        page.route(catalog_url, lambda route: route.abort())
        page.get_by_role("button", name="Play Super Tilt Bro", exact=True).click()
        page.get_by_test_id("included-status").wait_for()
        page.wait_for_function("[...document.querySelectorAll('button')].some(button => button.textContent === 'Play Super Tilt Bro' && !button.disabled)")
        assert page.get_by_role("button", name="Play Super Tilt Bro", exact=True).is_enabled()
        result["catalog_failure_retryable"] = True
        if screenshot_dir:
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot_dir / "catalog-recovery.png"))
        page.unroute(catalog_url)

        page.evaluate("entrySockets.filter(socket => socket.url.includes(':8787/')).forEach(socket => socket.close())")
        page.get_by_role("button", name="Retry directory", exact=True).wait_for()
        page.get_by_role("button", name="Retry directory", exact=True).click()
        page.get_by_text("No public lobbies yet. Start a game above.", exact=True).wait_for()
        result["directory_retry_recovered"] = True

        fixture = ROOT / "apps/client/public/generated/diagnostic.nes"
        with page.expect_file_chooser() as chooser_info:
            page.get_by_role("button", name="Choose NES file", exact=True).click()
        chooser_info.value.set_files(fixture)
        page.get_by_test_id("room-view").wait_for(state="attached", timeout=15000)
        result["catalog_failure_local_file_recovery"] = True
        if screenshot_dir:
            page.screenshot(path=str(screenshot_dir / "catalog-local-file-recovery.png"))

        retry = browser.new_page(viewport={"width": 1280, "height": 800})
        retry.goto("http://127.0.0.1:8765/")
        retry.route(catalog_url, lambda route: route.abort())
        retry.get_by_role("button", name="Play Super Tilt Bro", exact=True).click()
        retry.wait_for_function("[...document.querySelectorAll('button')].some(button => button.textContent === 'Play Super Tilt Bro' && !button.disabled)")
        retry.unroute(catalog_url)
        retry.get_by_role("button", name="Play Super Tilt Bro", exact=True).click()
        retry.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>2", timeout=30000)
        retry.get_by_test_id("room-view").wait_for(state="attached")
        retry.get_by_role("button", name="Game help", exact=True).click()
        retry.get_by_role("heading", name="Game help · Super Tilt Bro", exact=True).wait_for()
        retry.get_by_role("button", name="Close", exact=True).click()
        result["catalog_retry_loaded_super_tilt_bro"] = True
        if screenshot_dir:
            retry.screenshot(path=str(screenshot_dir / "super-tilt-bro-playing.png"))

        from_below = browser.new_page(viewport={"width": 1280, "height": 800})
        from_below.goto("http://127.0.0.1:8765/")
        from_below.get_by_role("button", name="Play From Below", exact=True).click()
        from_below.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>120", timeout=30000)
        from_below.wait_for_function("()=>{const c=document.querySelector('canvas'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;return d.some((v,i)=>i%4!==3&&v!==0)}", timeout=30000)
        from_below.get_by_test_id("room-view").wait_for(state="attached")
        from_below.get_by_role("button", name="Game help", exact=True).click()
        from_below.get_by_role("heading", name="Game help · From Below", exact=True).wait_for()
        from_below.get_by_role("button", name="Close", exact=True).click()
        result["from_below_loaded_and_rendered"] = True
        if screenshot_dir:
            from_below.screenshot(path=str(screenshot_dir / "from-below-playing.png"))

        local = browser.new_page(viewport={"width": 1280, "height": 800})
        local.goto("http://127.0.0.1:8765/")
        local.set_input_files("input[type=file]", fixture)
        local.get_by_test_id("room-view").wait_for(state="attached", timeout=15000)
        assert "Public lobby" in local.locator(".room-invite").inner_text()
        result["local_file_hosted"] = True
        browser.close()
    return result


def startup_failure_check(environment):
    blocker = socket.socket()
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    blocker.bind(("127.0.0.1", 8765))
    blocker.listen()
    try:
        failed = subprocess.run(
            ["sh", "scripts/demo.sh"], cwd=ROOT, env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=15,
        )
    finally:
        blocker.close()
    assert failed.returncode != 0, failed.stdout
    wait_closed(8787)


def start_launcher(environment, log_path):
    log = log_path.open("w")
    service = subprocess.Popen(
        ["sh", "scripts/demo.sh"], cwd=ROOT, env=environment,
        stdout=log, stderr=subprocess.STDOUT, text=True, start_new_session=True,
    )
    return service, log


def wait_ready(service, log_path):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if service.poll() is not None:
            raise AssertionError("Documented launcher exited early: " + log_path.read_text())
        try:
            if fetch("http://127.0.0.1:8765/")[0] == 200:
                return
        except OSError:
            time.sleep(.1)
    raise AssertionError("Documented application URL did not become ready: " + log_path.read_text())


def stop_launcher(service, signum):
    service.send_signal(signum)
    try:
        return_code = service.wait(timeout=5)
    except subprocess.TimeoutExpired as error:
        os.killpg(service.pid, signal.SIGKILL)
        service.wait()
        raise AssertionError(f"launcher ignored signal {signum}") from error
    assert return_code in (-signum, 128 + signum), return_code
    wait_closed(8765)
    wait_closed(8787)


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
    startup_failure_check(environment)
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
            assert b"Host your NES file" in source and b"Show lobbies" in source and b"Play " in source
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
                      "catalog": catalog, "client_startup_failure_released_ports": [8765, 8787],
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
