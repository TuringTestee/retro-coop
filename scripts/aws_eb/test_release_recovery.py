import io
import json
import subprocess
import unittest
from unittest.mock import patch

import release_recovery


PREVIOUS = 'main-111111111111'
ATTEMPTED = 'main-222222222222'


class RecoveryTests(unittest.TestCase):
    def recover(self, states, *, request_timeout=False, health=None, timeout=20):
        calls, clock = [], [0]
        states = iter(states)
        last = None

        def run(args, **kwargs):
            nonlocal last
            calls.append(args)
            operation = args[2]
            if operation == 'describe-application-versions':
                result = {'ApplicationVersions': [{'VersionLabel': PREVIOUS}]}
            elif operation == 'describe-environments':
                last = next(states, last)
                result = {'Environments': [last]}
            elif operation == 'update-environment':
                self.assertIn(PREVIOUS, args)
                if request_timeout:
                    raise subprocess.TimeoutExpired(args, 30)
                result = {}
            else:
                self.fail(f'Unexpected AWS operation {operation}')
            return subprocess.CompletedProcess(args, 0, json.dumps(result))

        def sleep(seconds):
            clock[0] += seconds

        def response(*args, **kwargs):
            self.assertEqual(args[0], 'https://example.test/healthz')
            if isinstance(health, Exception):
                raise health
            return io.StringIO(json.dumps(health or {'status': 'ok', 'service': 'retro-coop-coordinator'}))

        with patch.object(release_recovery.subprocess, 'run', side_effect=run), \
                patch.object(release_recovery.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(release_recovery.time, 'sleep', side_effect=sleep), \
                patch.object(release_recovery.urllib.request, 'urlopen', side_effect=response):
            result = release_recovery.restore_release('app', 'env', 'region', PREVIOUS,
                                                       ATTEMPTED, 'https://example.test', timeout)
        return result, calls

    def state(self, version, status='Ready', health='Green'):
        return {'VersionLabel': version, 'Status': status, 'Health': health}

    def test_failed_release_is_replaced_after_inflight_update_settles(self):
        result, calls = self.recover([self.state(ATTEMPTED, 'Updating'),
                                     self.state(ATTEMPTED, health='Red'),
                                     self.state(PREVIOUS, 'Updating'), self.state(PREVIOUS)])
        self.assertEqual(result['live'], PREVIOUS)
        self.assertTrue(result['restored'])
        self.assertEqual(sum(args[2] == 'update-environment' for args in calls), 1)

    def test_previous_healthy_release_does_not_restart(self):
        result, calls = self.recover([self.state(PREVIOUS)])
        self.assertFalse(result['restored'])
        self.assertFalse(any(args[2] == 'update-environment' for args in calls))

    def test_accepted_update_with_client_timeout_is_observed(self):
        result, calls = self.recover([self.state(ATTEMPTED), self.state(PREVIOUS)], request_timeout=True)
        self.assertEqual(result['live'], PREVIOUS)
        self.assertEqual(sum(args[2] == 'update-environment' for args in calls), 1)

    def test_unrelated_release_is_preserved(self):
        with self.assertRaisesRegex(ValueError, 'unexpected active version'):
            self.recover([self.state('main-333333333333')])

    def test_unhealthy_or_unreachable_restore_never_claims_success(self):
        for state, health in [(self.state(PREVIOUS, health='Red'), None),
                              (self.state(PREVIOUS), OSError('service unavailable'))]:
            with self.subTest(health=health), self.assertRaises(TimeoutError):
                self.recover([state], health=health)


if __name__ == '__main__':
    unittest.main()
