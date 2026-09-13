"""Mutate a real diagnostic smoke result; never manufacture a full-session pass."""
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

from verify_realtime import verify


FIXTURE = Path(__file__).resolve().parents[2] / "docs/implementation/d02/network-smoke.json"


class EvidenceRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observed = json.loads(FIXTURE.read_text())

    def test_observed_smoke_is_explicitly_not_full_qualification(self):
        verify(self.observed, 10)
        with self.assertRaisesRegex(ValueError, "duration"):
            verify(self.observed)

    def test_matching_peers_cannot_omit_a_checkpoint(self):
        candidate = copy.deepcopy(self.observed)
        for run in candidate["runs"]:
            run["hashes"] = run["hashes"][1:]
        # Both lists still agree, and their reported comparison booleans are true.
        with self.assertRaisesRegex(ValueError, "checkpoints"):
            verify(candidate, 10)

    def test_corrupted_runtime_evidence_is_rejected(self):
        changes = [
            ("short workload", ("runs", 0, "frames"), 600),
            ("wrong checkpoint frame", ("runs", 0, "hashes", 0, "frame"), 599),
            ("peer divergence", ("runs", 1, "hashes", 0, "hash"), "0" * 64),
            ("wrong ROM", ("rom_sha256",), "0" * 64),
            ("wrong WASM", ("wasm_sha256",), "0" * 64),
            ("wrong adapter", ("adapter_sha256",), "0" * 64),
            ("reported failure", ("runs", 0, "errors"), ["runtime failed"]),
            ("lost PCM", ("runs", 0, "audio", "received"), 1),
            # The rendered prototype actually overflowed by 21,901 samples.
            ("observed overflow", ("runs", 0, "audio", "overflow"), 21901),
            ("stale epoch samples", ("runs", 0, "audio", "stale"), 799),
            ("silent receiver", ("runs", 0, "voiceLevels", "p50"), 0),
            ("own tone substituted", ("runs", 0, "voiceFrequencyHz", "p50"), 523),
            ("missing render measurements", ("runs", 0, "paintMs", "count"), 0),
            ("uncleared timeline", ("runs", 0, "flush", "queued"), 12),
            ("track left live", ("runs", 0, "teardown", "localTrack"), "live"),
            ("NaN energy", ("runs", 0, "audio", "energy"), float("nan")),
            ("wrong impairment", ("network_evidence", "netem_after", 0, "options", "loss-random", "loss"), 0),
            ("no actual drops", ("network_evidence", "netem_after", 0, "drops"), 0),
            ("wrong route", ("network_evidence", "route", 0, "dev"), "unimpaired"),
            ("no captured traffic", ("network_evidence", "udp_headers", "flows"), {}),
            ("mixed run sidecars", ("network_evidence", "run_id"), "another-concurrent-run"),
        ]
        for name, path, value in changes:
            with self.subTest(name=name):
                candidate = copy.deepcopy(self.observed)
                target = candidate
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.assertRaises(ValueError):
                    verify(candidate, 10)

    def test_source_audio_does_not_substitute_for_received_audio(self):
        candidate = copy.deepcopy(self.observed)
        candidate["runs"][0]["rtc"] = [
            stat for stat in candidate["runs"][0]["rtc"] if stat["type"] != "inbound-rtp"
        ]
        with self.assertRaisesRegex(ValueError, "inbound RTP"):
            verify(candidate, 10)

    def test_full_matrix_peer_reflexive_candidate_is_still_a_direct_route(self):
        matrix = json.loads(FIXTURE.with_name("network-matrix.json").read_text())
        self.assertEqual(matrix["error"], "missing active UDP host candidate pair")
        # Preserve the original verifier rejection; independently recheck its measured peers.
        for pair in matrix["pairs"]:
            verify(pair["result"])
        pair = matrix["pairs"][1]["result"]
        rtc = [s for s in pair["runs"][1]["rtc"] if s["type"] == "candidate-pair"]
        self.assertEqual(rtc[0]["remote"]["candidateType"], "prflx")
        for field, value in (("candidateType", "relay"), ("candidateType", "srflx"), ("protocol", "tcp")):
            with self.subTest(field=field, value=value):
                candidate = copy.deepcopy(pair)
                for stat in candidate["runs"][1]["rtc"]:
                    if stat["type"] == "candidate-pair":
                        stat["remote"][field] = value
                with self.assertRaisesRegex(ValueError, "direct UDP"):
                    verify(candidate)
        candidate = copy.deepcopy(pair)
        for stat in candidate["runs"][1]["rtc"]:
            if stat["type"] == "candidate-pair":
                stat["bytesReceived"] = 0
        with self.assertRaisesRegex(ValueError, "direct UDP"):
            verify(candidate)

    def test_cli_default_cannot_promote_smoke_to_full_pass(self):
        command = [sys.executable, str(Path(__file__).with_name("verify_realtime.py")), str(FIXTURE)]
        full = subprocess.run(command, capture_output=True, text=True, timeout=5)
        self.assertEqual(full.returncode, 1)
        self.assertIn("duration", full.stderr)
        smoke = subprocess.run(command + ["--seconds", "10"], capture_output=True, text=True, timeout=5)
        self.assertEqual(smoke.returncode, 0, smoke.stderr)
        self.assertIn("SMOKE ONLY", smoke.stdout)


if __name__ == "__main__":
    unittest.main()
