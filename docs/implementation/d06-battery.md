Audience: Agent

# Local battery file boundary

The emulator worker can now export and import a cartridge's battery-backed data without exporting its ROM. This is the first D06 implementation slice: it does not yet provide save slots, browser persistence, file-picker UI, whole-machine saves, or rewind. Issue #10 stays open for those outcomes.

## Scope and trust boundary

Battery data is the cartridge's persistent RAM and board-held extensions such as Bandai EEPROM. It is not a snapshot of CPU registers, mapper execution state, picture, sound, or controller input. Import replaces only the battery bytes on the existing timeline. A later UI must explain this and confirm replacing progress; these worker operations have no user-facing controls yet. Nothing sends files to the coordinator or persists ROM content.

The new Rust `battery` module is independent of the NROM/NTSC peer checkpoint codec; that codec's guard and format are unchanged. The existing trusted in-memory local save remains internal. No upstream whole-state decoder receives imported battery data, and this change makes no whole-state safety claim.

The worker hashes the actual loaded WASM bytes, then binds that 32-byte digest once after cartridge initialization. Rust independently hashes the exact cartridge bytes before discarding the input allocation. The battery identity hashes schema, exact ROM digest, actual WASM digest, resolved region, the fixed local adapter settings (zero RAM, 48 kHz, normal speed, two standard controllers, default mapper revisions), and the locally derived battery length. A modified build, appended ROM byte, or different region therefore cannot silently reuse a file. The digest identifies compatibility, not ownership or authenticity.

`RCBAT001` is a fixed binary envelope:

| Bytes | Meaning |
| --- | --- |
| 0–7 | Versioned magic |
| 8–39 | Compatibility identity SHA-256 |
| 40–43 | Little-endian payload length |
| 44–75 | Payload SHA-256 for accidental corruption detection |
| 76 onward | Exact upstream battery bytes, including mapper extensions |

The shared Rust `local_file` module owns the whole-file limit of 2 MiB for battery and machine files. The worker reads it through `local_battery_limit()` and rejects oversized buffers before allocating/copying into WASM; `local_battery_alloc` enforces that same Rust constant independently. The shared TypeScript contract validates request shape and rejects empty buffers, without carrying a second size policy. Import requires an exact locally expected total and payload length, magic, identity and checksum. Trailing bytes are rejected. Imported length fields never determine a decoder allocation. A checksum is not a signature: arbitrary battery bytes are valid when the user deliberately supplies a correctly formed file.

Export synchronizes board extensions on a trusted clone, leaving the live machine unchanged. Import completes all checks before cloning the current bus, applies bytes to that candidate through the upstream battery API, then commits through `load_bus`. Immutable cartridge data and mapper mappings always originate from the already loaded local game. CPU corruption flags, partial MMC1 serial writes and other running hardware are not replaced by file content. Candidate allocations depend on the current local cartridge, not on imported metadata; the temporary full bus clone can include large ROMs. This is not a rewind buffer or its memory accounting.

The WASM ABI owns each nonzero pointer returned by `local_battery_alloc` exactly once: consume it with `local_bind_core` (or its compatibility alias `local_battery_bind`) or `local_battery_import` using the same allocation length. Export and errors use the existing `local_output(0)`/`local_output_len` copying convention. These pointer APIs are called only by the trusted worker; arbitrary hostile pointer calls are not a memory-safe public interface. Worker `battery-export`/`battery-import` requests carry a nonnegative safe integer `requestId`; success and battery errors echo it. An invalid battery import does not become a fatal emulator error. A cartridge without battery support returns an explicit operation error and remains playable.

## Verification and remaining D06 work

After the README tool preparation, run `timeout 60s sh scripts/preflight.sh`. Focused Rust tests exercise changed MMC1 banks and partial serial writes, MMC3 bank/IRQ setup, PAL/Dendy Bandai EEPROM extensions, unchanged live state on rejection, CPU corruption preservation, immutable ROM exclusion, and future hardware/pixel/PCM equality with an untouched execution twin. They use the project's original diagnostic and direct board register writes, not commercial ROMs. This is representative evidence, not all-mapper qualification.

Run `sh scripts/foundation/prepare.sh`, `npm run build`, then `python3 scripts/foundation/browser_smoke.py --chrome --output /tmp/foundation.local.json`. Omit `--chrome` for pinned Playwright Chromium in CI. The existing browser suite now also exercises the real built worker and WASM battery requests, correlation, nonzero payload roundtrip, malformed and oversized buffers, exact ROM mismatch, absent battery, and continued identical pixels/PCM after rejection. The probe observes actual WASM limit/allocation calls without replacing their return values: a buffer at the exported limit reaches format validation, while limit plus one never reaches allocation. It presents no battery-test audio; the existing application suite uses only its game gain mute. Its JSON is retained by the existing core artifact. There is no new visible UI requiring battery screenshots, new CI job, or longer budget.

Still required under D06: audited whole-state schema with general mutable mapper validation; IndexedDB save/battery persistence, slot management and visible error/export recovery; compatible whole-state import/export; measured ten seconds of actual emulated rewind within 32 MiB. This slice neither closes D06 nor reduces arbitrary supported-game scope. D20 remains broad hardware qualification, not a prerequisite used to defer D06 acceptance.

Authority: issue #10 / D06 in approved planning PR #3, merged `ecf6bd4c7443526f0a163b721a351c854ee90fd4`; [saves design](../design/browser-nes-platform.md#saves-rewind-and-controls), [U6 saves flow](../design/browser-nes-ui.md#u6--saves-and-local-data), and issue #10's safe-boundary implementation audit. D05 prerequisite merged at `f248296aca30c4a2f60475e4c3e062c73577dd76`. Root authorized this bounded intermediate battery ABI slice while retaining sole merge ownership.
