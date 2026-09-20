"""Verify paired emulator/audio evidence; ten seconds is explicitly smoke-only."""
import argparse
import json
import math
import re
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def verify(result, seconds=600, require_muted=False):
    require(seconds in (10, 600), "only explicit 10-second smoke or full 600-second runs")
    require(result.get("seconds") == seconds, "duration differs from requested verification scope")
    require("error" not in result, "probe reported an error")
    require(digest(result["adapter_sha256"]), "missing JS adapter identity")
    require(digest(result["rom_sha256"]) and digest(result["wasm_sha256"]), "missing content/build identity")
    runs = result["runs"]
    require(len(runs) == 2 and [r["role"] for r in runs] == [0, 1], "two ordered player roles required")
    pair = result["pair"].split("-")
    require(pair in (["Chrome", "Chrome"], ["Chrome", "Firefox"], ["Firefox", "Firefox"]), "unknown browser pair")
    frames = math.ceil(seconds * 60.0988)
    checkpoints = list(range(600, frames + 1, 600))
    if not checkpoints or checkpoints[-1] != frames:
        checkpoints.append(frames)
    expected_identity = {"adapter": result["adapter_sha256"], "rom": result["rom_sha256"], "wasm": result["wasm_sha256"],
                         "protocol": "D02-RT1", "region": "NTSC", "input_lead": 12}
    for role, run in enumerate(runs):
        require(run["browser"].replace("Chromium", "Chrome") == pair[role] and bool(run["version"]), "browser identity")
        require(run["seconds"] == seconds and run["frames"] == frames, "incomplete frame workload")
        require(number(run["wallMs"]) and seconds * 1000 <= run["wallMs"] <= (seconds + 120) * 1000,
                "real-time duration outside full workload/deadline")
        require(run["errors"] == [] and run["identityMatched"] is True, "runtime or handshake failure")
        require(json.loads(run["identity"]) == expected_identity, "ROM/WASM/protocol fingerprint mismatch")
        hashes = run["hashes"]
        require([h["frame"] for h in hashes] == checkpoints, "missing, repeated, or wrong-frame checkpoints")
        require(all(set(h) == {"frame", "hash"} and digest(h["hash"]) for h in hashes), "invalid checkpoint digest")
        require(run["peerHashesMatched"] is True, "peer did not acknowledge matching checkpoint hashes")
        require(run["pendingInputs"] == 0 and run["remoteInputQueue"] == 0, "undrained final inputs")
        require(0 <= run["maxBuffered"] <= 65536 and 0 <= run["maxRemoteInputs"] <= 121, "unbounded transport queue")
        require(run["audioSampleRate"] == 48000, "unexpected audio sample rate")
        if require_muted:
            require(run.get("outputMuted") is True and number(run.get("outputPeak")) and run["outputPeak"] == 0,
                    "application output is not measured muted")
        audio = run["audio"]
        for key in ("received", "played", "underrun", "overflow", "maxQueued", "stale", "flushes", "flushed", "queued"):
            require(type(audio[key]) is int and audio[key] >= 0, "invalid audio counter: " + key)
        require(audio["capacity"] == 12000 and audio["queued"] <= audio["maxQueued"] <= 12000, "audio buffer bound")
        require(audio["overflow"] == 0 and audio["stale"] == 0, "lost or stale-epoch audio samples")
        require(audio["received"] == audio["played"] + audio["flushed"] + audio["queued"] + audio["overflow"],
                "audio sample accounting differs")
        require(frames * 700 <= audio["received"] <= frames * 900 and audio["played"] > 0, "missing full-frame PCM")
        require(number(audio["energy"]) and audio["energy"] > 0, "silent game-audio output")
        require(run["coreQueueEmpty"] is True and run["flush"] == {"kind": "flushed", "epoch": 1, "queued": 0},
                "timeline jump did not clear the core and presentation queues")
        require(audio["flushes"] == 1 and audio["epoch"] == 1, "audio epoch mismatch")
        for key in ("emulateMs", "copyMs", "paintMs", "transferMs"):
            require(run[key]["count"] == frames, "missing per-frame measurements: " + key)
        levels, frequency = run["voiceLevels"], run["voiceFrequencyHz"]
        require(levels["count"] >= seconds - 1 and frequency["count"] >= seconds - 1, "insufficient voice observations")
        require(all(number(levels[k]) and levels[k] > 0.001 for k in ("p50", "max")), "remote voice remains silent")
        require(number(frequency["p50"]) and abs(frequency["p50"] - (659 if role == 0 else 523)) <= 60,
                "received tone is not the other player's source")
        require(number(run["voiceEnableToEnergyMs"]) and run["voiceEnableToEnergyMs"] > 0, "missing voice startup measurement")
        require(any(s["type"] == "inbound-rtp" and s.get("kind") == "audio"
                    and number(s.get("packetsReceived")) and s["packetsReceived"] > 0
                    and number(s.get("totalSamplesReceived")) and s["totalSamplesReceived"] > 0 for s in run["rtc"]),
                "no decoded inbound RTP audio evidence")
        # RFC 8445 section 7.3.1.3 permits peer-reflexive candidates learned by checks.
        # The separate namespace route, qdisc and bidirectional capture remain mandatory.
        require(any(s["type"] == "candidate-pair" and s["local"]["protocol"] == "udp"
                    and s["remote"]["protocol"] == "udp" and s["local"]["candidateType"] in ("host", "prflx")
                    and s["remote"]["candidateType"] in ("host", "prflx") and s["bytesSent"] > 0 and s["bytesReceived"] > 0
                    for s in run["rtc"]), "missing active direct UDP candidate pair")
        teardown = run["teardown"]
        require(teardown["localTrack"] == "ended" and teardown["connection"] == "closed"
                and teardown["audio"] == "closed" and teardown["remoteElementPaused"] is True, "incomplete media teardown")
    require(result["canonical_equal"] is True and runs[0]["hashes"] == runs[1]["hashes"], "canonical peer divergence")
    verify_network_evidence(result, seconds)


def verify_network_evidence(result, seconds):
    """Validate the shared actual-packet impairment proof for a uniquely bound run."""
    evidence = result["network_evidence"]
    require(isinstance(result["run_id"], str) and bool(result["run_id"])
            and evidence["run_id"] == result["run_id"], "network evidence belongs to another run")
    before, after = evidence["netem_before"], evidence["netem_after"]
    require(len(before) == len(after) == 1, "ambiguous qdisc evidence")
    for qdisc in (before[0], after[0]):
        require(qdisc["kind"] == "netem" and qdisc["root"] is True, "missing root netem")
        options = qdisc["options"]
        require(options["delay"]["delay"] == 0.05 and options["delay"]["jitter"] == 0.01
                and options["loss-random"]["loss"] == 0.01, "wrong packet delay/jitter/loss configuration")
    require(before[0]["handle"] == after[0]["handle"], "qdisc replaced during run")
    require(after[0]["drops"] > before[0]["drops"] and after[0]["packets"] > before[0]["packets"], "no measured packet impairment")
    require(any(r["dev"] == "lo" and r["dst"] == "10.201.0.1" and r["type"] == "local" for r in evidence["route"]),
            "peer address does not traverse impaired loopback")
    capture = evidence["udp_headers"]
    require(number(capture["wall_seconds"]) and capture["wall_seconds"] >= seconds, "capture did not span workload")
    flows = capture["flows"]
    observed = set()
    for flow, counters in flows.items():
        match = re.fullmatch(r"10\.201\.0\.1:(\d+)>10\.201\.0\.1:(\d+)", flow)
        if match and counters["observations"] > 0 and counters["udp_bytes"] > 0:
            one, two = map(int, match.groups())
            if 0 < one <= 65535 and 0 < two <= 65535 and one != two:
                observed.add((one, two))
    require(any((two, one) in observed for one, two in observed), "no bidirectional private-address UDP capture")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--seconds", type=int, choices=(10, 600), default=600)
    parser.add_argument("--require-muted", action="store_true", help="Require actual post-gain silence; historical runs did not measure this")
    parser.add_argument("--network-dir", type=Path,
                        help="Bundle this run's finished sidecars before another run overwrites them")
    args = parser.parse_args()
    try:
        result = json.loads(args.result.read_text())
        if args.network_dir:
            require("network_evidence" not in result, "refusing to overwrite already bundled network evidence")
            names = {"netem_before": "netem-before.local.json", "netem_after": "netem-after.local.json",
                     "route": "route.local.json", "udp_headers": "udp-headers.local.json"}
            result["network_evidence"] = {key: json.loads((args.network_dir / name).read_text()) for key, name in names.items()}
            result["network_evidence"]["run_id"] = json.loads((args.network_dir / "run-id.local.json").read_text())["run_id"]
            require(result["network_evidence"]["run_id"] == result["run_id"], "sidecars belong to another run")
            # Preserve captured failures too; success is decided only by verify().
            args.result.write_text(json.dumps(result, indent=2) + "\n")
        verify(result, args.seconds, require_muted=args.require_muted)
    except (ValueError, KeyError, TypeError, IndexError, OSError) as error:
        parser.exit(1, "FAIL: " + str(error) + "\n")
    scope = "SMOKE ONLY (10 seconds)" if args.seconds == 10 else "FULL 600-second paired experiment"
    print("PASS: " + scope + "; checkpoint agreement, bounded audio, received peer tone, packet impairment and teardown.")


if __name__ == "__main__":
    main()
