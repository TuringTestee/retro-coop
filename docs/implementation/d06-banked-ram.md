Audience: Agent

# MMC1 banked-RAM qualification

This bounded D06 follow-on will test whether CPU writes can select and preserve distinct cartridge RAM banks. The current upstream code maps bank zero regardless of the bank bits. The first deliverable is an original failing diagnostic; no runtime correction is applied before that result is captured.

## Scope and current status

The original CPU diagnostics now reproduce both mapping failures on the unpatched pin; the bounded patch passes those identical fixtures. Focused native state/battery/rewind and actual-worker validation passes; final integrated checks and independent review remain pending. Heavy local tests are coordinated with other builders. PR #58 was merged separately and is not edited here.

The approved [D06 row](https://github.com/TuringTestee/retro-coop/blob/ecf6bd4c7443526f0a163b721a351c854ee90fd4/docs/implementation/browser-nes-audit.md) requires compatible persistence/restore and ten-second/32-MiB rewind. Issue #10 requires representative bank-changing, RAM/battery, regional, malformed-import and replay proof. Implementing all 24 upstream mapper variants is not an established D06 acceptance requirement. Six state-profile variants are admitted today; the other 18 are inventory gaps, not an implicit assignment to implement them all. D20 remains the reviewed advertised-compatibility matrix and is not a dependency of D06.

The runtime change is limited to the demonstrated MMC1 RAM-bank/related mirrored-register mapping cause. Arbitrary supported ROM loading, peer admission and state-profile admission stay unchanged. Broader mapper/submapper corrections require their own bounded scope.

## Upstream provenance and dependency approach

As checked on 2026-09-20, upstream main is our existing pin `a0a6b17f8ba9c5ee451453fb2409753fd06e5a31`. Latest released `tetanes-core 0.17.0` records source commit `94e3db3684ced606c6865c51a9a61b0e15bc08fe`; GitHub reports the pin one commit ahead with no changed files. Both revisions and the actual released crate have the identical MMC1 blob `a34d663e86ade4d0ca972fc7e55177372ebc7ab0`. The published archive SHA-256 is `c12a52c1ee5d08354b57b57e858367518e9a7a266ad19ca65138ceb054d831c4`, matching registry metadata. Neither fixes the mapping code. Merely changing to the release is ineffective.

Implemented dependency approach after the before-failure result:

1. Vendor the verified published `tetanes-core 0.17.0` crate into an owned versioned dependency directory. Retain upstream licence, archive checksum, source revision and package metadata. Its standalone Cargo manifest avoids fragile workspace extraction. Record the exact initial tree and a small readable patch against it.
2. Use a Cargo patch/path override for this one dependency and update the lockfile. All callers still use the upstream mapper implementation; there is no adapter-side second mapping owner. The normal offline locked native/WASM commands consume committed source without downloading or modifying the shared Cargo cache. No build-time network patching or hidden local modifications are allowed.
3. Keep the behavioral diff confined to the demonstrated MMC1 mapper and cartridge-allocation owners plus their regression tests. Any needed derived immutable board geometry must remain locally reconstructed/trusted and part of existing identity validation; do not accept a new allocation or geometry field from save bytes.
4. When upstream incorporates an equivalent correction, pin its exact revision, remove the local override/vendor patch, and rerun these same native/WASM, save/battery, replay and memory regressions. The rebuilt core digest naturally changes compatibility identity; old-version Local Data must remain exportable/deletable without automatic incompatible restore.

Vendoring adds maintained source and provenance overhead, but avoids creating an externally hosted fork or making clean builds depend on an unversioned patch cache. The vendored mapper is now patched. The packaged `test_roms/` directory is deliberately omitted: its 6.3 MiB of upstream test binaries are not needed to build the dependency or execute our original diagnostics. Provenance retains their original hashes and explicit omission prefix; all retained files must match upstream or the recorded two-file patch. `scripts/verify_vendor.py` enforces that exact inventory in preflight. Upstream ROM-based tests are not claimed as executed by this delivery.

## Original diagnostic and required evidence

`scripts/foundation/banked_ram_fixture.py` emits only original machine code and generated bank markers. NES 2.0 declares 512 KiB PRG, 8 KiB CHR RAM and 32 KiB battery RAM. Identical executable code in each PRG bank permits real banking during execution.

- `banked`: actual CPU serial writes select four RAM banks, write 0x11/0x22/0x33/0x44 at $6000 and read each back into separate CPU RAM result slots. The expected values come from the program's actions, not inspection of emulator registers.
- `mirrored`: a CPU write sequence to C001 selects CHR1 in 4 KiB mode, then reads a distinct ROM-bank marker through the expected outer PRG mapping. The same program through canonical C000 should be a control case before changing the mapper owner.

`spikes/d02/examples/mmc1_banked_probe.rs` executes the fixture and checks its completion/result bytes. First run both cases against the unchanged upstream dependency and retain raw failures. Then add controls and broaden only the demonstrated mapping tests: partial serial writes, bank contents after state and battery roundtrip, invalid-import invariance, exact replay and regional ten-second rewind with actual allocation accounting. Actual-worker proof must execute the generated program; header-only boot or register mutation alone is insufficient.

Hardware wiring must be checked against the [MMC1 board documentation](https://www.nesdev.org/wiki/INES_Mapper_001) and [submapper definitions](https://www.nesdev.org/wiki/NES_2.0_submappers). SOROM/SUROM/SXROM are not interchangeable; 16-KiB mixed volatile/battery wiring is not claimed by the initial 32-KiB diagnostic.

## Before/after result

At original fixture commit `461f638` on unmodified core pin, [before output](d06-banked-ram/before.json) reads all four RAM slots as 68 instead of 17/34/51/68, and mirrored C001 reads PRG bank zero instead of 16. Canonical C000 control passes. The [patched output](d06-banked-ram/after.json) passes all three with identical fixture hashes. [Initial build](d06-banked-ram/before-build.txt) took 4.95 seconds; [patched locked offline build](d06-banked-ram/after-build.txt) took 13.61 seconds. The first example build warning was repaired with an explicit discard of the rendered frame. These are focused native mapping results, not full D06 acceptance.

The patch masks the retained mirrored register address at its mapping consumer and derives SOROM/SXROM RAM selection from trusted CHR/RAM geometry. Existing 8-KiB and larger-CHR behavior is retained. A separate 16-KiB SOROM CPU fixture exposed the loader overriding explicit NES 2.0 geometry with a 32-KiB fallback. The loader now retains positive explicit NES 2.0 MMC1 sizes; legacy unspecified headers retain the prior fallback. Exact 8/16/32-KiB controls and state/battery tests now pass. No allocation count is accepted from save bytes.

The published crate omits its root licence files. Both upstream MIT and Apache licences are therefore retained separately under `vendor/`, fetched from the exact release revision and checked by recorded supplementary hashes. The zero-context patch is an inspectable record; replay it with `git apply --unidiff-zero` against the verified upstream source if needed.

The first WASM command was invoked from the repository root with `--manifest-path`, bypassing the existing `spikes/d02/.cargo/config.toml` target configuration. Its [raw failure](d06-banked-ram/wasm-invocation-failure.txt) is retained. The documented build runs inside `spikes/d02`; the command was corrected without changing target configuration or dependency features.

## Qualification and reproduction

The [native result](d06-banked-ram/native-after.txt) checks distinct 16/32-KiB bank bytes, two CPU-written partial serial bits, battery restoration without CPU/mapper changes, malformed import invariance, wrong-core identity rejection and exact replay in NTSC/PAL/Dendy. Actual CPU programs check RAM write-disable, serial reset, canonical/mirrored registers and single-bank behavior. Regional continuously banked progress rewinds at least ten actual CPU-clock seconds, compares exact state/pixels at the independently traced target and replays the future. Maximum observed native accounted peak is 4,404,272 bytes.

The first [actual-worker result](d06-banked-ram/worker-initial.json) passes in 32.30 seconds, with valid battery replacement and restoration proving actual mutation, rejected imports leaving the timeline unchanged, and three regional exact rewind/replay checks. Later final proof additionally exercises a larger-CHR control. These are original functional geometry fixtures; the 16-KiB fixture declares all RAM battery-backed and does not qualify real SOROM's mixed volatile/battery retention wiring or every submapper.

The [geometry failure](d06-banked-ram/geometry-before-failure.txt) is retained: the mapper-only patch let CPU reads appear correct while the second declared 16-KiB bank landed at the wrong backing offset. The repair preserves explicit positive NES 2.0 MMC1 geometry at the cartridge loader. Unspecified/zero legacy fallback and other mapper allocation policies are unchanged; full zero-RAM hardware semantics are not newly qualified.

Run `python3 scripts/foundation/banked_ram_fixture.py all spikes/d02`, then from `spikes/d02` run `cargo +1.95.0 test --locked --offline --release --lib banked_ram -- --nocapture`. Build the actual core using `sh scripts/foundation/prepare.sh` and `npm run build`. Run `python3 scripts/foundation/banked_ram_smoke.py --chrome --output /tmp/banked.local.json`; it shares the existing worker lifecycle/allocation probe and a reusable standalone runner. Normal foundation UI proof remains its own command and unchanged 90-second CI timeout. Banked qualification has a separate 90-second CI command with raw `banked-ram.local.json` included by the existing artifact glob. The complete presubmit deadline remains 30 minutes. Run the README full preflight under its existing 60-second hard limit before handoff.
