Audience: Agent

# Validated local machine files

The worker can save and restore a running game without putting its ROM in the file. This D06 slice validates six mapper families and keeps unsupported save profiles separate from local game loading. It does not deliver save slots, browser persistence, file-picker controls or rewind. Issue #10 remains open, including qualification of the remaining mapper families.

## Scope and compatibility

The audited profiles are upstream Nrom, Sxrom (MMC1), Uxrom, Cnrom, Txrom (MMC3) and Axrom. Tests exercise mapper numbers 0, 1, 2, 3, 4 and 7 under NTSC, PAL and Dendy. Upstream aliases sharing those variants are not separately qualified by these tests. Other variants return an explicit unvalidated-save-profile operation error; their existing local play and battery operations remain available. Codec preparation is lazy on the first state operation, so even save-template allocation is independent of ROM admission.

The identity binds the versioned schema, exact ROM SHA-256, actual loaded WASM SHA-256, resolved region, fixed adapter settings and locally derived cartridge geometry/immutable mapper settings. Mutable registers never enter the identity: a first export after play can be imported into a fresh instance of the same game. Core binding uses `local_bind_core`. The common identity construction lives in `local_file.rs`, preserving the battery format's existing identity byte order.

The NROM/NTSC peer checkpoint admission and format remain unchanged. Local states are a separate boundary; this is not permission to send arbitrary local states through the peer protocol. Both codecs use the same CPU, PPU, APU, input and parser validation helpers in `state_validation.rs`. Only their format-specific boundaries and mapper admission differ.

## File and allocation boundary

`RCSTATE1` contains an eight-byte magic, 32-byte compatibility identity and 32-byte payload digest, followed by canonical JSON. The digest detects damage, not hostile authorship. The JSON contains mutable hardware, exact RAM and mapper execution state. It excludes ROM, cartridge allocation metadata, derived memory mappings and presentation filter history. Import reconstructs those excluded fields from the already loaded cartridge before invoking upstream typed deserialization; `load_bus` rebuilds mappings.

`local_file.rs` owns the shared 2 MiB whole-file ceiling. The worker queries `local_state_limit`, checks before copying, and allocates through independently bounded `local_state_alloc`. Contracts own request shape/correlation, not a second numeric size policy. Before JSON allocation, the parser bounds depth to 24, strings to 256 bytes and state tokens to 400,000. Canonical encoding rejects duplicate keys, whitespace variants and trailing data. Shape checks require exact object fields and array lengths; typed decoding additionally checks integer widths and enums. Mapper validation is one registry that both validates dynamic registers and supplies immutable identity fields. MMC1 dispatch masks a CPU write address to select a register but stores its original mirrored CHR address (`0xA000`–`0xDFFF`); the file preserves that exact address because pinned upstream board mapping reads it directly. Out-of-window addresses are rejected, not normalized.

Untrusted metadata never controls arena geometry. Allocation still includes a trusted current-cartridge template and candidate bus, which can contain large ROMs. This is not a rewind ring and does not establish the later 32 MiB rewind budget. Invalid input is checked before committing the candidate and leaves the live machine, including its CPU jam flag, unchanged. Success restores the explicitly serialized jam flag that upstream serialization omits.

`state-export` and `state-import` use a nonnegative safe integer `requestId`; `state-exported`, `state-imported` and `state-error` echo it. The worker's shared local-file handler also serves battery operations. Malformed files, incompatible identity and unsupported profiles are correlated nonfatal operation errors. Pointer ownership follows the existing battery ABI: consume each nonzero allocation exactly once with its allocation length; this internal trusted-worker pointer API is not safe for arbitrary hostile pointer calls.

## Clock and audio behavior

Exports accept synchronized states produced by the adapter's frame clock. A DMA instruction can finish after the nominal frame boundary, so local validation accepts that post-render interval rather than requiring scanline 240. Regional PPU constants and frame-counter step tables come from the pinned upstream core. CPU sub-dot residue is checked against the region's divider and power-on phase; PAL and Dendy are not forced into NTSC's zero residue. Peer checkpoints retain their stricter scanline boundary.

Restore starts a fresh presentation audio epoch: sample-rate setup resets synthesis/filter history and queued samples are cleared. Hardware registers and future video are restored; arbitrary pre-restore PCM continuity is not promised. Tests compare canonical hardware/video and separately compare PCM from two instances restored into the same fresh audio epoch. This avoids confusing presentation history with machine state.

## Verification and lineage

After README tool preparation, run `timeout 60s sh scripts/preflight.sh`. The native tests exercise changed PRG and CHR banks, CHR RAM, partial MMC1 serial writes, actual CPU writes through both mirrored CHR-register windows, MMC3 IRQ/A12 state, CPU corruption, DMA overshoot, all three regions and PAL five-step audio timing. Malformed, oversized, noncanonical and wrong-identity inputs must preserve the live snapshot. Fixtures are the project's original diagnostic with explicit register writes, not commercial ROMs; representative coverage is not complete mapper certification.

Run `sh scripts/foundation/prepare.sh`, `npm run build`, then `python3 scripts/foundation/browser_smoke.py --chrome --output /tmp/foundation.local.json` (omit `--chrome` for CI's pinned Chromium). The real worker/WASM probe checks export/import replay, fresh-instance compatibility, nonfatal malformed imports, allocator observation at the cap, and continued play plus battery export for an unvalidated mapper. Shared probe lifecycle/instrumentation lives in `worker_probe.py`; it observes actual exported limit/allocation calls without replacing their results. The existing CI foundation JSON includes these results. No new visible controls or screenshots are claimed by this slice, and no new CI job or budget is introduced.

This implements a bounded prerequisite of [D06](https://github.com/TuringTestee/retro-coop/issues/10), following the approved [project implementation plan](browser-nes-platform.md) merged in PR #3 and the issue's untrusted-allocation audit. The pinned TetaNES source in the Cargo lockfile remains the emulator implementation. Remaining work includes the other mapper profiles, IndexedDB transactions and identity-aware UI, manual/automatic slots, migration behavior, and a measured ring covering ten actual emulated seconds within 32 MiB. Battery files remain distinct: they replace persistent cartridge bytes without restoring a machine timeline; see [the battery boundary](d06-battery.md).
