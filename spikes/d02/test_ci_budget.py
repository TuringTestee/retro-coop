"""Exercise shared time accounting, command termination and watchdog decisions."""
import contextlib
import io
import os
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch, Mock

import ci_budget as budget


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GITHUB_RUN_ATTEMPT': '1'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_api_start_includes_setup_and_queue(self):
        started = budget.timestamp('2026-09-13T00:00:00Z')
        with patch.object(budget, 'api', return_value={
                'run_attempt': 1, 'run_started_at': '2026-09-13T00:00:00Z'}):
            self.assertEqual(budget.run_deadline(),
                             started + budget.BUDGET_SECONDS)
        with self.assertRaises(ValueError):
            budget.timestamp('2026-09-13T00:00:00')

    def test_retry_cannot_reset_budget(self):
        with patch.dict(os.environ, {'GITHUB_RUN_ATTEMPT': '2'}):
            with self.assertRaises(ValueError):
                budget.run_command(time.time() + 10, ['true'])
        with patch.object(budget, 'api', return_value={'run_attempt': 2}):
            with self.assertRaises(ValueError):
                budget.run_deadline()

    def test_expired_command_never_starts_and_exit_status_survives(self):
        with patch.object(budget.subprocess, 'Popen') as start:
            self.assertEqual(budget.run_command(time.time() - 1, ['false']), 124)
            start.assert_not_called()
        self.assertEqual(budget.run_command(time.time() + 5,
                         [sys.executable, '-c', 'raise SystemExit(7)']), 7)

    def test_timeout_kills_entire_process_group(self):
        process = Mock(pid=4567)
        process.wait.side_effect = [subprocess.TimeoutExpired('test', 1), -9]
        with patch.object(budget.subprocess, 'Popen', return_value=process) as start:
            with patch.object(budget.os, 'killpg') as kill:
                self.assertEqual(budget.run_command(time.time() + 1, ['test']), 124)
                kill.assert_called_once_with(4567, signal.SIGKILL)
        start.assert_called_once_with(['test'], start_new_session=True)

    def test_real_command_deadline(self):
        started = time.monotonic()
        result = budget.run_command(time.time() + .15,
                                    [sys.executable, '-c', 'import time; time.sleep(10)'])
        self.assertEqual(result, 124)
        self.assertLess(time.monotonic() - started, 2)

    def test_shared_deadline_kills_foreground_timeout_descendant(self):
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            marker = pathlib.Path(directory) / 'completed'
            command = ['bash', '-c',
                       'timeout --foreground 5s python3 -c "$1"', 'budget-test',
                       'import time,pathlib; time.sleep(.6); pathlib.Path(' + repr(str(marker)) + ').touch()']
            self.assertEqual(budget.run_command(time.time() + .15, command), 124)
            time.sleep(.65)
            self.assertFalse(marker.exists(), 'workload escaped the shared process group')

    def test_ci_job_refuses_local_execution(self):
        import pathlib
        script = pathlib.Path(__file__).with_name('ci_job.sh')
        with patch.dict(os.environ, {'GITHUB_ACTIONS': ''}):
            result = subprocess.run(['bash', str(script), 'network'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(result.stderr, b'')

    def test_namespace_deadline_stops_detached_and_orphan_children(self):
        from ci_namespace_probe import probe
        with contextlib.redirect_stdout(io.StringIO()):
            probe(ci=os.environ.get('GITHUB_ACTIONS') == 'true')

    def test_privileged_namespace_is_ci_only(self):
        with patch.dict(os.environ, {'GITHUB_ACTIONS': ''}):
            with self.assertRaises(ValueError):
                budget.namespace_command(['true'])

    def test_late_success_is_failure(self):
        process = Mock()
        process.wait.return_value = 0
        with patch.object(budget.subprocess, 'Popen', return_value=process):
            with patch.object(budget, 'remaining', side_effect=[1, 1, 0]):
                self.assertEqual(budget.run_command(100, ['true']), 124)

    def test_watch_exits_on_named_successful_gate_only(self):
        jobs = {'total_count': 2, 'jobs': [
            {'name': 'other', 'status': 'completed', 'conclusion': 'failure'},
            {'name': 'preflight', 'status': 'completed', 'conclusion': 'success',
             'completed_at': '1970-01-01T00:01:30Z'},
        ]}
        with patch.object(budget, 'run_deadline', return_value=100):
            with patch.object(budget.time, 'time', return_value=95):
                with patch.object(budget, 'api', return_value=jobs) as api:
                    self.assertEqual(budget.watch('preflight'), 0)
                    self.assertEqual(api.call_count, 1)
                    jobs['jobs'][1]['completed_at'] = '1970-01-01T00:01:40Z'
                    self.assertEqual(budget.watch('preflight'), 1)
                    jobs['jobs'][1]['conclusion'] = 'failure'
                    self.assertEqual(budget.watch('preflight'), 1)

    def test_watch_requires_both_pr_gates_under_one_deadline(self):
        jobs = {'total_count': 2, 'jobs': [
            {'name': 'entrypoint', 'status': 'completed', 'conclusion': 'success',
             'completed_at': '1970-01-01T00:01:30Z'},
            {'name': 'images', 'status': 'completed', 'conclusion': 'success',
             'completed_at': '1970-01-01T00:01:31Z'},
        ]}
        with patch.object(budget, 'run_deadline', return_value=100):
            with patch.object(budget.time, 'time', return_value=95):
                with patch.object(budget, 'api', return_value=jobs):
                    self.assertEqual(budget.watch(['entrypoint', 'images']), 0)
                    jobs['jobs'][1]['conclusion'] = 'failure'
                    self.assertEqual(budget.watch(['entrypoint', 'images']), 1)
                    jobs['jobs'][1]['conclusion'] = 'success'
                    jobs['jobs'][1]['completed_at'] = '1970-01-01T00:01:40Z'
                    self.assertEqual(budget.watch(['entrypoint', 'images']), 1)
                    with self.assertRaises(ValueError):
                        budget.watch(['images', 'images'])

    def test_gate_response_arriving_after_deadline_fails(self):
        clock = [95.0]
        def api(*args, **kwargs):
            clock[0] = 101.0
            return {'total_count': 1, 'jobs': [{
                'name': 'preflight', 'status': 'completed',
                'conclusion': 'success', 'completed_at': '1970-01-01T00:01:30Z'}]}
        with patch.object(budget, 'run_deadline', return_value=100):
            with patch.object(budget.time, 'time', side_effect=lambda: clock[0]):
                with patch.object(budget, 'api', side_effect=api):
                    self.assertEqual(budget.watch('preflight'), 1)

    def test_observation_failure_does_not_extend_deadline(self):
        clock = [98.0]
        def sleep(seconds):
            clock[0] += seconds
        def api(path, **kwargs):
            if path.startswith('/jobs'):
                raise OSError('temporary observation failure')
            self.assertEqual(path, '/cancel')
            self.assertEqual(kwargs['method'], 'POST')
        with patch.object(budget, 'run_deadline', return_value=100):
            with patch.object(budget.time, 'time', side_effect=lambda: clock[0]):
                with patch.object(budget.time, 'sleep', side_effect=sleep):
                    with patch.object(budget, 'api', side_effect=api) as calls:
                        with contextlib.redirect_stderr(io.StringIO()):
                            self.assertEqual(budget.watch('preflight'), 124)
                        self.assertEqual(clock[0], 100)
                        self.assertEqual(calls.call_count, 2)

    def test_invalid_deadline_is_not_unbounded(self):
        for value in [float('nan'), float('inf'), -1]:
            with self.assertRaises(ValueError):
                budget.remaining(value)


if __name__ == '__main__':
    unittest.main()
