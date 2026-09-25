"""Reject misleading qualification claims using a real short production capture."""
import copy
import json
from pathlib import Path
import unittest
from verify import verify
from workload import active_seconds
from browser_errors import classify_page_errors
import firefox_driver
from prepare_stock_firefox import VERSION, URL, ARCHIVE_SHA256, ARCHIVE_BYTES


class GameplayEvidenceTests(unittest.TestCase):
    def test_only_early_recovered_firefox_socket_errors_are_diagnostics(self):
        socket = 'ws://127.0.0.1:41825/coordinator/ws'
        startup = [
            {'message': f'Firefox can’t establish a connection to the server at {socket}.', 'elapsed': 9.315},
            {'message': f'The connection to {socket} was interrupted while the page was loading.', 'elapsed': 9.315},
        ]
        late = {'message': startup[0]['message'], 'elapsed': 605.0}
        unrelated = {'message': 'Unexpected script failure', 'elapsed': 4.0}
        recovered, fatal = classify_page_errors([*startup, late, unrelated], socket, 12.0, True)
        self.assertEqual(recovered, startup)
        self.assertEqual(fatal, [late, unrelated])
        self.assertEqual(classify_page_errors(startup, socket, 12.0, False), ([], startup))
        self.assertEqual(classify_page_errors(startup, socket, 8.0, True), ([], startup))

    @classmethod
    def setUpClass(cls):
        cls.record = json.loads((Path(__file__).resolve().parents[2] /
            'docs/implementation/d11/firefox-short.json').read_text())

    def test_slow_manual_setup_cannot_consume_sustained_qualification(self):
        # Failed CI paused at frame 508 and produced 594 transitions, below 595.
        # Those manual setup frames must not shorten the resumed 600-second run.
        initial = 508 / 60
        self.assertLess(active_seconds(600, initial, 600 - initial), 600)
        self.assertEqual(active_seconds(600, initial, 600), 600)
        self.assertEqual(active_seconds(30, initial, 30), 30)
        self.assertEqual(active_seconds(8, 4, 4), 8)

    def test_one_missing_transition_still_fails_unchanged_acceptance(self):
        record = copy.deepcopy(self.record)
        required = max(1, (record['target_frames'] - 300) // 60)
        record['peers'][1]['scriptedInputs'] = required - 1
        with self.assertRaisesRegex(ValueError, 'missing sustained controller transitions'):
            verify(record, 30)

    def test_actual_short_capture_is_not_ten_minute_qualification(self):
        verify(self.record, 30)
        with self.assertRaisesRegex(ValueError, 'wrong workload'):
            verify(self.record, 600)

    def test_full_firefox_workload_requires_official_build(self):
        record=copy.deepcopy(self.record)
        record['target_seconds']=600
        with self.assertRaisesRegex(ValueError,'pinned official build'):
            verify(record,600)

    def test_official_browser_provenance_has_one_pinned_owner(self):
        record={'firefox_driver':firefox_driver.DRIVER,
                'firefox_executable_sha256':'a'*64,
                'firefox_build':{'version':VERSION,'source':URL,
                    'archive_sha256':ARCHIVE_SHA256,'archive_bytes':ARCHIVE_BYTES,
                    'binary_sha256':'a'*64}}
        firefox_driver.validate_evidence(record,VERSION)
        for key in ['version','source','archive_sha256','archive_bytes','binary_sha256']:
            changed=copy.deepcopy(record)
            changed['firefox_build'][key]='wrong'
            with self.assertRaises(ValueError):
                firefox_driver.validate_evidence(changed,VERSION)
        with self.assertRaises(ValueError):
            firefox_driver.validate_evidence(record,'unexpected version')

    def test_controlled_worker_latency_is_not_qualification(self):
        record=copy.deepcopy(self.record)
        record['controlled_worker_delivery_floor_ms']=14
        with self.assertRaisesRegex(ValueError,'controlled diagnostic'):
            verify(record,30)

    def test_equal_peers_cannot_hide_missing_checkpoint(self):
        record = copy.deepcopy(self.record)
        for peer in record['peers']:
            del peer['sentHashes'][1]
        with self.assertRaisesRegex(ValueError, 'missing or reordered'):
            verify(record, 30)

    def test_wrong_build_short_time_and_missing_input_are_rejected(self):
        mutations = (
            lambda r: r['identity'].update(coreSha256='0' * 64),
            lambda r: r.update(active_seconds=29.99),
            lambda r: r['peers'][1].update(scriptedInputs=0),
            lambda r: r['network_evidence'].update(run_id='different-run'),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                record = copy.deepcopy(self.record)
                mutate(record)
                with self.assertRaises(ValueError):
                    verify(record, 30)


if __name__ == '__main__':
    unittest.main()
