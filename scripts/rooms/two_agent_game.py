"""Two independent browser processes join and play the same public NES room.

Run the host and guest roles concurrently against one browser-server.ts URL, each
in its own process. The shared directory carries only rendezvous and proof data;
the NES bytes are loaded separately by each browser and never sent to the room.
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
parser.add_argument("--rom", type=Path, help="The same local .nes file on both agents")
parser.add_argument("--session-dir", type=Path, required=True)
args = parser.parse_args()
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
    assert host["room_code"] == guest["room_code"]
    assert host["rom_sha256"] == guest["rom_sha256"]
    assert host["game_status"] == guest["game_status"] == "paused"
    assert host["started"] == guest["started"] == "shared"
    assert host["established"] and guest["established"]
    assert host["frames"] >= 120 and guest["frames"] >= 120
    assert host["last_hash"] and host["last_hash"] == guest["last_hash"]
    assert "Route: direct." in host["connection"] and "Route: direct." in guest["connection"]
    assert not host["page_errors"] and not guest["page_errors"]
    assert all((session / f"{role}-{view}.png").stat().st_size > 0
               for role in ("host", "guest") for view in ("playing", "room"))
    result = {
        "result": "pass",
        "claim": "Two independent browser processes joined and played one public game",
        "room_id": host["room_id"],
        "room_code": host["room_code"],
        "rom_sha256": host["rom_sha256"],
        "host_frames": host["frames"],
        "guest_frames": guest["frames"],
        "matching_paused_hash": host["last_hash"],
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
                    worker = subprocess.Popen(
                        [sys.executable, __file__, "--role", role, "--url", url,
                         "--rom", str(args.rom.resolve()), "--session-dir", str(session)],
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
if not args.url or not args.rom:
    parser.error("host and guest need --url and --rom")
rom = args.rom.read_bytes()
rom_hash = hashlib.sha256(rom).hexdigest()
errors = []
started = time.monotonic()

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(ignore_default_args=["--mute-audio"])
    try:
        page = browser.new_page(viewport={"width": 1280, "height": 900})
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
        selection = {
            "name": "shared-game.nes",
            "mimeType": "application/octet-stream",
            "buffer": rom,
        }

        if args.role == "host":
            page.get_by_label("Room access").select_option("public")
            page.set_input_files("input[type=file]", selection)
            page.get_by_test_id("room-view").wait_for(state="attached")
            page.wait_for_function("proof.room?.role==='host' && proof.room?.code", polling=50)
            room = page.evaluate("proof.room")
            assert room["occupancy"] == 1 and room["visibility"] == "public"
            assert page.get_by_role("button", name="Start game", exact=True).is_enabled()
            save("host-ready.json", {"room_id": room["id"], "code": room["code"], "rom_sha256": rom_hash})
            wait_for("guest-ready.json")
            page.wait_for_function(
                "proof.room?.guest && proof.room?.matches && proof.room?.game?.ready?.includes('guest')",
                timeout=30000,
                polling=50,
            )
            page.get_by_text("Guest is ready. Start together when you are ready.", exact=True).wait_for()
            page.get_by_role("button", name="Start game", exact=True).click()
        else:
            expected = wait_for("host-ready.json")
            assert expected["rom_sha256"] == rom_hash, "Agents selected different ROM bytes"
            search = page.get_by_label("Search room, game, host, or code")
            search.fill(expected["code"])
            # The room ID comes from the live directory; select that exact row.
            row = page.locator(f'.room-list li[data-room-id="{expected["room_id"]}"]')
            row.get_by_role("button", name="Join", exact=True).click()
            page.get_by_test_id("room-view").wait_for(state="attached")
            page.wait_for_function("proof.room?.role==='guest'", polling=50)
            assert page.evaluate("proof.room.id") == expected["room_id"]
            page.set_input_files("input[type=file]", selection)
            page.wait_for_function("proof.room?.matches===true", timeout=30000, polling=50)
            save("guest-ready.json", {"room_id": expected["room_id"], "rom_sha256": rom_hash})

        page.wait_for_function(
            "proof.room?.established && proof.room?.started==='shared' && proof.room?.game?.status==='playing'",
            timeout=30000,
            polling=50,
        )
        assert page.evaluate("proof.room.fingerprint.romSha256") == rom_hash
        connection = page.get_by_test_id("connection-status").inner_text()
        assert "Route: direct." in connection
        page.evaluate("releaseFrames()")
        page.locator("canvas").focus()
        page.keyboard.down("x" if args.role == "host" else "z")
        page.wait_for_function("proof.frameCount>=120", timeout=30000, polling=50)
        page.keyboard.up("x" if args.role == "host" else "z")
        page.screenshot(path=str(session / f"{args.role}-playing.png"), full_page=True)
        if args.role == "host":
            wait_for("guest-120.json", 30)
            page.get_by_role("button", name="Pause", exact=True).click()
        else:
            save("guest-120.json", {"frames": page.evaluate("proof.frameCount")})
        page.wait_for_function("proof.room?.game?.status==='paused'", timeout=15000, polling=50)
        page.wait_for_function("proof.hashes.length>0", timeout=15000, polling=50)
        page.get_by_role("button", name="Room", exact=True).click()
        page.locator(".room-panel").wait_for(state="visible")
        page.screenshot(path=str(session / f"{args.role}-room.png"), full_page=True)
        room = page.evaluate("proof.room")
        evidence = {
            "result": "pass",
            "role": args.role,
            "room_id": room["id"],
            "room_code": room["code"],
            "rom_sha256": rom_hash,
            "started": room["started"],
            "game_status": room["game"]["status"],
            "established": room["established"],
            "frames": page.evaluate("proof.frameCount"),
            "last_hash": page.evaluate("proof.hashes.at(-1)"),
            "connection": connection,
            "browser": browser.version,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "page_errors": errors,
        }
        save(f"{args.role}.json", evidence)
        if args.role == "host":
            # Keep the host connected until the guest captures the intentional
            # paused state; closing early changes that state to peer loss.
            wait_for("guest.json", 15)
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
