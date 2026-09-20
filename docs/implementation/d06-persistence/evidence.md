Audience: Agent

# Persistence candidate evidence

The real browser restored nonzero battery progress before the game executed, preserved old and corrupt backups, restored local preferences, and prevented stale deletion or automatic recreation after clear-all. These are author checks; independent acceptance and presubmit CI remain separate gates.

- Base: `2c3d1a7986ef7dd76ed788577b1191ba7a59e1f1`.
- Tested application source: `be2ba3aa680e8ceb308084a1d9ea4202651cd904`; later evidence-only commits do not change it.
- Browser: `python3 scripts/foundation/browser_smoke.py --chrome --output /tmp/d06-timestamp-final.json` after `npm run build`. [Structured results](browser.json), [raw output](browser.txt), [client build](client-build.txt). The static local server intentionally has no coordinator; its websocket 404s demonstrate local play continues without that service.
- Native: all 22 release library tests passed, including the new battery-info ABI and existing mapper/region/adversarial battery/state tests. [Raw output](native.txt), [WASM build](wasm-build.txt). Final full preflight repeats the native tests at the complete candidate.
- Complete preflight on committed round-1 repair evidence `97dd63c` passed in 7.20 seconds, including all 22 native and 42 Node tests without skips. The committed merge-base diff check passed. [Raw preflight](preflight.txt). Prior results remain in history.
- WASM SHA-256: `5f0b24f626e00f4dba4c4a7cbe08c7b19e514b8d9631a7f81c45f0cd6777efaa`; complete browser workload: 50.3 seconds.
- Focused control/contracts tests: [output](focused.txt).
- Actual inspected UI: [desktop records](local-data-before.png), [desktop after confirmed clear](local-data-after.png), [populated mobile panel](local-data-mobile-before.png), [mobile after clear](local-data-mobile.png). The populated mobile dialog scrolls vertically; there is no horizontal overflow. Game audio uses only the application's gain mute; no browser/OS global mute is applied.
- Retained harness failures: [wrong CPU field](harness-cpu-field-failure.txt), [single-page context](harness-context-failure.txt), [ambiguous Right selector](harness-selector-failure.txt). These were failed development checks, not product acceptance. The corrected candidate's complete browser results are linked above.
- Author draft repair: [before-fail CPU result](replacement-before.txt) showed boot RAM 0 instead of 90 when reselecting the same ROM before its first periodic save. [Focused after-pass](replacement-after.txt) and the complete current browser run confirm capture now commits before candidate restore. Concurrent captures share the pending write promise. The original browser/preflight evidence remains in earlier commits; this was author cleanup, not an independent review round.
- Requirement snapshots: [issue and assignment history](issue-source.json), [epic](epic-source.json). The [technical guide](../d06-persistence.md) preserves governing approval lineage and remaining D06 obligations.

The browser probe waits for the actual ten-second persistence timer. Its cartridge program reads SRAM into CPU work RAM at boot; the exported real state independently confirms the restored byte. The other-build record is explicitly synthetic, preserving/exporting unknown bytes without claiming unavailable historical-core compatibility. Storage records contain only the documented metadata and state/battery/preferences fields; request observations show local asset GETs only.

Shared invariants remain single-owned: Rust `local_file` owns compatibility and the trusted cap/info; both codec consumers use it. The existing worker/player request correlation owns all file operations. `saves.ts` owns database transactions, expected-byte comparison and the clear generation. Controls validation reuses the same actions and conflict function as remapping; fingerprint matching and preference identity use `fileIdentity`. No peer NROM admission, mapper save-profile guard, whole-state decoder or file-limit copy was introduced.

D06 remains open for measured ten-second/32-MiB rewind and remaining agreed qualification. Unload persistence is best-effort, browser eviction can erase records, and arbitrary state-restore PCM continuity remains unsupported. Root owns merge after fresh independent acceptance, current CI and integration verification.

## Independent round 1 repair

[Independent round 1](https://github.com/TuringTestee/retro-coop/pull/55#issuecomment-5748797704) returned AgreeButChangesRequested, scores 4/4/2/4, because an unchanged `NaN` battery timestamp could not be deleted. The [local before-fail](timestamp-before.txt) and [after-pass](timestamp-after.txt) use real React/IndexedDB and verify exported bytes plus preservation of an unrelated save. The full current browser additionally proves metadata-only corruption does not block play or trigger automatic export, and that changing `NaN` to `null` during confirmation still refuses stale deletion for battery and preference records.

The shared byte-record comparison now uses `Object.is` for timestamp equality, and battery retry consumes that same comparison instead of its own timestamp-only guard. Preference deletion checks timestamp identity before JSON value comparison. `validSavedAt` is the single normal-timestamp policy used by slot listing, battery autoload and recovery display. Explicit recovery can delete unchanged malformed metadata; automatic battery persistence stays disabled for that metadata.

Main PR #54 was integrated in merge commit `eb8c72f` before final proof; its peer changes do not replace the persistence owners. Prior failures, author repairs and round history remain accessible in earlier commits and the linked review. No independent acceptance is claimed for the repair; root owns fresh review and merge.

Prior-head CI [35500467197](https://github.com/TuringTestee/retro-coop/actions/runs/35500467197) completed successfully before this repair was pushed; it was not cancelled or represented as current-head CI. The repaired head requires its own unchanged-budget run.
