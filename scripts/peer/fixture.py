"""Run-local coturn fixture shared by browser verification, never a public service."""

import collections
import re
import secrets
import socket
import subprocess
import tempfile
import time
from pathlib import Path


class LocalTurn:
    def __init__(self, executable="turnserver"):
        self.executable = executable
        self.process = None
        self.directory = None

    def __enter__(self):
        self.directory = tempfile.TemporaryDirectory(prefix="retro-peer-")
        path = Path(self.directory.name)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.secret = secrets.token_hex(32)
        config = path / "turn.conf"
        config.write_text(
            f"""listening-ip=127.0.0.1
relay-ip=127.0.0.1
listening-port={self.port}
min-port=49200
max-port=49249
realm=retro-coop-local
use-auth-secret
static-auth-secret={self.secret}
user-quota=4
total-quota=16
relay-threads=1
max-bps=100000
bps-capacity=1600000
allow-loopback-peers
no-multicast-peers
no-cli
no-tls
no-dtls
no-tcp-relay
no-software-attribute
pidfile={path}/turn.pid
log-file=stdout
"""
        )
        config.chmod(0o600)
        self.log = path / "turn.log"
        try:
            with self.log.open("w") as log:
                self.process = subprocess.Popen(
                    [self.executable, "-v", "-c", str(config)],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            deadline = time.monotonic() + 10
            while True:
                assert self.process.poll() is None, "coturn stopped during startup"
                try:
                    with socket.create_connection(
                        ("127.0.0.1", self.port), timeout=0.2
                    ):
                        return self
                except OSError:
                    assert time.monotonic() < deadline, "coturn startup deadline"
                    time.sleep(0.05)
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def environment(self):
        return {
            "TURN_URLS": f"turn:127.0.0.1:{self.port}?transport=udp",
            "TURN_SECRET": self.secret,
            "TURN_ROOM_LIMIT": "1",
        }

    def error_codes(self):
        # Only numeric codes leave the private temporary directory.
        return dict(
            collections.Counter(
                re.findall(r"error (\d{3})", self.log.read_text(errors="replace"))
            )
        )

    def __exit__(self, *_):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.directory:
            self.directory.cleanup()
