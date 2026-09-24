#!/usr/bin/env python3
"""Check TURN rendering and a local coturn startup without publishing secrets."""

import argparse
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--turnserver")
args = parser.parse_args()
render = Path(__file__).with_name("render_turn.py")
with tempfile.TemporaryDirectory(prefix="retro-turn-render-") as temporary:
    root = Path(temporary)
    secret = root / "secret"
    secret.write_text("a" * 64)
    secret.chmod(0o600)
    output = root / "turn.conf"
    command = [sys.executable, str(render), "--public-ip", "34.100.1.2", "--private-ip", "127.0.0.1", "--secret-file", str(secret), "--output", str(output)]
    subprocess.run(command, check=True)
    config = output.read_text()
    assert output.stat().st_mode & 0o077 == 0
    for expected in ["external-ip=34.100.1.2/127.0.0.1", "static-auth-secret=" + "a" * 64,
                     "total-quota=8", "bps-capacity=400000", "min-port=49160", "max-port=49175"]:
        assert expected in config
    for broken in [
        command,
        [*command[:2], "--public-ip", "127.0.0.1", *command[4:]],
        [*command[:4], "--private-ip", "0.0.0.0", *command[6:]],
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
        subprocess.run([*command, "--runtime-dir", str(root)], check=True)
        with (root / "turn.log").open("wb") as log:
            process = subprocess.Popen([args.turnserver, "-c", str(output)], stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise AssertionError("coturn stopped during startup")
                    try:
                        with socket.create_connection(("127.0.0.1", 3478), timeout=.2):
                            break
                    except OSError:
                        time.sleep(.05)
                else:
                    raise AssertionError("coturn startup deadline")
            finally:
                process.terminate()
                process.wait(timeout=5)
print("TURN render passed (secret handling, quotas, relay ports and local startup).")
