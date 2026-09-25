"""Publish readable full-suite evidence and fail if any workload is incomplete."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from ci_budget import api, timestamp


def verify(command):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--network-dir', type=Path, required=True)
    parser.add_argument('--core-dir', type=Path, required=True)
    args = parser.parse_args()
    source = os.environ.get('GITHUB_SHA', 'unknown')
    run = os.environ.get('GITHUB_RUN_ID', 'unknown')
    repo = os.environ.get('GITHUB_REPOSITORY', 'unknown')
    print('# Post-release qualification')
    print(f'\nSource: `{source}` · [Actions run](https://github.com/{repo}/actions/runs/{run})')
    statuses = {name: os.environ.get(f'D02_{name.upper()}', 'unknown') for name in ('fixture', 'core', 'network')}
    print('\n| Workload | Result |')
    print('| --- | --- |')
    for name, status in statuses.items():
        print(f'| {name} | {status} |')
    failures = [name for name, status in statuses.items() if status != 'success']
    try:
        jobs = api('/jobs?filter=latest&per_page=100')['jobs']
        observed = [job for job in jobs if job['name'] == 'core' or job['name'].startswith('network (')]
        print('\n| Browser job | Conclusion | Elapsed |')
        print('| --- | --- | ---: |')
        for job in sorted(observed, key=lambda item: item['name']):
            start, end = job.get('started_at'), job.get('completed_at')
            elapsed = f'{(timestamp(end) - timestamp(start)):.0f}s' if start and end else 'unfinished'
            print(f'| {job["name"]} | {job.get("conclusion") or job["status"]} | {elapsed} |')
    except (KeyError, OSError, ValueError, TypeError) as error:
        print(f'\nPer-job timings unavailable: {type(error).__name__}. The Actions run retains each job log.')
    print('\nThe three network jobs each run 600 seconds of game traffic and 600 seconds of independent probe traffic. The complete core suite runs separately. All jobs share the original 30-minute deadline.')
    if statuses['network'] == 'success':
        checks = [
            [sys.executable, 'spikes/d02/verify_ci_matrix.py', str(args.network_dir)],
            [sys.executable, 'scripts/gameplay/verify_matrix.py', str(args.network_dir), '--seconds', '600'],
        ]
        for command in checks:
            passed, output = verify(command)
            print(f'\n`{" ".join(command)}`: {"PASS" if passed else "FAIL"}. {output}')
            if not passed:
                failures.append(command[1])
        if not failures:
            print('\n| Browser pair | Game active time | Probe peer times |')
            print('| --- | ---: | ---: |')
            for path in sorted(args.network_dir.rglob('pair.local.json')):
                pair = json.loads(path.read_text())
                gameplay = next(path.parent.rglob('gameplay.json'))
                game = json.loads(gameplay.read_text())
                times = ', '.join(f'{peer["wallMs"] / 1000:.1f}s' for peer in pair['runs'])
                print(f'| {pair["pair"]} | {game["active_seconds"]:.1f}s | {times} |')
    if statuses['core'] == 'success':
        files = list(args.core_dir.rglob('browser-ci.local.json'))
        if len(files) != 1:
            failures.append('missing core browser evidence')
        else:
            core = json.loads(files[0].read_text())
            print('\nCore browser replay: ' + ', '.join(
                f'{item["browser"]} {item["wall_seconds"]:.1f}s' for item in core['runs']))
    if failures:
        print('\n**FAIL:** ' + ', '.join(failures) + '. Download the core and per-pair artifacts from this run for the partial results and logs.')
        return 1
    print('\n**PASS:** complete core and both 600-second network matrices. Evidence is attached to this Actions run.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
