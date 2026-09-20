# Firefox performance harness correction

The production performance test used Playwright's patched Firefox build, while the existing D02 test used the official Firefox release. With identical game inputs and outputs, the patched build took much longer to execute each frame. Production qualification now uses the same verified official release as D02. No emulator optimization, extra input delay, relaxed timeout, or reduced workload was adopted.

## Actual failed gate

[CI 35512085633](https://github.com/TuringTestee/retro-coop/actions/runs/35512085633) tested candidate `dab41c71ba3f45269ac4b978274088dd3cc6ae7a`, tree `e56ff0787922e6f30325331af3ec0917f70838ef`. Its core job passed all 19 short gameplay cases in 167.19 seconds, and Chrome–Chrome and Chrome–Firefox completed their long workloads. Firefox–Firefox failed: the host reached approximately 1,002 ms of real-time debt after 2,474 resumed-epoch frames. Both peers negotiated delay 8, their measured transport round trips were 109/111 ms, and neither native connection failed. Worker delivery averaged 14.97/15.13 ms. The retained `ci-35512085633-firefox-firefox/` files include the failed measurement and actual packet impairment evidence. This run remains failed qualification.

Resource snapshots show four logical CPUs, available memory and no cgroup throttling. They do not justify blaming runner throttling or calling the failure flaky. The earlier successful artificial 14 ms worker-delivery floor did not cover this measured cost.

## Bounded experiments

Each oracle executes the same 600 **frames**, fixed two-controller input sequence and actual production worker/WASM. It hashes every RGBA frame and every PCM buffer, checks nonzero PCM, and compares canonical state payloads every 120 frames. Canonical comparison excludes the envelope's intentionally different core-build identity. These are diagnostics, not the required 600-second network qualification.

| Experiment | Native mean ms | Worker mean ms | WASM bytes | Outcome |
|---|---:|---:|---:|---|
| Baseline, patched automation | 8.217 | 9.078 | 3,144,842 | Reference |
| Thin LTO, one codegen unit | 8.572 | 9.447 | 2,783,509 | Rejected: no speed gain |
| PPU clock forced inline | 8.083 | 8.950 | 3,660,299 | Rejected: insufficient margin and larger artifact |
| Reuse output vector capacity | 10.240 | 11.098 | 3,146,046 | Rejected: pixel/PCM phase did not improve |
| Restored baseline control | 8.225 | 9.075 | 3,144,842 | Baseline recovered |
| Same patched binary, standalone | 8.117 | 8.988 | 3,144,842 | Automation connection did not explain cost |
| Official 146.0.1, standalone | 1.678 | 1.910 | 3,144,842 | Substantial browser-build difference |

Every experiment produced exactly identical pixel, audio and canonical-payload hashes. Individual timings are measurements, not deterministic speedup guarantees. The output experiment's native-cost change despite unchanged emulation source is retained; no allocation-cause claim follows from it. Original build times were 49.18 seconds for cold Thin LTO, 53.52 seconds for PPU inline, and 14.10 seconds for output reuse.

The baseline phase probe measured approximately 9.5 ms native emulation, 0.77 ms pixel extraction and 0.20 ms main frame-handler work. A Firefox sampling profile attributed 2,038 worker leaf samples to PPU clock, 1,455 to the frame loop, 613 to CPU bus read, 504 to APU lazy clock and 458 to video filtering. Profiling itself increased timing; it is not a clean performance comparison. No safe general cycle-skipping optimization was established, and none was added.

The known [Mozilla debugger/WASM baseline mechanism](https://bugzilla.mozilla.org/show_bug.cgi?id=1714072) motivated the same-binary standalone control. That control did **not** establish debugger attachment as the cause. Only the browser-build performance difference is demonstrated; its deeper compiler cause remains unproven.

## Test driver and initialization

`spikes/d02/firefox_driver.py` shares official launch options, page options and provenance between the legacy and production probes. It imports the sole version/archive pins from `prepare_stock_firefox.py`. Production records the installed metadata, executable hash before/after, driver and both browser-instance versions. Its full-workload verifier rejects bundled, missing or mismatched Firefox provenance. Historical bundled short functional captures remain explicitly different coverage.

Each player owns a separate browser instance, as D02 already did. This preserves actual focus checks: sharing the official browser process made the host lose focus when the second page became active, and the product correctly refused to start.

Stock BiDi preload scripts produced `Permission denied to access property "length"` reports even on an empty HTTP page. The independent `bidi-minimal.py` / `.json` reproduction contains no game code. [Mozilla bug 2032066](https://bugzilla.mozilla.org/show_bug.cgi?id=2032066) describes the same boundary, although its tracked versions do not prove this release's internal cause. Errors were not suppressed. The harness now fulfills only its exact same-origin document URL with the existing fixture inserted before the app module, in separate lexical scopes. App JavaScript and WASM assets remain byte-for-byte unchanged. The mutable per-page fixture list also preserves delayed-join injection. Invite hash assignment followed by reload avoids BiDi's load wait on same-document hash navigation.

Retained initialization failures distinguish hash-navigation, real focus, preload errors and an author-found script-scope collision from product failures. The scope collision was corrected by preserving the separate scopes of the original preload scripts.

## Reproduction

Prepare/build the candidate normally. Install official Firefox with the existing pinned installer, and run the standalone oracle twice, choosing official and bundled executables:

```sh
python3 spikes/d02/prepare_stock_firefox.py /tmp/d11-official
ORACLE_FIREFOX=/tmp/d11-official/firefox/firefox python3 scripts/gameplay/performance_probe.py /tmp/official.json
ORACLE_FIREFOX=/path/to/playwright/firefox python3 scripts/gameplay/performance_probe.py /tmp/bundled.json
```

`performance_automated.py` runs the same workload through the patched Playwright driver used for the compiler experiments. Both scripts share `performance-workload.js`, `performance-worker.js` and the existing actual-worker lifecycle helper. `managed-*-oracle.json` verifies the checked-in standalone harness.

For rejected compiler experiments, use a disposable checkout of the measured source. The included patches describe the isolated PPU/output changes. Thin LTO used `CARGO_PROFILE_RELEASE_LTO=thin CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1` with `cargo +1.95.0 build --locked --offline --release --lib --target wasm32-unknown-unknown` from `spikes/d02`; default release optimization already used level 3. Copy that generated core to `apps/client/src/generated/`, rebuild the client, then run the exact-output oracle. Do not combine rejected changes or treat them as the delivered fix.

All three required production pairs still need 600 seconds under the original kernel impairment, input-delay range, periodic hashes, real-time frame count and one-second stall/debt limits. The current failed run is not reclassified; the repaired final candidate requires new CI qualification and independent review.

## Current repair checks

On source commit `350f9a9`, all 19 short gameplay cases passed in 168.05 seconds under their unchanged 180-second cap; `short-suite/` retains every case and screenshot. The unmodified official Firefox–Firefox production probe passed 30.01 active seconds under actual kernel impairment, with 2,017 matching final frames and hash, delay 8 in both epochs, worker delivery means 2.208/2.163 ms and zero page errors. Its existing packet verifier passed. Total setup, browser control and barrier time was 71.31 seconds, distinct from active game time. The official mixed-browser delayed-join proof passed in 15.42 seconds with the HTML fixture path. These short checks do not replace final CI's three 600-second workloads.
