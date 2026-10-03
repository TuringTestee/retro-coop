#!/usr/bin/env python3
"""Restore the recorded healthy release after a failed Elastic Beanstalk deployment."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request


def restore_release(application, environment, region, previous, attempted, site, timeout=240):
    if not all((application, environment, region, site)) or not site.startswith('https://') or timeout <= 0:
        raise ValueError('The application, environment, region and HTTPS site are required')
    if not all(re.fullmatch(r'main-[a-f0-9]{12}', version) for version in (previous, attempted)):
        raise ValueError('Recovery requires immutable main version labels')
    deadline = time.monotonic() + timeout

    def aws(*args):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Release recovery exceeded its deadline')
        result = subprocess.run(['aws', *args, '--region', region, '--output', 'json'],
                                check=True, capture_output=True, text=True, timeout=min(30, remaining))
        return json.loads(result.stdout or '{}')

    versions = aws('elasticbeanstalk', 'describe-application-versions', '--application-name', application,
                   '--version-labels', previous).get('ApplicationVersions', [])
    if len(versions) != 1 or versions[0].get('VersionLabel') != previous:
        raise ValueError('The recorded previous release does not exist in this application')
    restored = False
    health_error = None
    while time.monotonic() < deadline:
        rows = aws('elasticbeanstalk', 'describe-environments', '--application-name', application,
                   '--environment-names', environment).get('Environments', [])
        if len(rows) != 1:
            raise ValueError('The named release environment is missing or ambiguous')
        current = rows[0]
        version, status, health = (current.get(key) for key in ('VersionLabel', 'Status', 'Health'))
        if version not in (previous, attempted):
            raise ValueError(f'Refusing recovery over unexpected active version {version}')
        if status in ('Terminated', 'Terminating'):
            raise RuntimeError('The release environment is terminating')
        if status == 'Ready':
            if version == previous:
                if health == 'Green':
                    try:
                        with urllib.request.urlopen(site.rstrip('/') + '/healthz',
                                                    timeout=min(15, max(0.1, deadline-time.monotonic()))) as response:
                            result = json.load(response)
                        if result.get('status') != 'ok' or result.get('service') != 'retro-coop-coordinator':
                            raise ValueError('The restored site did not return the coordinator health response')
                        return {'previous': previous, 'attempted': attempted, 'live': version,
                                'restored': restored, 'health': health}
                    except (OSError, ValueError) as error:
                        health_error = str(error)
            elif not restored:
                try:
                    aws('elasticbeanstalk', 'update-environment', '--environment-name', environment,
                        '--version-label', previous)
                except subprocess.TimeoutExpired:
                    # A client timeout does not cancel the AWS update. Observe its result.
                    pass
                restored = True
        time.sleep(min(5, max(0, deadline-time.monotonic())))
    raise TimeoutError('The previous release did not become Ready/Green with healthy HTTPS '
                       f'before the recovery deadline{": " + health_error if health_error else ""}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', required=True)
    parser.add_argument('--attempted', required=True)
    args = parser.parse_args()
    summary = f'### Failed website release\n\nAttempted: {args.attempted}\n\nPrevious: {args.previous}\n\n'
    try:
        result = restore_release(os.environ.get('EB_APPLICATION_NAME'), os.environ.get('EB_ENVIRONMENT_NAME'),
                                 os.environ.get('AWS_REGION'), args.previous, args.attempted,
                                 os.environ.get('SITE_URL'))
        summary += f'Recovery verified: {result["live"]}, Ready/{result["health"]}, HTTPS healthy. '
        relation = 'differs from' if result['live'] != args.attempted else 'matches'
        summary += f'The deployment remains failed; the live site {relation} the attempted main revision.\n'
        print(json.dumps(result))
    except Exception as error:
        summary += f'Recovery failed: {error}. Inspect the environment before deploying again.\n'
        raise
    finally:
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as output:
                output.write(summary)


if __name__ == '__main__':
    main()
