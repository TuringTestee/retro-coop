"""Reject missing shards and divergences that individually valid pairs cannot detect."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from verify_ci_matrix import verify_matrix

FIXTURE = Path(__file__).resolve().parents[2] / 'docs/implementation/d02/network-final-ci.json'


class MatrixEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.results = [entry['result'] for entry in json.loads(FIXTURE.read_text())['pairs']]
        for index, result in enumerate(self.results):
            self.write(index, result)

    def write(self, index, result):
        directory = self.root / str(index)
        directory.mkdir(exist_ok=True)
        (directory / 'pair.local.json').write_text(json.dumps(result))

    def test_complete_observed_matrix_passes(self):
        self.assertEqual(len(verify_matrix(self.root)), 3)

    def test_missing_and_duplicate_pairs_fail(self):
        (self.root / '2/pair.local.json').unlink()
        with self.assertRaisesRegex(ValueError, 'missing required'):
            verify_matrix(self.root)
        self.write(2, self.results[0])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            verify_matrix(self.root)

    def test_individually_agreeing_pair_cannot_diverge_from_matrix(self):
        result = copy.deepcopy(self.results[2])
        for run in result['runs']:
            run['hashes'][0]['hash'] = 'a' * 64
        self.write(2, result)
        with self.assertRaisesRegex(ValueError, 'cross-pair'):
            verify_matrix(self.root)

    def test_internally_matching_fingerprint_cannot_change_matrix_artifact(self):
        result = copy.deepcopy(self.results[2])
        result['wasm_sha256'] = 'b' * 64
        for run in result['runs']:
            identity = json.loads(run['identity'])
            identity['wasm'] = result['wasm_sha256']
            run['identity'] = json.dumps(identity)
        self.write(2, result)
        with self.assertRaisesRegex(ValueError, 'artifact identities'):
            verify_matrix(self.root)


if __name__ == '__main__':
    unittest.main()
