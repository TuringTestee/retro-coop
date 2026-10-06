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


def migrated_default_preferences(browser, url, output):
    """Restore both supported record shapes, then edit and play with distinct Save/B keys."""
    from playwright.sync_api import expect
    from rooms.ui_helpers import choose_section, capture_binding
    rows=[]
    context=browser.new_context(viewport={'width':1280,'height':800})
    context.add_init_script((ROOT/'scripts/gameplay/fixture.js').read_text()+"addEventListener('DOMContentLoaded',()=>releaseFrames());")
    page=context.new_page()
    def load_game():
        page.get_by_role('button',name='Load NES game').click();page.get_by_role('button',name='Add game file').click();page.get_by_label('NES cartridge file').set_input_files(str(ROOT/'spikes/d02/fixture.local.nes'))
        page.get_by_role('button',name='Prepare',exact=True).wait_for()
    try:
        page.goto(url);page.get_by_role('button',name='Host a new game').click();load_game()
        editor,capture=capture_binding(page);capture.press('k')
        editor.get_by_role('button',name='Save',exact=True).click();expect(editor).to_have_count(0)
        page.get_by_role('button',name='Back to Main Page',exact=True).click();page.get_by_role('button',name='Close lobby',exact=True).click()
        page.locator('.rc-listing').wait_for()
        for count in (15,16):
            page.evaluate("""async count=>{const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('retro-coop-local');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
              await new Promise((resolve,reject)=>{const tx=db.transaction('preferences','readwrite'),store=tx.objectStore('preferences'),r=store.getAll();r.onsuccess=()=>{if(r.result.length!==1){tx.abort();return;}const row=r.result[0],c=row.value.controls;c.keyboard={...c.keyboard,a:['KeyX'],b:['KeyZ'],select:['ShiftLeft','ShiftRight'],start:['Enter'],save:['KeyC']};if(count===15){delete c.keyboard.restart;delete c.gamepad.restart;}store.put(row);};tx.oncomplete=resolve;tx.onabort=()=>reject(tx.error??Error('fixture preferences missing'));});db.close();}""",count)
            for reload in range(2):
                page.reload();page.get_by_role('button',name='Host a new game').click();load_game()
                choose_section(page,'Controls')
                expect(page.get_by_role('button',name='Map B: Z',exact=True)).to_be_visible()
                expect(page.get_by_role('button',name='Map Save: C',exact=True)).to_be_visible()
                assert page.get_by_text('Stored preferences are invalid.',exact=False).count()==0
                if reload==0:
                    page.get_by_role('button',name='Back to Main Page',exact=True).click();page.get_by_role('button',name='Close lobby',exact=True).click();page.locator('.rc-listing').wait_for()
            editor,capture=capture_binding(page,'B');capture.press('b');editor.get_by_role('button',name='Save',exact=True).click();expect(editor).to_have_count(0)
            editor,capture=capture_binding(page,'B');expect(editor).to_contain_text('Current: B');capture.press('z');editor.get_by_role('button',name='Save',exact=True).click();expect(editor).to_have_count(0)
            rows.append({'record_actions':count,'reloads':2,'b':'Z','save':'C','editable':True})
            if count==15:
                page.get_by_role('button',name='Back to Main Page',exact=True).click();page.get_by_role('button',name='Close lobby',exact=True).click();page.locator('.rc-listing').wait_for()
        page.get_by_role('button',name='Prepare',exact=True).click();page.get_by_role('button',name='Start →').click();page.wait_for_function('proof.frameCount>10')
        def native(key,expected):
            before=page.evaluate('proof.frameCount');page.keyboard.down(key)
            page.wait_for_function('before=>proof.frameCount>before+proof.room.game.delay+3',arg=before)
            page.evaluate("delete proof.controllerRam;currentWorker.postMessage({type:'state-export',requestId:900000})")
            page.wait_for_function('proof.controllerRam!==undefined');ram=page.evaluate('proof.controllerRam');assert ram==[expected,0],(count,key,ram)
            page.keyboard.up(key);return ram
        b=native('z',64);save=native('c',0)
        page.get_by_text('Saved to quick slot 1.',exact=True).wait_for()
        rows[-1].update(native_b_ram=b,native_save_ram=save,save_notice=True)
        page.get_by_role('button',name='Back to Main Page',exact=True).click();page.get_by_role('button',name='Close lobby',exact=True).click();page.locator('.rc-listing').wait_for()
    finally:context.close()
    (output/'migrated-default-preferences.json').write_text(json.dumps(rows,indent=2)+'\n')

def browser_check(screenshot_dir=None, url="http://127.0.0.1:8765/"):
    """Exercise the public lobby journey in the built application."""
    from playwright.sync_api import sync_playwright, expect
    from rooms.ui_helpers import choose_panel, choose_audio

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
        browser = playwright.chromium.launch(ignore_default_args=["--mute-audio"])
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
        guest.get_by_role("button",name="Edit your name:",exact=False).click()
        guest.get_by_label("Your name",exact=True).fill("P"*32)
        guest.get_by_role("button",name="Save name",exact=True).click()
        spectator=browser.new_page(viewport={"width":1024,"height":600})
        spectator.goto(url)
        spectator.locator('.rc-lobby-card').first.click()
        spectator.get_by_text("Waiting for the host to load a NES game").wait_for(timeout=15000)
        for sender, receiver, text in ((guest, host, "Ready when you are"),
                                       (host, guest, "Hosting and chatting")):
            choose_panel(sender, "Chat")
            choose_panel(receiver, "Chat")
            field = sender.get_by_label("Message everyone")
            field.press_sequentially(text)
            expect(field).to_have_value(text)
            field.press("Enter")
            expect(receiver.get_by_role("log", name="Lobby messages")).to_contain_text(text)
            expect(field).to_have_value("")
        assert host.get_by_role("button", name="Start →").count() == 0
        choose_panel(host, "Game")
        host.get_by_role("button", name="Load NES game").click()
        host.get_by_role("button", name="Super Tilt Bro", exact=False).click()
        host.get_by_role("button", name="Prepare", exact=True).wait_for(timeout=30000)
        guest.get_by_role("button", name="Prepare", exact=True).wait_for(timeout=30000)
        for page in (host, guest):
            choose_audio(page, "Game sound")
            page.get_by_role("button", name="Mute game", exact=True).click()
        choose_panel(host, "Game")
        choose_panel(guest, "Game")
        primary_region=host.locator(".rc-prepare-action-region").bounding_box()
        prepare_box=host.get_by_role("button",name="Prepare",exact=True).bounding_box()
        host.get_by_role("button", name="Prepare", exact=True).click()
        expect(host.get_by_role("button", name="Start →")).to_be_disabled()
        expect(host.locator(".rc-prepare-cover")).to_contain_text("not ready")
        assert host.locator(".rc-primary-action-reason").evaluate("node=>{const r=node.getBoundingClientRect(),p=node.closest('.rc-prepare-feedback').getBoundingClientRect();return r.left>=p.left&&r.right<=p.right&&r.top>=p.top&&r.bottom<=p.bottom&&node.scrollHeight<=node.clientHeight;}")
        assert host.locator(".rc-prepare-action-region").bounding_box()==primary_region
        start_box=host.get_by_role("button",name="Start →").bounding_box()
        for axis,length in [("x","width"),("y","height")]:
            assert abs((start_box[axis]+start_box[length]/2)-(prepare_box[axis]+prepare_box[length]/2))<1
        assert host.locator(".rc-footer").get_by_role("button",name="Start →").count()==0
        assert guest.get_by_role("button",name="Start →").count()==0
        if screenshot_dir:
            host.screenshot(path=str(screenshot_dir / "centered-start-waiting.png"))
        guest.get_by_role("button", name="Prepare", exact=True).click()
        expect(host.locator(".rc-prepare-cover").get_by_role("button",name="Start →")).to_be_enabled()
        assert host.locator(".rc-prepare-action-region").bounding_box()==primary_region
        assert spectator.get_by_role("button",name="Prepare",exact=True).count()==0
        assert spectator.get_by_role("button",name="Start →").count()==0
        for size in sizes:
            host.set_viewport_size(size)
            choose_panel(host, "Game")
            fits(host)
            assert host.get_by_role("button",name="Start →").count()==1
            assert host.locator(".rc-footer").get_by_role("button",name="Start →").count()==0
            assert host.locator(".rc-prepare-cover").get_by_role("button",name="Start →").evaluate("node => {const r=node.getBoundingClientRect(), p=node.closest('.rc-game-viewport').getBoundingClientRect();return r.left>=p.left&&r.right<=p.right&&r.top>=p.top&&r.bottom<=p.bottom;}")
        if screenshot_dir:
            host.screenshot(path=str(screenshot_dir / "centered-start-ready-phone.png"))
        host.get_by_role("button", name="Start →").click(timeout=15000)
        host.get_by_text("Game starts in", exact=False).wait_for(timeout=15000)
        host.wait_for_function("Number(document.querySelector('canvas')?.dataset.frameCount) > 5", timeout=30000)
        guest.wait_for_function("Number(document.querySelector('canvas')?.dataset.frameCount) > 5", timeout=30000)
        choose_panel(host, "Chat")
        choose_panel(guest, "Chat")
        field = guest.get_by_label("Message everyone")
        field.press_sequentially("Chat while playing Z C A D P Q E")
        expect(field).to_have_value("Chat while playing Z C A D P Q E")
        field.press("Enter")
        expect(host.get_by_role("log", name="Lobby messages")).to_contain_text("Chat while playing Z C A D P Q E")
        expect(field).to_have_value("")
        for page, size in ((host, {"width": 390, "height": 700}), (guest, {"width": 320, "height": 568})):
            page.set_viewport_size(size)
            fits(page)
        choose_panel(host, "Game")
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
        migration_output=screenshot_dir or ROOT / "spikes/d02/public-entrypoint.local/preferences"
        migration_output.mkdir(parents=True,exist_ok=True)
        migrated_default_preferences(browser,url,migration_output)
        browser.close()
    return {"empty_lobby_before_game": True, "guest_chat_and_readiness": True, "incremental_chat_and_enter": True,
            "synchronized_start": True, "centered_start_same_region": True, "spectator_nonblocking": True, "mobile_shell": True, "exit_to_main": True,
            "game_worker_and_frame_cleared": True, "migrated_preferences_reload_and_play": True}

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
            catalog = {
                "super_tilt_bro": fetch("http://127.0.0.1:8765/catalog/super-tilt-bro-e-847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d.nes", "HEAD")[0],
                "from_below": fetch("http://127.0.0.1:8765/catalog/from-below-1.0-1a3ac4faf4b35640505344059ae5d91dae07cd47e1fb4d9d2a33c76391f1c555.nes", "HEAD")[0],
            }
            assert old_status == coordinator_status == 200
            assert home == old_route
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
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--screenshot-dir", type=Path)
    args = parser.parse_args()
    ROOT = args.runtime_root.resolve()
    result = runtime_check(args.browser, args.screenshot_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
