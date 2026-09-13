"""Run all three full peer pairs concurrently within one fixed 900-second budget."""
import argparse
import json
import subprocess
import time
import uuid
from pathlib import Path
from verify_realtime import verify

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('rom', type=Path)
parser.add_argument('--bundled-chromium', action='store_true')
parser.add_argument('--firefox-executable', type=Path)
parser.add_argument('--output', type=Path, default=Path('network-matrix.local.json'))
args = parser.parse_args()
started = time.monotonic()
directory = Path('.network-runs')/('matrix-'+str(uuid.uuid4()))
directory.mkdir(parents=True)
children = []
result = {'scope': 'Three full 600-second pairs, concurrent on one host', 'pairs': []}
try:
    for pair in ['Chrome-Chrome', 'Firefox-Firefox', 'Chrome-Firefox']:
        output = directory/(pair+'.json')
        log = (directory/(pair+'.log')).open('w')
        command = ['sh', 'run_network_probe.sh', str(args.rom.resolve()), '--seconds', '600',
                   '--pair', pair, '--output', str(output.resolve())]
        if args.bundled_chromium:
            command.append('--bundled-chromium')
        if args.firefox_executable:
            command.extend(['--firefox-executable', str(args.firefox_executable.resolve())])
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        children.append((pair, process, output, log))
    while any(process.poll() is None for _, process, _, _ in children):
        for pair, process, output, _ in children:
            if process.poll() is not None:
                if process.returncode != 0:
                    raise RuntimeError('Pair failed: '+pair)
                # A verifier-only rejection must not discard independent peers still finishing.
                # Verify all completed outputs after every process exits.
        if time.monotonic()-started >= 900:
            raise TimeoutError('Shared matrix deadline exceeded')
        print(json.dumps({'wall_seconds': round(time.monotonic()-started, 1),
                          'processes': {pair: process.poll() for pair, process, _, _ in children}}), flush=True)
        time.sleep(10)
    for pair, process, output, _ in children:
        entry = {'pair': pair, 'exit_code': process.returncode}
        if output.exists():
            entry['result'] = json.loads(output.read_text())
        result['pairs'].append(entry)
        if process.returncode != 0:
            raise RuntimeError('Pair failed: '+pair)
        verify(entry['result'], 600, require_muted=True)
    result['all_pairs_verified'] = True
except Exception as error:
    result['error'] = str(error)
finally:
    import os
    import signal
    for _, process, _, log in children:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        log.close()
    # Preserve every available failure result, including pairs not yet inspected.
    existing = {entry['pair'] for entry in result['pairs']}
    for pair, process, output, _ in children:
        if pair not in existing:
            entry = {'pair': pair, 'exit_code': process.returncode}
            if output.exists():
                entry['result'] = json.loads(output.read_text())
            result['pairs'].append(entry)
    result['wall_seconds'] = time.monotonic()-started
    args.output.write_text(json.dumps(result, indent=2)+'\n')
if not result.get('all_pairs_verified'):
    raise SystemExit(result.get('error', 'Matrix failed'))
print('PASS: all three full 600-second pairs, including packet impairment, voice and bounded audio.')
