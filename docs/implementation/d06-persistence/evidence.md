Audience: Agent

# Persistence candidate evidence

The real browser restored nonzero battery progress before the game executed, preserved old and corrupt backups, restored local preferences, and prevented stale deletion or automatic recreation after clear-all. These are author checks; independent acceptance and presubmit CI remain separate gates.

- Base: `0629cec4f90b9e8b4c335358dbdc5a1f8d4e528e`.
- Tested application source: `1aab46d`; later evidence-only commits do not change it.
- Browser: `python3 scripts/foundation/browser_smoke.py --chrome --output /tmp/d06-persistence-repaired.json` after `npm run build`. [Structured results](browser.json), [raw output](browser.txt), [client build](client-build.txt). The static local server intentionally has no coordinator; its websocket 404s demonstrate local play continues without that service.
- Native: all 22 release library tests passed, including the new battery-info ABI and existing mapper/region/adversarial battery/state tests. [Raw output](native.txt), [WASM build](wasm-build.txt). Final full preflight repeats the native tests at the complete candidate.
- The original complete preflight passed in 7.92 seconds; a fresh complete preflight follows this committed repair evidence. [Raw preflight](preflight.txt).
- WASM SHA-256: `5f0b24f626e00f4dba4c4a7cbe08c7b19e514b8d9631a7f81c45f0cd6777efaa`; complete browser workload: 48.76 seconds.
- Focused control/contracts tests: [output](focused.txt).
- Actual inspected UI: [desktop records](local-data-before.png), [desktop after confirmed clear](local-data-after.png), [populated mobile panel](local-data-mobile-before.png), [mobile after clear](local-data-mobile.png). The populated mobile dialog scrolls vertically; there is no horizontal overflow. Game audio uses only the application's gain mute; no browser/OS global mute is applied.
- Retained harness failures: [wrong CPU field](harness-cpu-field-failure.txt), [single-page context](harness-context-failure.txt), [ambiguous Right selector](harness-selector-failure.txt). These were failed development checks, not product acceptance. The corrected candidate's complete browser results are linked above.
- Author draft repair: [before-fail CPU result](replacement-before.txt) showed boot RAM 0 instead of 90 when reselecting the same ROM before its first periodic save. [Focused after-pass](replacement-after.txt) and the complete current browser run confirm capture now commits before candidate restore. Concurrent captures share the pending write promise. The original browser/preflight evidence remains in earlier commits; this was author cleanup, not an independent review round.
- Requirement snapshots: [issue and assignment history](issue-source.json), [epic](epic-source.json). The [technical guide](../d06-persistence.md) preserves governing approval lineage and remaining D06 obligations.

The browser probe waits for the actual ten-second persistence timer. Its cartridge program reads SRAM into CPU work RAM at boot; the exported real state independently confirms the restored byte. The other-build record is explicitly synthetic, preserving/exporting unknown bytes without claiming unavailable historical-core compatibility. Storage records contain only the documented metadata and state/battery/preferences fields; request observations show local asset GETs only.

Shared invariants remain single-owned: Rust `local_file` owns compatibility and the trusted cap/info; both codec consumers use it. The existing worker/player request correlation owns all file operations. `saves.ts` owns database transactions, expected-byte comparison and the clear generation. Controls validation reuses the same actions and conflict function as remapping; fingerprint matching and preference identity use `fileIdentity`. No peer NROM admission, mapper save-profile guard, whole-state decoder or file-limit copy was introduced.

D06 remains open for measured ten-second/32-MiB rewind and remaining agreed qualification. Unload persistence is best-effort, browser eviction can erase records, and arbitrary state-restore PCM continuity remains unsupported. Root owns merge after fresh independent acceptance, current CI and integration verification.
