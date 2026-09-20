"""Require all full peer pairs from isolated runners and matching canonical records."""
import argparse
import json
from pathlib import Path
from verify_realtime import require, verify


def verify_matrix(directory):
    observed = {}
    for path in directory.rglob('pair.local.json'):
        result = json.loads(path.read_text())
        pair = result['pair']
        require(pair not in observed, 'duplicate browser pair')
        verify(result, 600, require_muted=True)
        observed[pair] = result
    require(set(observed) == {'Chrome-Chrome', 'Firefox-Firefox', 'Chrome-Firefox'}, 'missing required browser pair')
    first = observed['Chrome-Chrome']['runs'][0]['hashes']
    identities = set()
    for result in observed.values():
        identities.add((result['rom_sha256'], result['wasm_sha256'], result['adapter_sha256']))
        require(all(run['hashes'] == first for run in result['runs']), 'cross-pair canonical divergence')
    require(len(identities) == 1, 'matrix artifact identities differ')
    return observed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    verify_matrix(args.directory)
    print('PASS: all three full isolated-runner pairs, six identical checkpoint lists and exact shared artifacts')
