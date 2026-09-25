"""Two independent browser processes join and play one host-shared NES room.

Only the host process receives the NES file path. The guest learns the
expected fingerprint from the published room and downloads bytes over HTTP.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--role", choices=("host", "guest", "verify", "run"), required=True)
parser.add_argument("--url", help="URL printed by scripts/rooms/browser-server.ts")
parser.add_argument("--rom", type=Path, help="Host NES file; never supplied to the guest")
parser.add_argument("--visibility", choices=("public", "unlisted"), default="public")
parser.add_argument("--expect-controller-ram", help="Two diagnostic WRAM bytes after held P1/P2 input, e.g. 128,64")
parser.add_argument("--session-dir", type=Path, required=True)
args = parser.parse_args()
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
    assert host["started"] == guest["started"] == "shared"
    assert host["established"] and guest["established"]
    assert host["frames"] >= 200 and guest["frames"] >= 200
    assert guest["rom_argument_received"] is False
    assert guest["file_chooser_count"] == 0
    assert host["store_verified_before_reload"] is True
    assert host["saved_row_selected_after_reload"] is True
    assert host["file_input_count_after_reload"] == 0
    assert host["remote_input_packets"] > 0 and guest["remote_input_packets"] > 0
    assert host["last_hash"] and host["last_hash"] == guest["last_hash"]
    assert host["controller_ram"] == guest["controller_ram"]
    if expected_ram is not None:
        assert host["controller_ram"] == expected_ram
    assert "Route: direct." in host["connection"] and "Route: direct." in guest["connection"]
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
        "host_received_inputs": host["remote_input_packets"],
        "guest_received_inputs": guest["remote_input_packets"],
        "matching_paused_hash": host["last_hash"],
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
                         *role_arguments, "--session-dir", str(session),
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

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(ignore_default_args=["--mute-audio"])
    try:
        page = browser.new_page(viewport={"width": 1366, "height": 682})
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
            store_verified_before_reload = page.wait_for_function('''async ({hash,size})=>{
              const db=await new Promise((resolve,reject)=>{const q=indexedDB.open('retro-coop-local',3);q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error)});
              const record=await new Promise((resolve,reject)=>{const q=db.transaction('roms').objectStore('roms').get(hash);q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error)});
              db.close();if(record?.sha256!==hash||record?.size!==size||record.bytes?.byteLength!==size||record.label!=='shared-game.nes')return false;
              const digest=await crypto.subtle.digest('SHA-256',record.bytes);
              return Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('')===hash;
            }''', arg={"hash": rom_hash, "size": len(rom)}, polling=50).json_value()
            assert store_verified_before_reload
            page.reload()
            page.get_by_test_id("create-game").wait_for(state="visible")
            file_input_count_after_reload = page.evaluate("document.querySelector('input[type=file]')?.files?.length")
            assert file_input_count_after_reload == 0
            saved_row = page.locator(".create-library li").filter(has_text="shared-game.nes")
            saved_row.get_by_role("button").wait_for(state="visible")
            assert "Saved" in saved_row.inner_text()
            saved_row.get_by_role("button").click()
            page.get_by_role("button", name="Create room", exact=True).wait_for()
            page.wait_for_function("!document.querySelector('.create-actions button')?.disabled", polling=50)
            assert page.locator(".create-options strong").inner_text() == "shared-game.nes"
            saved_row_selected_after_reload = True
            page.get_by_label("Room access").select_option(args.visibility)
            page.get_by_role("button", name="Create room", exact=True).click()
            page.get_by_test_id("room-view").wait_for(state="attached")
            page.wait_for_function("proof.room?.role==='host'", polling=50)
            room = page.evaluate("proof.room")
            assert room["occupancy"] == 1 and room["visibility"] == args.visibility
            assert "catalogId" not in room and room["romBytes"] == len(rom)
            assert page.get_by_role("button", name="Start game", exact=True).is_enabled()
            invitation=page.get_by_label("Room invitation").input_value() if args.visibility == "unlisted" else None
            save("host-ready.json", {"room_id": room["id"], "code": room.get("code"), "invitation": invitation})
            wait_for("guest-ready.json")
            page.wait_for_function(
                "proof.room?.guest && proof.room?.matches && proof.room?.game?.ready?.includes('guest')",
                timeout=30000,
                polling=50,
            )
            page.get_by_text("Guest is prepared. Start together when you are ready.", exact=True).wait_for()
            page.get_by_role("button", name="Start game", exact=True).click()
        else:
            expected = wait_for("host-ready.json")
            if args.visibility == "unlisted":
                page.goto(expected["invitation"])
                page.get_by_role("button", name="Join room", exact=True).click()
            else:
                search = page.get_by_label("Search room, game, host, or code")
                search.fill(expected["code"])
                # The room ID comes from the live directory; select that exact row.
                row = page.locator(f'.room-list li[data-room-id="{expected["room_id"]}"]')
                row.get_by_role("button", name="Join", exact=True).click()
            page.get_by_test_id("room-view").wait_for(state="attached")
            page.wait_for_function("proof.room?.role==='guest'", polling=50)
            assert page.evaluate("proof.room.id") == expected["room_id"]
            assert page.evaluate("!('catalogId' in proof.room) && proof.room.romBytes > 0")
            rom_hash = page.evaluate("proof.room.fingerprint.romSha256")
            page.get_by_role("button", name="Prepare to play", exact=True).wait_for(timeout=30000)
            page.wait_for_function("proof.room?.matches===true", timeout=30000, polling=50)
            page.get_by_role("button", name="Prepare to play", exact=True).click()
            save("guest-ready.json", {"room_id": expected["room_id"], "rom_sha256": rom_hash})

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
        page.keyboard.up("x" if args.role == "host" else "z")
        page.screenshot(path=str(session / f"{args.role}-playing.png"), full_page=True)
        if args.role == "host":
            wait_for("guest-200.json", 30)
            page.get_by_role("button", name="Pause", exact=True).click()
        else:
            save("guest-200.json", {"frames": page.evaluate("proof.frameCount")})
        page.wait_for_function("proof.room?.game?.status==='paused'", timeout=15000, polling=50)
        connection = page.get_by_test_id("connection-status").inner_text()
        assert "Route: direct." in connection
        page.wait_for_function("proof.hashes.length>0", timeout=15000, polling=50)
        page.locator(".room-panel").wait_for(state="visible")
        page.screenshot(path=str(session / f"{args.role}-room.png"), full_page=True)
        room = page.evaluate("proof.room")
        assert page.get_by_role("button", name="Ready to resume", exact=True).count() == 1
        assert page.get_by_role("button", name="Choose another file", exact=True).count() == 0
        page.get_by_role("button", name="Ready to resume", exact=True).focus()
        page.keyboard.press("Enter")
        page.wait_for_function("role => proof.room?.game?.ready?.includes(role)", arg=args.role, timeout=15000)
        page.locator("canvas").focus()
        assert page.locator("canvas").evaluate("node => node === document.activeElement")
        remote_inputs = page.evaluate("Object.values(proof.admission.lead).reduce((count, packets) => count + packets, 0)")
        assert remote_inputs > 0, "No remote controller input reached this browser"
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
            "frames": page.evaluate("proof.frameCount"),
            "remote_input_packets": remote_inputs,
            "last_hash": page.evaluate("proof.hashes.at(-1)"),
            "controller_ram": controller_ram,
            "connection": connection,
            "browser": browser.version,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "page_errors": errors,
            "rom_argument_received": args.rom is not None,
            "file_chooser_count": len(file_choosers),
            "store_verified_before_reload": store_verified_before_reload,
            "saved_row_selected_after_reload": saved_row_selected_after_reload,
            "file_input_count_after_reload": file_input_count_after_reload,
            "single_keyboard_resume_action": True,
            "back_to_game_focuses_canvas": True,
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
    finally:
        browser.close()
