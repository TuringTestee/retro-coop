"""Keep CI commands inside the event's shared absolute run deadline."""
import argparse
import datetime
import json
import math
from pathlib import Path
import os
import signal
import subprocess
import sys
import time
import urllib.request

try:
    BUDGET_SECONDS = int(os.environ.get('D02_BUDGET_SECONDS', '1800'))
except ValueError as error:
    raise SystemExit('D02_BUDGET_SECONDS must be an integer') from error
if not 60 <= BUDGET_SECONDS <= 1800:
    raise SystemExit('D02_BUDGET_SECONDS must be between 60 and 1800')


ROOT = Path(__file__).resolve().parents[2]


def requires_product_checks(event, labels, paths):
    # Only known prose inputs may omit product validation. Empty/unknown scope,
    # workflow changes and the release gate retain the complete workload.
    if event != 'pull_request' or 'release-gate-proof' in labels or not paths:
        return True
    return any(not (path in {'README.md', 'AGENTS.md'} or
                        (path.startswith('docs/') and path.endswith('.md')))
               for path in paths)


def product_checks_selected():
    if os.environ.get('GITHUB_EVENT_NAME') != 'pull_request':
        return True
    try:
        event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        pr = event['pull_request']
        labels = [label['name'] for label in pr['labels']]
        base, head = pr['base']['sha'], pr['head']['sha']
        if not all(len(sha) == 40 and all(c in '0123456789abcdef' for c in sha)
                   for sha in (base, head)):
            raise ValueError('Invalid pull-request revisions')
        paths = subprocess.check_output(
            ['git', 'diff', '--no-renames', '--name-only', '-z', f'{base}...{head}'],
            cwd=ROOT, stderr=subprocess.PIPE).decode().split('\0')
        return requires_product_checks('pull_request', labels, [path for path in paths if path])
    except (KeyError, ValueError, TypeError, OSError, subprocess.CalledProcessError) as error:
        print(f'CI change scope unavailable; keeping full product checks: {error}', file=sys.stderr)
        return True


def selected_gates(product):
    if not product:
        return ['build']
    return ['entrypoint-' + suite for suite in
            ('journey', 'controls', 'ui', 'layout', 'recovery', 'save-load')] + ['images']


def timestamp(value):
    parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('GitHub timestamp must include a timezone')
    return parsed.timestamp()


def reject_retry():
    if os.environ.get('GITHUB_RUN_ATTEMPT') != '1':
        raise ValueError('CI retries cannot extend the original run budget')


def api(path, method='GET', timeout=15):
    token = os.environ['GH_TOKEN']
    repo = os.environ['GITHUB_REPOSITORY']
    run = os.environ['GITHUB_RUN_ID']
    if len(repo.split('/')) != 2 or not run.isdigit():
        raise ValueError('Invalid GitHub run identity')
    url = f'https://api.github.com/repos/{repo}/actions/runs/{run}{path}'
    request = urllib.request.Request(url, method=method, headers={
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    return json.loads(data) if data else None


def run_deadline():
    reject_retry()
    run = api('')
    if run.get('run_attempt') != 1:
        raise ValueError('API run attempt is not the original attempt')
    # run_started_at precedes the first job, conservatively including queue time.
    return timestamp(run['run_started_at']) + BUDGET_SECONDS


def remaining(deadline):
    if not math.isfinite(deadline) or deadline <= 0:
        raise ValueError('Invalid shared deadline')
    return max(0.0, deadline - time.time())


def namespace_command(command, ci=True):
    if ci:
        if os.environ.get('GITHUB_ACTIONS') != 'true':
            raise ValueError('Privileged CI namespace is forbidden outside GitHub Actions')
        prefix = ['sudo', '-n', '-E', 'unshare', '--pid', '--fork',
                  '--kill-child=KILL', '--mount-proc',
                  '--setuid', str(os.getuid()), '--setgid', str(os.getgid())]
    else:
        # Local regression only: no sudo or host configuration changes.
        prefix = ['unshare', '--user', '--map-current-user', '--pid', '--fork',
                  '--kill-child=KILL', '--mount-proc']
    return prefix + [sys.executable, str(Path(__file__).with_name('ci_namespace.py').resolve()),
                     str(os.getuid()), str(os.getgid()), os.environ.get('HOME', ''),
                     os.environ.get('PATH', ''), *command]


def run_command(deadline, command):
    reject_retry()
    if not command:
        raise ValueError('A command is required')
    if remaining(deadline) <= 0:
        return 124
    process = subprocess.Popen(command, start_new_session=True)
    try:
        code = process.wait(timeout=remaining(deadline))
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        # CI commands have a user-owned namespace PID 1 in this group.
        # Its death also kills detached/orphan descendants via the kernel.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        return 124
    if remaining(deadline) <= 0:
        return 124
    return code if code >= 0 else 128 - code


def watch(gate, poll_seconds=5):
    deadline = run_deadline()
    gates = [gate] if isinstance(gate, str) else list(gate)
    if not gates or len(gates) != len(set(gates)) or not all(gates) or not 0 < poll_seconds <= 10:
        raise ValueError('Gate and polling interval must be bounded')
    while remaining(deadline) > 0:
        try:
            jobs = api('/jobs?filter=latest&per_page=100',
                       timeout=min(15, remaining(deadline)))
            if jobs['total_count'] > 100:
                raise ValueError('Job count exceeds the bounded watchdog query')
            matches = {name: [job for job in jobs['jobs'] if job['name'] == name] for name in gates}
            if any(len(found) > 1 for found in matches.values()):
                raise ValueError('Final gate name must be unique')
            complete = [found[0] for found in matches.values() if found and found[0]['status'] == 'completed']
            if any(job['conclusion'] != 'success' or timestamp(job['completed_at']) >= deadline
                   for job in complete) or remaining(deadline) <= 0:
                return 1
            if len(complete) == len(gates):
                return 0
        except (OSError, TimeoutError):
            # A transient observation failure cannot reset or extend the clock.
            print('Watchdog observation unavailable; original deadline retained.',
                  file=sys.stderr)
        time.sleep(min(poll_seconds, remaining(deadline)))
    print('Shared CI deadline reached; cancelling this workflow.', file=sys.stderr)
    api('/cancel', method='POST')
    return 124


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('deadline')
    commands.add_parser('select')
    for name in ['check', 'run']:
        child = commands.add_parser(name)
        child.add_argument('--deadline', required=True, type=float)
        if name == 'run':
            child.add_argument('--namespace', action='store_true')
            child.add_argument('command', nargs=argparse.REMAINDER)
    child = commands.add_parser('watch')
    child.add_argument('--gate', action='append')
    child.add_argument('--selected-gates', action='store_true')
    args = parser.parse_args()
    reject_retry()
    if args.action == 'select':
        print('true' if product_checks_selected() else 'false')
        return 0
    if args.action == 'deadline':
        print(f'{run_deadline():.6f}')
        return 0
    if args.action == 'check':
        return 0 if remaining(args.deadline) > 0 else 124
    if args.action == 'watch':
        return watch(selected_gates(product_checks_selected()) if args.selected_gates
                     else args.gate or ['preflight'])
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if args.namespace:
        command = namespace_command(command)
    return run_command(args.deadline, command)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError) as error:
        print(f'CI budget error: {type(error).__name__}: {error}', file=sys.stderr)
        sys.exit(1)
