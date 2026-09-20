"""Reject misleading qualification claims using a real short production capture."""
import copy
import json
from pathlib import Path
import unittest
from verify import verify
import firefox_driver
from prepare_stock_firefox import VERSION, URL, ARCHIVE_SHA256, ARCHIVE_BYTES


class GameplayEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads((Path(__file__).resolve().parents[2] /
            'docs/implementation/d11/firefox-short.json').read_text())

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
