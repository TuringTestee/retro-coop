"""Fail the gate unless both complete browser runs meet the D02 probe assertions."""
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text())
assert len(result["runs"]) == 2, "missing browser run"
assert result.get("cross_browser_hashes_equal") is True, "browser hash mismatch"
for run in result["runs"]:
    assert "error" not in run, run.get("error")
    assert [x["frame"] for x in run["hashes"]] == list(range(600, 36001, 600))
    assert run["restoreEqual"][1] and run["restoreEqual"][3], "hardware/video restore"
    assert all(run["newEpochEqual"]), "same checkpoint differs across prior histories"
    assert run["audioQueueEmpty"] and 700 <= run["lastAudioSamples"] <= 900
    assert run["checkpointBytes"] <= 2 * 1024 * 1024
    rewind = run["rewind"]
    assert rewind["retained_snapshots"] == 601 and rewind["frames_rewound"] == 600
    assert rewind["tracked_allocation_bytes"] <= 32 * 1024 * 1024
    assert rewind["canonical_replay_equal"]
print("PASS: complete 36,000-frame browser hashes, hardware restore, new audio epoch, 600-frame rewind and size bounds.")
