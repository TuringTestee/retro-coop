#!/usr/bin/env python3
"""Run the room download recovery browser journey against an isolated gateway."""
import json
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path)
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='retro-coop-integrated-roms-') as rom_dir:
    service = subprocess.Popen(
        ['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
        env={**os.environ, 'COORDINATOR_ROM_DIR': rom_dir},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        address = service.stdout.readline()
        if not address:
            raise RuntimeError('The isolated browser gateway did not start: ' + service.stderr.read())
        url = json.loads(address)['url']
        subprocess.run([
            sys.executable, 'scripts/rooms/guest_transfer_browser.py',
            '--url', url, '--fixture', 'apps/client/dist/generated/diagnostic.nes',
            '--rom-dir', rom_dir,
            *(['--output', str(args.output)] if args.output else []),
        ], cwd=ROOT, check=True, timeout=55)
    finally:
        service.terminate()
        try:
            service.wait(timeout=5)
        except subprocess.TimeoutExpired:
            service.kill()
            service.wait()
