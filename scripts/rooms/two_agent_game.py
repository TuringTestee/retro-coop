"""Two independent browser processes join and play one host-shared NES room.

Only the host process receives the NES file path. The guest learns the
expected fingerprint from the published room and downloads bytes over HTTP.
"""

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
from layout_geometry import GeometryRecorder, browser_zoom, control_visibility, verify_zoom, zoom_context


ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--role", choices=("host", "guest", "verify", "run"), required=True)
parser.add_argument("--runtime-root", type=Path, default=ROOT, help="Checkout providing the built runtime and fixture")
parser.add_argument("--url", help="URL printed by scripts/rooms/browser-server.ts")
parser.add_argument("--rom", type=Path, help="Host NES file; never supplied to the guest")
parser.add_argument("--visibility", choices=("public", "protected"), default="public")
parser.add_argument("--expect-controller-ram", help="Two diagnostic WRAM bytes after held P1/P2 input, e.g. 128,64")
parser.add_argument("--session-dir", type=Path, required=True)
parser.add_argument("--width", type=int, default=1366)
parser.add_argument("--height", type=int, default=682)
parser.add_argument("--zoom", type=int, choices=(1, 2), default=1)
args = parser.parse_args()
ROOT = args.runtime_root.resolve()
expected_ram = [int(value) for value in args.expect_controller_ram.split(",")] if args.expect_controller_ram else None
if expected_ram is not None and (len(expected_ram) != 2 or any(value < 0 or value > 255 for value in expected_ram)):
    parser.error("--expect-controller-ram needs two byte values")
session = args.session_dir.resolve()
session.mkdir(parents=True, exist_ok=True)


def save(name, value):
    target = session / name
    temporary = session / f".{name}.{os.getpid()}"
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(target)


def wait_for(name, seconds=100):
    target = session / name
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if target.exists():
            return json.loads(target.read_text())
        time.sleep(0.1)
    raise TimeoutError(f"Waiting for {name}; another player did not reach this step")


def verify():
    host, guest = wait_for("host.json", 1), wait_for("guest.json", 1)
    assert host["result"] == guest["result"] == "pass"
    assert host["role"] == "host" and guest["role"] == "guest"
    assert host["room_id"] == guest["room_id"]
    assert host["visibility"] == guest["visibility"] == args.visibility
    assert host["room_code"] == guest["room_code"]
    assert host["rom_sha256"] == guest["rom_sha256"]
    assert host["game_status"] == guest["game_status"] == "paused"
    assert host["resumed_together"] and guest["resumed_together"]
    assert host["started"] == guest["started"] == "shared"
    assert host["established"] and guest["established"]
    assert host["frames"] >= 200 and guest["frames"] >= 200
    assert guest["rom_argument_received"] is False
    assert guest["file_chooser_count"] == 0
    assert host["store_verified_before_reload"] is True
    assert host["saved_row_selected_after_reload"] is True
    assert host["file_input_count_after_reload"] == 0
    assert host["received_gameplay"]["input"] > 0 and host["received_gameplay"]["frame"] == 0
    assert guest["received_gameplay"]["frame"] > 0 and guest["received_gameplay"]["input"] == 0
    assert host["last_hash"] and host["last_hash"] == guest["last_hash"]
    assert host["frames"] == guest["frames"] == host["last_hash"]["frame"]
    assert host["controller_ram"] == guest["controller_ram"]
    if expected_ram is not None:
        assert host["controller_ram"] == expected_ram
    assert host["direct_without_notice"] and guest["direct_without_notice"]
    assert not host["page_errors"] and not guest["page_errors"]
    assert all((session / f"{role}-{view}.png").stat().st_size > 0
               for role in ("host", "guest") for view in ("playing", "room"))
    result = {
        "result": "pass",
        "claim": "A reloaded saved library game reached 200 synchronized frames without a guest ROM path",
        "room_id": host["room_id"],
        "room_code": host["room_code"],
        "visibility": args.visibility,
        "rom_sha256": host["rom_sha256"],
        "host_frames": host["frames"],
        "guest_frames": guest["frames"],
        "host_received_inputs": host["received_gameplay"]["input"],
        "guest_received_committed_frames": guest["received_gameplay"]["frame"],
        "matching_paused_hash": host["last_hash"],
        "paused_layout": {
            role: {
                "play_to_pause": row["play_to_pause_layout"],
                "pause_to_resume": row["pause_to_resume_layout"],
                "leave": row["paused_leave_bounds"],
                "ready": row["paused_resume_bounds"],
            } for role, row in (("host", host), ("guest", guest))
        },
        "host_resume_action_max_drift_css_px": max(
            abs(host["ready_slot_bounds"][axis] - host["resume_slot_bounds"][axis])
            for axis in ("x", "y", "width", "height")
        ),
        "controller_ram": host["controller_ram"],
        "store_verified_before_reload": host["store_verified_before_reload"],
        "saved_row_selected_after_reload": host["saved_row_selected_after_reload"],
        "file_input_count_after_reload": host["file_input_count_after_reload"],
        "guest_rom_argument_received": guest["rom_argument_received"],
        "guest_file_chooser_count": guest["file_chooser_count"],
        "host_elapsed_seconds": host["elapsed_seconds"],
        "guest_elapsed_seconds": guest["elapsed_seconds"],
        "host_page_errors": host["page_errors"],
        "guest_page_errors": guest["page_errors"],
        "host_screenshot": str(session / "host-playing.png"),
        "guest_screenshot": str(session / "guest-playing.png"),
        "host_room_screenshot": str(session / "host-room.png"),
        "guest_room_screenshot": str(session / "guest-room.png"),
    }
    save("result.json", result)
    print(json.dumps(result, indent=2))


if args.role == "verify":
    verify()
    raise SystemExit(0)
if args.role == "run":
    if not args.rom:
        parser.error("run needs --rom")
    if any((session / name).exists() for name in ("host-ready.json", "host.json", "guest.json")):
        parser.error("run needs a fresh --session-dir")
    with (session / "server.log").open("w") as server_log:
        service = subprocess.Popen(
            ["node", "scripts/rooms/browser-server.ts"],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=server_log, text=True,
        )
        try:
            address = service.stdout.readline()
            if not address:
                raise RuntimeError("The test gateway exited before reporting its URL")
            url = json.loads(address)["url"]
            workers = []
            with (session / "host.log").open("w") as host_log, (session / "guest.log").open("w") as guest_log:
                for role, log in (("host", host_log), ("guest", guest_log)):
                    role_arguments = ["--rom", str(args.rom.resolve())] if role == "host" else []
                    worker = subprocess.Popen(
                        [sys.executable, __file__, "--role", role, "--url", url,
                         *role_arguments, "--runtime-root", str(ROOT), "--session-dir", str(session),
                         "--width", str(args.width), "--height", str(args.height),
                         "--zoom", str(args.zoom),
                         "--visibility", args.visibility,
                         *(["--expect-controller-ram", args.expect_controller_ram] if args.expect_controller_ram else [])],
                        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                    )
                    workers.append(worker)
                try:
                    deadline = time.monotonic() + 55
                    while time.monotonic() < deadline:
                        statuses = [worker.poll() for worker in workers]
                        if all(status == 0 for status in statuses):
                            break
                        if any(status is not None and status != 0 for status in statuses):
                            raise RuntimeError(f"Player processes failed: {statuses}")
                        time.sleep(0.1)
                    else:
                        raise TimeoutError("Player processes exceeded 55 seconds")
                finally:
                    for worker in workers:
                        if worker.poll() is None:
                            worker.terminate()
                            worker.wait(timeout=5)
        except Exception:
            for role in ("host", "guest"):
                log = session / f"{role}.log"
                if log.exists():
                    print(f"{role} log:\n{log.read_text()[-6000:]}", file=sys.stderr)
            raise
        finally:
            service.terminate()
            service.wait(timeout=5)
    verify()
    raise SystemExit(0)
if not args.url or (args.role == "host" and not args.rom) or (args.role == "guest" and args.rom):
    parser.error("host needs --url and --rom; guest needs --url without --rom")
rom = args.rom.read_bytes() if args.rom else None
rom_hash = hashlib.sha256(rom).hexdigest() if rom is not None else None
errors = []
started = time.monotonic()

with sync_playwright() as playwright, ExitStack() as resources:
    zoom_worker = None
    if args.zoom == 2:
        context, zoom_worker = resources.enter_context(
            zoom_context(playwright, {"width": args.width * 2, "height": args.height * 2})
        )
        page = context.new_page()
        browser = context.browser
    else:
        browser = playwright.chromium.launch(ignore_default_args=["--mute-audio"])
        resources.callback(browser.close)
        page = browser.new_page(viewport={"width": args.width, "height": args.height})
    try:
        page.set_default_timeout(15000)
        page.on("pageerror", lambda error: errors.append(str(error)))
        # Room creation and Join first arrive as command results. The gameplay
        # fixture records later room broadcasts, so also record result rooms.
        page.add_init_script((ROOT / "scripts/gameplay/fixture.js").read_text() + """
            (() => { const Socket = WebSocket; window.WebSocket = class extends Socket {
              constructor(...args) { super(...args); this.addEventListener('message', event => {
                try { const packet = JSON.parse(event.data);
                  const room = packet.type === 'result' && packet.ok ? packet.data?.room : undefined;
                  if (room) proof.room = room;
                } catch {}
              }); }
            }; })();
        """)
        page.goto(args.url)
        zoom_receipt = browser_zoom(page, zoom_worker, 2) if zoom_worker else None
        page.get_by_test_id("directory").wait_for(state="visible")
        file_choosers = []
        page.on("filechooser", lambda chooser: file_choosers.append(chooser))
        store_verified_before_reload = False
        saved_row_selected_after_reload = False
        file_input_count_after_reload = None

        if args.role == "host":
            page.get_by_role("button", name="Create game", exact=True).click()
            page.set_input_files("input[type=file]", {
                "name": "shared-game.nes", "mimeType": "application/octet-stream", "buffer": rom,
            })
            page.locator('.create-library li').filter(has_text='shared-game.nes').wait_for()
            store_check = '''async ({hash,size})=>{
              const db=await new Promise((resolve,reject)=>{const q=indexedDB.open('retro-coop-local',3);q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error)});
              const record=await new Promise((resolve,reject)=>{const q=db.transaction('roms').objectStore('roms').get(hash);q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error)});
              db.close();if(record?.sha256!==hash||record?.size!==size||record.bytes?.byteLength!==size||record.label!=='shared-game.nes')return false;
              const digest=await crypto.subtle.digest('SHA-256',record.bytes);
              return Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('')===hash;
            }'''
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                store_verified_before_reload = page.evaluate(store_check, {"hash": rom_hash, "size": len(rom)})
                if store_verified_before_reload:
                    break
                page.wait_for_timeout(50)
            assert store_verified_before_reload
            page.reload()
            if zoom_worker:
                zoom_receipt = browser_zoom(page, zoom_worker, 2)
            page.get_by_test_id("create-game").wait_for(state="visible")
            file_input_count_after_reload = page.evaluate("document.querySelector('input[type=file]')?.files?.length")
            assert file_input_count_after_reload == 0
            saved_row = page.locator(".create-library li").filter(has_text="shared-game.nes")
            saved_row.get_by_role("button").wait_for(state="visible")
            assert saved_row.count() == 1
            saved_row.get_by_role("button").click()
            page.get_by_role("button", name="Create room", exact=True).wait_for()
            page.wait_for_function("!document.querySelector('.create-actions button')?.disabled", polling=50)
            assert page.locator(".create-library li button.selected strong").inner_text() == "shared-game.nes"
            saved_row_selected_after_reload = True
            page.get_by_label("Room access").select_option(args.visibility)
            if args.visibility == "protected":
                page.get_by_label("Room password").fill("blue-sky-room")
            page.get_by_role("button", name="Create room", exact=True).click()
            page.get_by_test_id("room-view").wait_for(state="attached")
            page.wait_for_function("proof.room?.role==='host'", polling=50)
            room = page.evaluate("proof.room")
            assert room["occupancy"] == 1 and room["visibility"] == args.visibility
            assert "catalogId" not in room and room["romBytes"] == len(rom)
            assert not page.get_by_role("button", name="Start game", exact=True).is_enabled()
            page.get_by_role("button", name="Ready", exact=True).click()
            invitation=page.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite") if args.visibility == "protected" else None
            save("host-ready.json", {"room_id": room["id"], "code": room.get("code"), "invitation": invitation})
            prepared = wait_for("guest-ready.json")
            page.wait_for_function(
                "member => proof.room?.slots.some(slot => slot.member?.id === member) && proof.room?.matches && proof.room?.game?.ready?.includes(member)",
                arg=prepared["member_id"],
                timeout=30000,
                polling=50,
            )
            page.locator('[data-slot-id="slot-2"] [data-slot-region="status"]').filter(has_text="Ready").wait_for()
            if page.get_by_role("button", name="Ready", exact=True).count():
                page.get_by_role("button", name="Ready", exact=True).click()
            page.get_by_role("button", name="Start game", exact=True).click()
        else:
            expected = wait_for("host-ready.json")
            if args.visibility == "protected":
                page.goto(expected["invitation"])
                if zoom_worker:
                    zoom_receipt = browser_zoom(page, zoom_worker, 2)
                page.get_by_role("button", name="Join room", exact=True).click()
                page.get_by_label("Room password").fill("blue-sky-room")
                page.locator(".room-password-dialog").get_by_role("button", name="Join room", exact=True).click()
            else:
                search = page.get_by_label("Search room, game, host, or code")
                search.fill(expected["code"])
                # The room ID comes from the live directory; select that exact row.
                row = page.locator(f'.room-list li[data-room-id="{expected["room_id"]}"]')
                row.get_by_role("button", name="Join", exact=True).click()
            page.get_by_test_id("room-view").wait_for(state="attached")
            page.wait_for_function("proof.room?.role==='member'", polling=50)
            assert page.evaluate("proof.room.id") == expected["room_id"]
            assert page.evaluate("!('catalogId' in proof.room) && proof.room.romBytes > 0")
            rom_hash = page.evaluate("proof.room.fingerprint.romSha256")
            page.get_by_role("button", name="Ready", exact=True).wait_for(timeout=30000)
            page.wait_for_function("proof.room?.matches===true", timeout=30000, polling=50)
            page.get_by_role("button", name="Ready", exact=True).click()
            save("guest-ready.json", {"room_id": expected["room_id"], "rom_sha256": rom_hash, "member_id": page.evaluate("proof.room.chatMembership")})

        page.wait_for_function(
            "proof.room?.established && proof.room?.started==='shared' && proof.room?.game?.status==='playing'",
            timeout=30000,
            polling=50,
        )
        assert page.evaluate("proof.room.fingerprint.romSha256") == rom_hash
        page.evaluate("releaseFrames()")
        page.locator("canvas").focus()
        page.keyboard.down("x" if args.role == "host" else "z")
        page.wait_for_function("proof.frameCount>=220", timeout=30000, polling=50)
        controller_ram = None
        if expected_ram is not None:
            page.evaluate("currentWorker.postMessage({type:'state-export',requestId:900000})")
            page.wait_for_function("Array.isArray(proof.controllerRam)", timeout=10000, polling=50)
            controller_ram = page.evaluate("proof.controllerRam")
            assert controller_ram == expected_ram, f"Both controllers did not change diagnostic game memory: {controller_ram}"
        save(f"{args.role}-sampled.json", {"controller_ram": controller_ram})
        wait_for(f"{'guest' if args.role == 'host' else 'host'}-sampled.json", 15)
        page.keyboard.up("x" if args.role == "host" else "z")
        direct_without_notice = page.get_by_test_id("connection-status").count() == 0
        assert direct_without_notice, "Direct shared play should have no connection notice"
        layout = GeometryRecorder(page, f"{args.role}-play-to-pause",
            "#room-heading, [data-layout-region=shared-leave-actions], .room-panel .play-controls, .room-panel .voice-card, [data-layout-region=game-actions], .room-detail-scroll")
        layout.mark("playing")
        page.screenshot(path=str(session / f"{args.role}-playing.png"), full_page=True)
        if args.role == "host":
            wait_for("guest-200.json", 30)
            page.get_by_role("button", name="Pause", exact=True).click()
        else:
            save("guest-200.json", {"frames": page.evaluate("proof.frameCount")})
        page.wait_for_function("proof.room?.game?.status==='paused'", timeout=15000, polling=50)
        layout.mark("paused")
        layout_result = layout.finish(session / f"{args.role}-play-to-pause.json",
            required=("room-heading", "shared-leave-actions", "play-controls", "voice-card", "game-actions", "room-detail-scroll"))
        assert page.get_by_test_id("connection-status").count() == 0
        page.wait_for_function("proof.hashes.length>0", timeout=15000, polling=50)
        page.locator(".room-panel").wait_for(state="visible")
        leave = page.get_by_role("button", name="Leave room", exact=True)
        leave_bounds = control_visibility(leave) if args.width > 760 else None
        leave.focus()
        page.evaluate("()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
        leave_focus_bounds = control_visibility(leave, require_focus=True)
        resume = page.get_by_role("button", name="Ready to resume", exact=True)
        resume_bounds = control_visibility(resume) if args.width > 760 else None
        resume.focus()
        page.evaluate("()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
        resume_focus_bounds = control_visibility(resume, require_focus=True)
        page.screenshot(path=str(session / f"{args.role}-room.png"), full_page=True)
        room = page.evaluate("proof.room")
        assert page.get_by_role("button", name="Ready to resume", exact=True).count() == 1
        assert page.get_by_role("button", name="Choose another file", exact=True).count() == 0
        paused_frames = page.evaluate("proof.frameCount")
        paused_hash = page.evaluate("proof.hashes.at(-1)")
        recovery_layout = GeometryRecorder(page, f"{args.role}-pause-to-resume",
            "#room-heading, [data-layout-region=shared-leave-actions], .room-panel .play-controls, .room-panel .voice-card, [data-layout-region=game-actions], .room-detail-scroll")
        recovery_layout.mark("paused")
        ready_slot_bounds = page.get_by_role("button", name="Ready to resume", exact=True).bounding_box()
        page.get_by_role("button", name="Ready to resume", exact=True).focus()
        page.keyboard.press("Enter")
        page.wait_for_function("proof.room?.game?.ready?.includes(proof.room.chatMembership)", timeout=15000)
        recovery_layout.mark("ready")
        resume_slot_bounds = None
        if args.role == "host":
            page.wait_for_function("proof.room?.game?.status==='resume_ready'", timeout=15000)
            resume_together = page.get_by_role("button", name="Resume together", exact=True)
            control_visibility(resume_together)
            assert page.get_by_role("button", name="Ready to resume", exact=True).count() == 0
            resume_slot_bounds = resume_together.bounding_box()
            assert ready_slot_bounds and resume_slot_bounds
            assert all(abs(ready_slot_bounds[axis]-resume_slot_bounds[axis]) <= 1 for axis in ("x", "y", "width", "height")), (ready_slot_bounds, resume_slot_bounds)
            recovery_layout.mark("all ready")
            resume_together.click()
        page.wait_for_function("proof.room?.game?.status==='playing'", timeout=15000)
        recovery_layout.mark("resumed")
        recovery_layout_result = recovery_layout.finish(session / f"{args.role}-pause-to-resume.json",
            required=("room-heading", "shared-leave-actions", "play-controls", "voice-card", "game-actions", "room-detail-scroll"))
        page.locator("canvas").focus()
        assert page.locator("canvas").evaluate("node => node === document.activeElement")
        leave_layout = GeometryRecorder(page, f"{args.role}-leave-recovery",
            "#room-heading, [data-layout-region=shared-leave-actions], .room-panel .play-controls, .room-panel .voice-card, [data-layout-region=game-actions], .room-detail-scroll")
        leave_layout.mark("playing")
        leave_layout.allow_user_scroll()
        leave = page.get_by_role("button", name="Leave room", exact=True)
        leave.focus()
        control_visibility(leave, require_focus=True)
        leave_style = leave.evaluate("n => ({font:getComputedStyle(n).fontSize,height:n.getBoundingClientRect().height})")
        page.keyboard.press("Enter")
        confirm = page.get_by_role("button", name="Confirm leave", exact=True)
        confirm.wait_for()
        question_fit = page.locator(".room-leave-actions .room-confirm p").evaluate("n => ({height:n.clientHeight,scrollHeight:n.scrollHeight,width:n.clientWidth,scrollWidth:n.scrollWidth})")
        assert question_fit["scrollHeight"] <= question_fit["height"] + 1 and question_fit["scrollWidth"] <= question_fit["width"] + 1, question_fit
        confirm.focus()
        confirm_bounds = control_visibility(confirm, require_focus=True)
        stay = page.get_by_role("button", name="Stay in room", exact=True)
        stay.focus()
        stay_bounds = control_visibility(stay, require_focus=True)
        for action in (confirm, stay):
            style = action.evaluate("n => ({font:getComputedStyle(n).fontSize,height:n.getBoundingClientRect().height})")
            assert style["font"] == leave_style["font"] and abs(style["height"] - leave_style["height"]) <= 1, (leave_style, style)
        leave_layout.allow_user_scroll(False)
        leave_layout.mark("confirm")
        page.screenshot(path=str(session / f"{args.role}-confirm-leave.png"), full_page=True)
        leave_layout.allow_user_scroll()
        page.keyboard.press("Enter")
        leave.wait_for()
        page.wait_for_function("document.activeElement?.hasAttribute('data-leave-room')")
        control_visibility(leave, require_focus=True)
        leave_layout.allow_user_scroll(False)
        leave_layout.mark("cancelled")
        page.evaluate("""() => { const original = WebSocket.prototype.send;
          WebSocket.prototype.send = function(raw) {
            let command; try { command = JSON.parse(raw); } catch {}
            if (command?.type === 'close' || command?.type === 'leave') {
              WebSocket.prototype.send = original;
              queueMicrotask(() => this.dispatchEvent(new MessageEvent('message', {
                data: JSON.stringify({type:'result',requestId:command.requestId,ok:false,error:'room_unavailable'})
              })));
              return;
            }
            return original.call(this, raw);
          };
        }""")
        leave_layout.allow_user_scroll()
        leave.focus()
        page.keyboard.press("Enter")
        confirm = page.get_by_role("button", name="Confirm leave", exact=True)
        confirm.focus()
        page.keyboard.press("Enter")
        error = page.locator(".room-leave-actions .room-confirm [role=alert]").filter(has_text="Could not leave. Retry or stay.")
        error.wait_for()
        assert error.evaluate("n => n.scrollWidth <= n.clientWidth + 1"), "Leave error does not fit its status region"
        control_visibility(error)
        stay = page.get_by_role("button", name="Stay in room", exact=True)
        stay.focus()
        control_visibility(stay, require_focus=True)
        leave_layout.allow_user_scroll(False)
        leave_layout.mark("failed leave")
        page.screenshot(path=str(session / f"{args.role}-failed-leave.png"), full_page=True)
        leave_layout.allow_user_scroll()
        page.keyboard.press("Enter")
        leave.wait_for()
        page.wait_for_function("document.activeElement?.hasAttribute('data-leave-room')")
        control_visibility(leave, require_focus=True)
        leave_layout.allow_user_scroll(False)
        leave_layout.mark("recovered")
        leave_layout_result = leave_layout.finish(session / f"{args.role}-leave-recovery.json",
            required=("room-heading", "shared-leave-actions", "play-controls", "voice-card", "game-actions", "room-detail-scroll"))
        assert page.evaluate("proof.room?.established && proof.room?.game?.status==='playing'")
        access_layout_result = None
        if args.role == "host" and args.visibility == "protected":
            access_layout = GeometryRecorder(page, "host-playing-public-access",
                "#room-heading, [data-layout-region=shared-leave-actions], .room-panel .play-controls, .room-panel .voice-card, [data-layout-region=game-actions], .room-detail-scroll")
            access_layout.mark("protected playing")
            access_layout.allow_user_scroll()
            page.get_by_role("button", name="Players", exact=True).click()
            page.locator("details.session-settings summary").click()
            public = page.get_by_role("button", name="Make public", exact=True)
            public.focus()
            control_visibility(public, require_focus=True)
            page.keyboard.press("Enter")
            group = page.get_by_role("group", name="Confirm public room")
            group.wait_for()
            assert "Anyone can join" in group.inner_text()
            confirm_public = group.get_by_role("button", name="Confirm public access", exact=True)
            confirm_public.focus()
            control_visibility(confirm_public, require_focus=True)
            keep_password = group.get_by_role("button", name="Keep password", exact=True)
            keep_password.focus()
            control_visibility(keep_password, require_focus=True)
            page.screenshot(path=str(session / "host-confirm-public.png"), full_page=True)
            page.keyboard.press("Enter")
            page.wait_for_function("document.activeElement?.hasAttribute('data-make-public')")
            control_visibility(public, require_focus=True)
            access_layout.mark("public change cancelled")
            page.keyboard.press("Enter")
            confirm_public = page.get_by_role("group", name="Confirm public room").get_by_role("button", name="Confirm public access", exact=True)
            confirm_public.focus()
            control_visibility(confirm_public, require_focus=True)
            page.keyboard.press("Enter")
            page.wait_for_function("proof.room?.visibility==='public' && proof.room?.game?.status==='playing'")
            access_layout.allow_user_scroll(False)
            access_layout.mark("public playing")
            access_layout_result = access_layout.finish(session / "host-playing-public-access.json",
                required=("room-heading", "shared-leave-actions", "play-controls", "voice-card", "game-actions", "room-detail-scroll"))
        received = page.evaluate("proof.admission.received")
        expected_packet = "input" if args.role == "host" else "frame"
        assert received[expected_packet] > 0, f"No authoritative gameplay traffic reached this {args.role}: {received}"
        evidence = {
            "result": "pass",
            "role": args.role,
            "room_id": room["id"],
            "room_code": room.get("code"),
            "visibility": room["visibility"],
            "rom_sha256": rom_hash,
            "started": room["started"],
            "game_status": room["game"]["status"],
            "established": room["established"],
            "frames": paused_frames,
            "received_gameplay": received,
            "last_hash": paused_hash,
            "resumed_frames": page.evaluate("proof.frameCount"),
            "controller_ram": controller_ram,
            "direct_without_notice": direct_without_notice,
            "browser": browser.version if browser else "chromium persistent context",
            "zoom": zoom_receipt,
            "zoom_verified": verify_zoom(zoom_worker, zoom_receipt) if zoom_worker and zoom_receipt else None,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "page_errors": errors,
            "rom_argument_received": args.rom is not None,
            "file_chooser_count": len(file_choosers),
            "store_verified_before_reload": store_verified_before_reload,
            "saved_row_selected_after_reload": saved_row_selected_after_reload,
            "file_input_count_after_reload": file_input_count_after_reload,
            "single_keyboard_resume_action": True,
            "back_to_game_focuses_canvas": True,
            "resumed_together": True,
            "ready_slot_bounds": ready_slot_bounds,
            "resume_slot_bounds": resume_slot_bounds,
            "pause_to_resume_layout": recovery_layout_result,
            "leave_recovery_layout": leave_layout_result,
            "playing_public_access_layout": access_layout_result,
            "confirm_leave_bounds": confirm_bounds,
            "stay_in_room_bounds": stay_bounds,
            "paused_leave_bounds": leave_bounds,
            "paused_leave_focus_bounds": leave_focus_bounds,
            "paused_resume_bounds": resume_bounds,
            "paused_resume_focus_bounds": resume_focus_bounds,
            "play_to_pause_layout": layout_result,
        }
        save(f"{args.role}.json", evidence)
        # Both browsers stay connected until each has checked keyboard resume,
        # canvas focus, and the paused game hash. Early peer exit clears ready.
        wait_for(f"{'guest' if args.role == 'host' else 'host'}.json", 15)
        print(json.dumps(evidence, indent=2))
    except Exception:
        page.screenshot(path=str(session / f"{args.role}-failure.png"), full_page=True)
        save(f"{args.role}-failure.json", {
            "role": args.role,
            "room": page.evaluate("window.proof?.room"),
            "frames": page.evaluate("window.proof?.frameCount"),
            "last_hash": page.evaluate("window.proof?.hashes?.at(-1)"),
            "status": page.get_by_test_id("room-status").all_inner_texts(),
            "page_errors": errors,
        })
        raise
