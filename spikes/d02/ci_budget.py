"""Keep every presubmit command inside one conservative 30-minute run deadline."""
import argparse
import datetime
import json
import math
import os
import signal
import subprocess
import sys
import time
import urllib.request

BUDGET_SECONDS = 1800


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
        # Kill descendants too: stopping only a launcher leaves browser tests alive.
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
    if not gate or not 0 < poll_seconds <= 10:
        raise ValueError('Gate and polling interval must be bounded')
    while remaining(deadline) > 0:
        try:
            jobs = api('/jobs?filter=latest&per_page=100',
                       timeout=min(15, remaining(deadline)))
            if jobs['total_count'] > 100:
                raise ValueError('Job count exceeds the bounded watchdog query')
            matches = [job for job in jobs['jobs'] if job['name'] == gate]
            if len(matches) > 1:
                raise ValueError('Final gate name must be unique')
            if matches and matches[0]['status'] == 'completed':
                job = matches[0]
                in_budget = (timestamp(job['completed_at']) < deadline
                             and remaining(deadline) > 0)
                return 0 if in_budget and job['conclusion'] == 'success' else 1
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
    for name in ['check', 'run']:
        child = commands.add_parser(name)
        child.add_argument('--deadline', required=True, type=float)
        if name == 'run':
            child.add_argument('command', nargs=argparse.REMAINDER)
    child = commands.add_parser('watch')
    child.add_argument('--gate', default='preflight')
    args = parser.parse_args()
    reject_retry()
    if args.action == 'deadline':
        print(f'{run_deadline():.6f}')
        return 0
    if args.action == 'check':
        return 0 if remaining(args.deadline) > 0 else 124
    if args.action == 'watch':
        return watch(args.gate)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    return run_command(args.deadline, command)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError) as error:
        print(f'CI budget error: {type(error).__name__}: {error}', file=sys.stderr)
        sys.exit(1)
