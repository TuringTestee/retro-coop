"""Reject misleading qualification claims using a real short production capture."""
import copy
import json
from pathlib import Path
import unittest
from verify import verify


class GameplayEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads((Path(__file__).resolve().parents[2] /
            'docs/agent/d11/firefox-short.json').read_text())

    def test_actual_short_capture_is_not_ten_minute_qualification(self):
        verify(self.record, 30)
        with self.assertRaisesRegex(ValueError, 'wrong workload'):
            verify(self.record, 600)

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
