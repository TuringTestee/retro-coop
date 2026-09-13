The pinned core can replay the same inputs in Linux Chrome and Firefox with matching state, picture and audio hashes. A complete experimental NROM checkpoint codec now validates inputs before restoring local cartridge mappings. The feasibility gate remains **incomplete**: Windows/macOS, impaired peer networking, actual speaker playback, and startup/voice measurements are not proved by these local probes. Do not release D04 or claim AC-05–07 complete from this report alone.

# D02 feasibility experiment

This is the bounded experiment for [issue #6](https://github.com/TuringTestee/retro-coop/issues/6), under [epic #2](https://github.com/TuringTestee/retro-coop/issues/2), the merged [design](../design/browser-nes-platform.md) and [technical plan](browser-nes-platform.md). D01 integrated in PR #29 at `6059838aed1e9039812e8dd4b0a1cdc736539d1d`. TetaNES remains pinned to `a0a6b17f8ba9c5ee451453fb2409753fd06e5a31`; no core switch or upstream source patch is made. This prototype specializes the codec to NROM/NTSC to test the selected From Below fixture, not to narrow the approved broad-compatibility release.

## Results and exact limits

Inspection/run date: 2026-09-13. Reference machine: Intel Core i7-8700K, six cores/twelve logical CPUs, about 16 GB RAM, Linux x86_64. Local browsers are Google Chrome 145.0.7632.75 and Playwright Firefox 146.0.1. These are the installed versions tested, not a claim to the latest stable releases or the required Windows/macOS matrix. Rust is 1.95.0 (`59807616e`, Cargo `f2d3ce0bd`), release profile, `wasm32-unknown-unknown`; the lockfile and target flags are committed. Both rendering and audio mixing remain enabled, RAM starts at zero, region is NTSC, output is 48 kHz, speed is 1x, run-ahead is unused, SRAM persistence is disabled. Each browser result records the actual WASM SHA-256 and platform.

The local From Below 1.0 artifact is 40,976 bytes, SHA-256 `1a3ac4faf4b35640505344059ae5d91dae07cd47e1fb4d9d2a33c76391f1c555`, as selected and licensed by the user in D03. Its bytes and original local path are absent from Git and CI. No featured-game substitution is made. Automated input is a deterministic two-controller bit sequence; it proves replay under those inputs, not correct gameplay modes, an uninterrupted human playthrough or universal compatibility.

| Completed observation | Evidence and meaning |
|---|---|
| Original 36,000-frame replay | [Raw browser results](d02/browser-raw.json): 60 records per browser, frames 600 through 36,000. Entire state/video/PCM hash records match between Linux Chrome and Firefox. Chrome emulation loop 93.136 s; Firefox 582.656 s. Total browser tasks 96.585 s and 603.354 s include restore/hashing overhead. |
| Upstream raw restore fails canonical identity | Both browsers restore identical video after 600 replayed frames, but raw-state and PCM hashes differ. Native structural comparison traced state differences to seven scalars inside `apu.filter_chain`; source preserves the current output filter/synth across restore. This failure is retained rather than presented as a pass. |
| Trusted local rewind | [Local restore results](d02/browser-local-restore.json): both browsers retain 601 raw dynamic snapshots spanning 600 NTSC frames. Actual tracked snapshot/vector allocations: 12,939,530 bytes; maximum snapshot 21,518 bytes; WASM linear memory after the probe 15,728,640 bytes. Both recover matching canonical state after replay. These are actual retained buffers, not only `size × frames`; linear memory also includes the core and transient allocations, but is not browser-process RSS. |
| Complete bounded codec, native | [Native checkpoint results](d02/native-checkpoint.json): 36,000 frames, 60 successful encode/decode checkpoints, maximum wire checkpoint 49,491 bytes. Hardware canonical restore matches; restoring the same checkpoint after different preceding histories produces identical new-epoch PCM and hardware state. Final frame has 799 samples. Uninterrupted PCM remains intentionally different across a timeline jump. |
| Focused hostile-state regression | Six tests cover original controller/audio diagnostic execution, complete checkpoint restore, 60-frame PCM equality after two independent preceding histories, explicit jam-state preservation, malformed identity/schema/length/field/range rejection without changing the live core, and ROM-free memory-tail restoration. A controlled upstream decoder test accepts less than 1 KiB of JSON requesting a 4 MiB memory arena, demonstrating why generic dumps are not accepted. |
| Final worker and complete-codec browser run | [Committed-build worker evidence](d02/browser-worker.json): both Linux browsers pass all 60 hash records, hardware/video restore, identical new-epoch state/video/PCM after different preceding histories, empty restored audio queue, and 799 final-frame samples. Wire checkpoint 49,465 bytes; rewind allocations 12,939,530 bytes; whole WASM linear memory after the probe 16,842,752 bytes. Chrome replay loop 95.1914 s; Firefox 566.330 s. `verify_results.py` passes. |
| Current executable-source CI | [CI run](https://github.com/TuringTestee/retro-coop/actions/runs/34770958129) passed in 10m03s, including setup/build, preflight and both original-fixture browser runs. [Committed CI artifact](d02/browser-ci.json) records Chromium 145.0.7632.6 and Firefox 146.0.1, replay loops 52.304/368.557 s, 47,179-byte checkpoints and passing new-epoch/rewind assertions. |

The final local worker artifact is SHA-256 `45c5ff0b3ae25aeb4e0cf7e791dc9cf9115243aab02d4c7fee571e1863322894`. CI records its separately built artifact hash; bit-for-bit cross-host build reproduction is not established. Executable source is commit `86e66a8e796a9b8f193705d25b25696ce9e4f31c`; the evidence-only update does not change it. Final review and CI status for that evidence update are published on PR #33. Firefox has limited headroom near real-time speed on this reference machine; these instrumented, headless runs are not a release performance promise.

The 600-frame rewind experiment spans about ten seconds at NTSC frame rate; PAL/Dendy require their own frame counts and qualification. The buffer accounting is for this selected fixture and raw **locally generated** rewind snapshots. Wire checkpoints use a different, validated JSON encoding; multiplying its size by 601 is not the implemented rewind allocation. Raw upstream dumps are never accepted from peers by the codec.

## State and ROM-content audit

`spikes/d02/src/checkpoint.rs` contains the experimental schema `D02NES01`. Its fingerprint hashes the schema, exact core revision, dependency lock, Rust toolchain/target flags, exact local ROM SHA-256, fixed options, and local memory/mapper layout. A future protocol handshake must also compare the deployed adapter/WASM artifact hash; no network handshake is implemented here.

Before generic JSON allocation, the decoder checks the 2 MiB envelope, schema/fingerprint, maximum depth 24, 60,000 structural tokens and 256-byte strings. After parsing, exact canonical encoding rejects duplicate fields, trailing bytes and alternate encodings; `serde_json`'s `float_roundtrip` feature preserves the encoded floating values. Exact object keys, fixed array lengths and scalar types are checked against the trusted local shape for this pinned NROM core. Upstream typed decoding only follows these checks and enforces Rust integer widths and enum names.

No peer-supplied memory arena length, ROM offset/range, CRC, mapper discriminant or bank mapping is decoded. The payload carries only the mutable memory tail; layout and NROM mirroring are reconstructed from the local loaded cartridge before creating the `Bus`. `load_bus` then restores ROM from local memory and rebuilds derived mappings. Unknown mapper/region configurations fail closed in this prototype. D20 must extend and audit board-specific schemas before additional hardware is admitted.

| Serialized component | Treatment and audited concern |
|---|---|
| Cartridge memory | Only `Memory::ram()` travels. PRG/CHR ROM, memory offsets/ranges, ROM CRC and page tables do not. Controlled sentinel tests preserve the receiver's PRG/CHR bytes exactly. |
| CPU | Registers, timing, interrupt flags, pending DMA and addressing state travel. `Cpu.corrupted` is added explicitly because upstream skips it. NTSC read/write timing is fixed; master-clock fields must be at the supported frame boundary. |
| PPU | Dynamic registers, scrolling, palette, sprite/OAM state and frame count travel. Pixel framebuffer and derived coverage tables are omitted by upstream. Checkpoints require scanline 240 with non-rendering derived flags; clock divider/timing are fixed. Fine-X, sprite count, secondary OAM, palette and other index/shift fields are bounded. Derived coverage is rebuilt before subsequent rendering. |
| NROM mapper | Mirroring/mappings come from the trusted local cartridge; no peer mapper object is accepted. NROM has no mutable bank registers. Other boards remain unsupported by this codec. |
| APU hardware | Pulse/triangle/noise/DMC timers, counters and output state travel. Guards cover duty/sequence/table indexes, sweep shifts, envelope/mixer ranges, DMC sizes, cycle bounds and frame-counter tables. Region-derived frame tables are checked, and delayed writes require a valid delay. |
| Presentation audio | Output samples, private band-limited synthesis history and filter history do not form the canonical hardware state. Every full-codec restore clears old audio and resets output synthesis/filtering at 48 kHz while retaining the hardware APU state. Two different preceding timelines must produce identical new-epoch output from the same checkpoint. |
| Controllers | Buttons, serial indexes, strobes and timers travel. `load_bus` is used instead of `deserialize_state`, which clears input. Standard-controller mode/configuration remains fixed and serial indexes are bounded. |
| Debugger/session data | Debugger, code map, PC history, patches and other upstream skipped session fields are not transmitted. The prototype does not expose cheats/debugger mutation. |

The canonical hash excludes output-filter history and includes the jam flag. It does not silently discard CPU, PPU, mapper, RAM or hardware APU differences. ROM-free means no immutable cartridge buffers or mapped ROM regions; normal CPU operands and mutable RAM may naturally contain values read from ROM during emulation. It is not a claim that no dynamic byte can ever equal a ROM byte.

The decoder's narrow shape/range audit is relevant proof, not a universal security certification. Fresh local review must assess this exact candidate, and real peer-transfer framing/backpressure/timeouts, broader adversarial fuzzing and additional mapper state invariants remain downstream work. The only WASM input allocation API in this developer harness loads trusted local ROM bytes; it is not a production RPC or file-validation API.

## Worker/audio behavior and remaining gates

The final harness runs WASM in a worker and traps every imported host function, including upstream localStorage functions. A successful run therefore proves that the configured path did not access those host imports. The worker returns hashes and measurements; no game or checkpoint bytes are uploaded. The sample buffer is drained by frame clocking and explicitly cleared on a timeline jump. Unit tests compare all PCM produced across 60 resumed frames and require a bounded sample count.

Hash equality is not audible-quality evidence. The new audio epoch can cause a discontinuity relative to uninterrupted playback; actual Web Audio queue flush/fade, speaker playback, worker-to-main audio/video copying costs, throttling/pause and latency need measured integration before acceptance. Those are not hidden inside a passing hash assertion.

Unmet feasibility proof remains explicit:

- The approved Chrome/Firefox pairs on Windows and macOS are not available on this Linux machine. Linux replay is useful preliminary evidence, not that matrix.
- These tests replay identical inputs independently; they do not prove a ten-minute two-peer session under 100 ms RTT, 20 ms jitter and 1% loss, input delay, WebRTC backpressure or recovery.
- Initial startup and voice measurements, real Web Audio output and public-network routes are unverified. AC-05, AC-06 and AC-07 remain open with their full product/network acceptance.
- Hardware qualification beyond this NROM/NTSC experiment and featured-game gameplay/rights packaging remain D03/D20 work; the broad release goal is retained.

The dispatcher must keep D04 blocked until these governing feasibility requirements are either evidenced or a reviewed, approved plan revision explicitly changes the prerequisite. This report does not silently convert an incomplete experiment into an architecture pass.

## Time budget and next decision

The approved limit is five developer days for **D01 plus D02 combined**, not five extra days for D02. Historical D01 human developer hours were not recorded and cannot be reconstructed from agent wall time. D02 began on 2026-09-13 around 16:40 UTC; command durations are measured where stated, but they are not interchangeable with developer days. Record this accounting gap rather than inventing remaining hours or claiming the bound has already been consumed.

Continue only within that combined allocation. If the missing OS/network/audio proof cannot be supplied inside the bound, record a failed feasibility gate and bring the concrete scope/core/schedule choice back for review. No fallback core, streaming architecture, reduced rewind target or smaller release behavior is authorized by this PR. D01's 16–24 developer-week range remains provisional; these Linux results are not enough to reduce it.

## Reproduce

Prepare tools and run the README preflight. No user ROM is needed for the regression suite. The original 24,592-byte diagnostic generated by `original_fixture.py` has SHA-256 `d4a21ae4b7c1b9601744b799b5cc48824c5c762964571b90d291e559ac1378ba`; it polls both controller ports, records progress, changes the backdrop and drives a pulse channel. It contains no third-party ROM bytes and is not a replacement featured title:

```sh
cd spikes/d02
python3 original_fixture.py fixture.local.nes
cargo +1.95.0 test --locked --release --lib
cargo +1.95.0 build --locked --release --lib --target wasm32-unknown-unknown
python3 -m venv /tmp/d02-browser-venv
/tmp/d02-browser-venv/bin/pip install playwright==1.58.0
/tmp/d02-browser-venv/bin/playwright install chromium firefox
python3 -m http.server 8765 --bind 127.0.0.1
```

In another terminal, run from `spikes/d02`:

```sh
timeout 1200s /tmp/d02-browser-venv/bin/python browser_probe.py fixture.local.nes --bundled-chromium --output browser-ci.local.json
python3 verify_results.py browser-ci.local.json
```

Bundled Chromium is identified as Chromium, not branded Chrome. To reproduce the licensed local content experiment, supply the local path as the positional ROM argument and omit `--bundled-chromium` on a machine with `/usr/bin/google-chrome`. Do not put that ROM or original private path in Git, CI configuration, logs shared with reviewers, or an HTTP-served directory. The tool reads it locally and passes it directly to the browser's worker; the server only serves the harness. `cargo +1.95.0 run --locked --release --bin probe -- <authorized-local-ROM>` repeats the native codec test.

The complete preflight has a 60-second outer timeout. CI retains one job with a 30-minute hard deadline, rejects retries that would extend its original run, and caps its browser phase at 1,200 seconds. The worker also terminates an individual browser experiment after 900 seconds. Cold tool installation/build is part of CI's shared deadline, not excluded setup time. Browser evidence is uploaded even on failure; a timeout is a failure, never a passing shortened workload. No post-submit soak is claimed or required for this isolated experiment; the planned staging soak still belongs to later networking integration.

[Dependency metadata](d02/dependencies.json) records the actual resolved WASM build graph including build-time crates. [Third-party notices](../../spikes/d02/THIRD_PARTY_NOTICES.txt) preserve notices from every recorded dependency; TetaNES is used under its MIT alternative. This is software-license inventory, not a license for From Below or emulator-bundled games.
