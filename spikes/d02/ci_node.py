"""Install the pinned Linux CI runtime from Node's checksum-verified release."""
import argparse
import hashlib
from http.client import IncompleteRead, RemoteDisconnected
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.request import urlopen
from urllib.error import HTTPError, URLError


def download(url, destination, deadline):
    interrupted = (ConnectionResetError, ConnectionAbortedError, RemoteDisconnected, IncompleteRead)
    for attempt in range(3):
        remaining = deadline - time.time()
        if remaining <= 0:
            raise TimeoutError('No download time remains inside the shared deadline')
        try:
            with urlopen(url, timeout=min(10, remaining)) as response:
                if not response.geturl().startswith('https://nodejs.org/'):
                    raise ValueError('Node release redirected outside its official HTTPS origin')
                with destination.open('wb') as output:
                    shutil.copyfileobj(response, output)
                length = response.headers.get('Content-Length')
                if length is not None and destination.stat().st_size != int(length):
                    raise IncompleteRead(b'', int(length) - destination.stat().st_size)
            return
        except interrupted as error:
            failure = error
        except HTTPError as error:
            if error.code not in (408, 429, 500, 502, 503, 504):
                raise
            failure = error
        except URLError as error:
            if not isinstance(error.reason, interrupted):
                raise
            failure = error
        # TimeoutError is deliberately not caught: SIGALRM owns the total deadline.
        delay = 0.25 * (attempt + 1)
        if attempt == 2 or deadline - time.time() <= delay:
            raise failure
        print(f'Node download interrupted; retry {attempt + 1}/2: {failure}', file=sys.stderr)
        time.sleep(delay)


def verify_archive(archive, checksums):
    matches = [line.split()[0] for line in checksums.read_text().splitlines()
               if len(line.split()) == 2 and line.split()[1] == archive.name]
    if len(matches) != 1 or not re.fullmatch(r'[a-f0-9]{64}', matches[0]):
        raise ValueError('Official checksum must identify exactly one pinned archive')
    with archive.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != matches[0]:
        raise ValueError('Node archive checksum mismatch')
    return actual


def install(deadline):
    root = Path(__file__).resolve().parents[2]
    version = (root / '.node-version').read_text().strip()
    package = json.loads((root / 'package.json').read_text())
    npm_version = package['engines']['npm']
    if (not re.fullmatch(r'\d+\.\d+\.\d+', version)
            or not re.fullmatch(r'\d+\.\d+\.\d+', npm_version)
            or package['engines']['node'] != version
            or package['packageManager'] != f'npm@{npm_version}'):
        raise ValueError('Node/npm pins disagree; exact release versions are required')
    arch = {'x86_64': 'x64', 'aarch64': 'arm64', 'arm64': 'arm64'}.get(platform.machine())
    if platform.system() != 'Linux' or arch is None:
        raise ValueError('CI Node bootstrap supports Linux x64 and ARM64')
    path_file = Path(os.environ['GITHUB_PATH'])
    work = Path(tempfile.mkdtemp(prefix='retro-node-', dir=os.environ['RUNNER_TEMP']))
    release = f'node-v{version}-linux-{arch}'
    archive, checksums = work / f'{release}.tar.xz', work / 'SHASUMS256.txt'
    base = f'https://nodejs.org/dist/v{version}'
    try:
        download(f'{base}/SHASUMS256.txt', checksums, deadline)
        download(f'{base}/{archive.name}', archive, deadline)
        digest = verify_archive(archive, checksums)
        with tarfile.open(archive) as bundle:
            bundle.extractall(work, filter='data')
        binary = work / release / 'bin' / 'node'
        npm = work / release / 'lib/node_modules/npm/bin/npm-cli.js'
        node_actual = subprocess.check_output([binary, '--version'], text=True).strip()
        npm_actual = subprocess.check_output([binary, npm, '--version'], text=True).strip()
        if node_actual != f'v{version}' or npm_actual != npm_version:
            raise ValueError(f'Installed runtime differs from pins: {node_actual}, npm {npm_actual}')
        with path_file.open('a') as output:
            output.write(f'{binary.parent}\n')
        return {'node': node_actual, 'npm': npm_actual, 'arch': arch,
                'url': f'{base}/{archive.name}', 'sha256': digest,
                'bin': str(binary.parent)}
    except BaseException:
        shutil.rmtree(work)
        raise
    finally:
        archive.unlink(missing_ok=True)
        checksums.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deadline', type=float, required=True)
    args = parser.parse_args()
    started = time.time()
    if not math.isfinite(args.deadline):
        raise ValueError('A finite shared deadline is required')
    remaining = min(60, args.deadline - started)
    if not 0 < remaining <= 60:
        raise ValueError('No installation time remains inside the shared deadline')

    def expired(_signum, _frame):
        raise TimeoutError('Node installation exceeded its bounded deadline')

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, remaining)
    try:
        result = install(started + remaining)
        result['elapsed_seconds'] = round(time.time() - started, 3)
        print(json.dumps(result))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Node bootstrap failed: {error}', file=sys.stderr)
        sys.exit(1)
