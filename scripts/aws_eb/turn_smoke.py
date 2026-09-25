#!/usr/bin/env python3
"""Check TURN rendering and optionally prove an authenticated local allocation."""

import argparse
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--turnserver")
parser.add_argument("--turn-client")
args = parser.parse_args()
if args.turn_client and not args.turnserver:
    parser.error("--turn-client requires --turnserver")
render = Path(__file__).with_name("render_turn.py")
with tempfile.TemporaryDirectory(prefix="retro-turn-render-") as temporary:
    root = Path(temporary)
    secret = root / "secret"
    secret.write_text("a" * 64)
    secret.chmod(0o600)
    output = root / "turn.conf"
    command = [sys.executable, str(render), "--public-ip", "54.1.2.3", "--private-ip", "127.0.0.1", "--secret-file", str(secret), "--output", str(output)]
    subprocess.run(command, check=True)
    config = output.read_text()
    assert output.stat().st_mode & 0o077 == 0
    for expected in ["external-ip=54.1.2.3/127.0.0.1", "static-auth-secret=" + "a" * 64,
                     "total-quota=16", "bps-capacity=1600000", "min-port=49160", "max-port=49175",
                     "denied-peer-ip=169.254.0.0-169.254.255.255"]:
        assert expected in config
    for broken in [
        command,
        [*command[:2], "--public-ip", "127.0.0.1", *command[4:]],
        [*command[:4], "--private-ip", "0.0.0.0", *command[6:]],
        [*command[:4], "--private-ip", "8.8.8.8", *command[6:]],
    ]:
        assert subprocess.run(broken, capture_output=True).returncode != 0
    output.unlink()
    secret.chmod(0o644)
    assert subprocess.run(command, capture_output=True).returncode != 0
    secret.chmod(0o600)
    secret.write_text("a" * 64 + "\n")
    assert subprocess.run(command, capture_output=True).returncode != 0
    secret.write_text("a" * 64)
    if args.turnserver:
        with socket.socket() as unused:
            unused.bind(("127.0.0.1", 0))
            port = unused.getsockname()[1]
        subprocess.run([*command, "--runtime-dir", str(root), "--listen-port", str(port)], check=True)
        log_path = root / "turn.log"
        with log_path.open("wb") as log:
            process = subprocess.Popen([args.turnserver, "-c", str(output)], stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise AssertionError("coturn stopped during startup")
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=.2):
                            break
                    except OSError:
                        time.sleep(.05)
                else:
                    raise AssertionError("coturn startup deadline")
                if args.turn_client:
                    # A public peer is allowed by the production deny list; zero payload packets leave this host.
                    def allocation(secret_value):
                        return subprocess.run(
                            [args.turn_client, "-v", "-c", "-n", "0", "-e", "8.8.8.8",
                             "-p", str(port), "-W", secret_value, "127.0.0.1"],
                            capture_output=True, text=True, timeout=15,
                        )

                    valid = allocation("a" * 64)
                    if (valid.returncode != 0 or "Received relay addr: 54.1.2.3:" not in valid.stdout
                            or "clnet_allocate: rtv=0" not in valid.stdout):
                        raise AssertionError("Authenticated TURN allocation did not return the configured public relay address")
                    before_invalid = log_path.stat().st_size
                    invalid = allocation("b" * 64)
                    with log_path.open("rb") as evidence:
                        evidence.seek(before_invalid)
                        rejection_log = evidence.read().decode("utf-8", errors="replace")
                    terminal_failure = "ERROR: Cannot complete Allocation" in invalid.stdout
                    auth_rejection = "check_stun_auth: Cannot find credentials of user <" in rejection_log
                    if (invalid.returncode == 0 or "Received relay addr:" in invalid.stdout
                            or not terminal_failure or not auth_rejection):
                        raise AssertionError(
                            "Wrong-secret probe lacked terminal authentication rejection "
                            f"(exit={invalid.returncode}, terminal={terminal_failure}, server_auth={auth_rejection})"
                        )
            finally:
                process.terminate()
                process.wait(timeout=5)
checks = ["secret handling", "quotas", "relay ports"]
if args.turnserver:
    checks.append("local startup")
if args.turn_client:
    checks.extend(["authenticated allocation", "wrong-secret rejection"])
print("TURN render passed (" + ", ".join(checks) + ").")
