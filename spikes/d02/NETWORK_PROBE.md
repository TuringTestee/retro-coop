This Linux experiment runs two real browsers through ten minutes of delayed controller inputs, rendered video, bounded Web Audio and a synthetic voice tone. Each pair uses an isolated kernel network namespace with packet delay and loss. It measures initial feasibility; it does not implement production rooms, shared restore consent, real microphones or public routes.

# Reproduce the bounded experiment

Build the WASM and original fixture using the main README. Install Playwright 1.58.0, its Firefox build and Chrome (or bundled Chromium with the explicit flag). Linux needs `unshare`, `ip`, `tc`, Python 3 and permission to create a user/network namespace. All interface, route and qdisc changes occur inside that namespace; the host network remains untouched. Hosted Ubuntu's AppArmor restriction is disabled only in the ephemeral CI runner before entering the namespace.

From `spikes/d02`:

```sh
node test_realtime_audio.cjs
node test_realtime_scheduler.cjs
python3 -m unittest test_verify_realtime.py
timeout 90s sh run_network_probe.sh fixture.local.nes --seconds 10 --pair Chrome-Firefox --output smoke.local.json
python3 verify_realtime.py smoke.local.json --seconds 10
timeout 900s python3 run_network_matrix.py fixture.local.nes --output network-matrix.local.json
```

The matrix runs Chrome–Chrome, Firefox–Firefox and Chrome–Firefox concurrently with independent namespaces and unique run IDs. Every pair must execute 36,060 frames over at least 600 real seconds, compare canonical state at each 600-frame boundary and the final frame, and pass strict audio, voice, packet and teardown checks. The outer 900-second deadline includes setup. Ten-second mode is explicitly smoke-only and is rejected by default verification. The driver and matrix preserve failed measurements and fail the command; neither skipped frames nor a shorter duration can pass. A run needs sufficient CPU/memory for six browser processes. CI retains the same full workload and the overall 30-minute job deadline.

Each run stores separate `.network-runs/<UUID>/` sidecars. A matching UUID ties the output pointer, result and packet evidence together before bundling. The header collector stores only private-address UDP port/count/length observations, never packet payloads. Keep all pair outputs distinct. Do not edit the four adapter assets during a matrix: their exact content is hashed into the peer identity alongside the WASM and local ROM hashes.

The original fixture is generated locally. A separately authorized ROM can be supplied as the positional path; keep it outside the served directory and do not publish the private path or bytes. The driver reads it locally and supplies it to each browser through automation. Peer messages carry only fingerprints, two-controller inputs, pings and hashes, with a 512-character message bound. This is an automated developer harness, not a production file validator or signaling service.

# What is measured

Each peer sends inputs twelve frames ahead on a reliable ordered WebRTC data channel. Both controller masks must exist before the same frame advances. A 150 ms initial playout warmup is explicit. Packet impairment is 50 ms delay with 10 ms jitter and 1% random loss on the loopback qdisc traversed in each direction: nominal 100 ms RTT and combined 20 ms jitter profile. ICE stats, the kernel route, qdisc packet/drop deltas and bidirectional private UDP headers establish the local route. They do not establish independent public networks or TURN.

WASM runs in a worker. The main thread actually copies and paints 256×240 RGBA frames. It transfers 48 kHz PCM into a 12,000-sample AudioWorklet ring (250 ms). An upper bound that includes in-flight PCM pauses further emulation above 8,000 queued samples; it resumes after actual worklet drain acknowledgements. No controller inputs are skipped. Wall duration, input stalls, backpressure, underruns and per-frame emulation/copy/transfer/paint timings remain visible, including poor performance. Overflow is a failure. At a common scripted midpoint each peer restores its own local checkpoint and flushes the audio epoch with a 240-sample fade-in. This is not the later shared-timeline authorization/barrier protocol.

Each synthetic voice source uses a different frequency. The receiver must observe nonzero RMS and the other peer's frequency, plus decoded inbound RTP samples. A muted playing HTMLAudioElement starts receiver consumption; a MediaStreamAudioSource/analyser is the sole audible path. Startup records preparation, explicit audio enable, ICE/channel readiness, first game frame and first remote energy separately. No permissions dialog, physical microphone, audible-quality judgment or repeated-attempt latency percentile is claimed. Closing stops tracks, worker and oscillator, detaches the element and closes the peer connection and AudioContext.

Full results and historical failed experiments are in the [D02 report](../../docs/implementation/d02-feasibility.md). Preserve exact versions, hardware and artifact identities when comparing results. Release qualification remains owned by the later networking, audio, content and deployment issues.
