Audience: Agent

# Persistence candidate evidence

The real browser restored nonzero battery progress before the game executed, preserved old and corrupt backups, restored local preferences, and prevented stale deletion or automatic recreation after clear-all. These are author checks; independent acceptance and presubmit CI remain separate gates.

- Base: `0629cec4f90b9e8b4c335358dbdc5a1f8d4e528e`.
- Tested application source: `ba72e42657550a72b2e08d691990fcd8d117eb1d`; later evidence-only commits do not change it.
- Browser: `python3 scripts/foundation/browser_smoke.py --chrome --output /tmp/d06-persistence-candidate.json` after `npm run build`. [Structured results](browser.json), [raw output](browser.txt), [client build](client-build.txt). The static local server intentionally has no coordinator; its websocket 404s demonstrate local play continues without that service.
- Native: all 22 release library tests passed, including the new battery-info ABI and existing mapper/region/adversarial battery/state tests. [Raw output](native.txt), [WASM build](wasm-build.txt). Final full preflight repeats the native tests at the complete candidate.
- Focused control/contracts tests: [output](focused.txt).
- Actual inspected UI: [desktop records](local-data-before.png), [desktop after confirmed clear](local-data-after.png), [populated mobile panel](local-data-mobile-before.png), [mobile after clear](local-data-mobile.png). The populated mobile dialog scrolls vertically; there is no horizontal overflow. Game audio uses only the application's gain mute; no browser/OS global mute is applied.
- Retained harness failures: [wrong CPU field](harness-cpu-field-failure.txt), [single-page context](harness-context-failure.txt), [ambiguous Right selector](harness-selector-failure.txt). These were failed development checks, not product acceptance. The corrected candidate's complete browser results are linked above.
- Requirement snapshots: [issue and assignment history](issue-source.json), [epic](epic-source.json). The [technical guide](../d06-persistence.md) preserves governing approval lineage and remaining D06 obligations.

The browser probe waits for the actual ten-second persistence timer. Its cartridge program reads SRAM into CPU work RAM at boot; the exported real state independently confirms the restored byte. The other-build record is explicitly synthetic, preserving/exporting unknown bytes without claiming unavailable historical-core compatibility. Storage records contain only the documented metadata and state/battery/preferences fields; request observations show local asset GETs only.

Shared invariants remain single-owned: Rust `local_file` owns compatibility and the trusted cap/info; both codec consumers use it. The existing worker/player request correlation owns all file operations. `saves.ts` owns database transactions, expected-byte comparison and the clear generation. Controls validation reuses the same actions and conflict function as remapping; fingerprint matching and preference identity use `fileIdentity`. No peer NROM admission, mapper save-profile guard, whole-state decoder or file-limit copy was introduced.

D06 remains open for measured ten-second/32-MiB rewind and remaining agreed qualification. Unload persistence is best-effort, browser eviction can erase records, and arbitrary state-restore PCM continuity remains unsupported. Root owns merge after fresh independent acceptance, current CI and integration verification.
