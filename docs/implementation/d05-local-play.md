Audience: Agent

# Local NES file-to-play

The application now starts a local NES game after one picker or drop action. It generates neutral guest/session names, keeps file bytes in the browser, and preserves the previous game when another selection fails or is cancelled. Online rooms and persistent saves remain later issues.

This records the D05 checkpoint. The subsequent [D08 room guide](d08-rooms.md) describes the current coordinator and hosting flow.

## Run and verify

Use the README's pinned tools, then `npm ci`, `sh scripts/foundation/prepare.sh`, and `npm run dev`. Open the printed local URL and choose an uncompressed NES cartridge. Arrow keys move, X/Z map to A/B, Enter is Start, Shift is Select; choose a detected gamepad in Settings to use it while the screen has focus. Game output starts muted; Unmute affects only the application's gain. Window blur/background pauses play. See [D07 controls and presentation](d07-controls.md) for remapping, controller recovery, filters, volume and fullscreen. Resume continues the existing worker rather than restarting progress.

For a production bundle run `npm run build`. With Playwright 1.58.0 and Chromium installed:

```sh
python3 scripts/foundation/browser_smoke.py --output /tmp/foundation.local.json
```

`--chrome` uses installed Chrome. The browser check uses the original generated diagnostic, never a downloaded commercial title. It observes rendered changes from input and nonzero PCM scheduled through the muted game gain; checks picker/drop, invalid file/hardware preservation, cancellation and late digest completion; compares exact ROM and WASM hashes; proves audio denial leaves frames running and explicit retry recovers; loads representative mapper headers 0/1/2/3/4/7 and an NES 2.0 file over 8 MiB; inspects outbound methods/URLs and mobile overflow. These fixtures exercise admission and basic execution, not bank switching or the complete D20 compatibility matrix. Browser evidence and screenshots are retained by CI's existing `foundation.local.*.png` artifact pattern.

The README's full `timeout 60s sh scripts/preflight.sh` includes focused header tests, generated-name isolation and existing TypeScript/service/codec checks. Presubmit retains the shared 30-minute deadline. No additional long post-submit test is required for this slice. The release-level 30-attempt cross-browser startup budgets remain D21/D23 qualification; the single browser smoke is not a p95 claim.

## Boundaries and reuse

`cartridge.ts` checks iNES/NES 2.0 structure and declared minimum length before invoking the core. There is no title/hash/mapper allowlist and no application 8 MiB ceiling, preserving the later user clarification and integrated PR #40. Safe integer/length validation prevents impossible declared sizes. Available browser memory and the pinned emulator determine actual admission. Archives and disk formats fail locally; unsupported hardware returns the core's error with a new-file action. Compatibility is labelled experimental until the later hardware matrix qualifies it.

`LocalPlayer` owns candidate/active workers, abortable file reads, generation tokens, input, audio and browser lifecycle. Only a successfully initialized candidate replaces the active worker. Aborting loading, a newer selection, disposal, or blur invalidates pending intent; stale reads/digests/worker messages cannot start a cancelled game. File chooser dismissal is a no-op. Active game input and audio remain separate from candidate initialization. Consumers can build saves, control settings and room transitions on this owner in subsequent dependent issues.

The local fingerprint uses SHA-256 over **all exact file bytes**, the actual loaded WASM bytes, a versioned local settings descriptor and cartridge header metadata. This is browser-local identity, not an approved peer checkpoint/schema or a claim that header metadata fully describes runtime behavior. Later multiplayer must add the approved state-schema contract. No filename is used in identity, display names, request URLs or storage. Random defaults are generated independently of the cartridge, without implying authenticated identity, published rooms or server-issued sessions. D08 owns that transition.

Source authority: D05 in epic #2 / issue #9, approved head `2e8adfcd3259f5bdffdc9a13ef9b983f78cfb965`, merged planning PR #3 at `ecf6bd4c7443526f0a163b721a351c854ee90fd4`; D04 integrated at `e825fe1858f446e74f0c6c1ed35d56a661856665`. This delivers AC-02/08/13 local portions and S02/S36 within D05. Public/unlisted room creation, visibility controls, editing hosted names and network readiness belong to the dependent D08/D09/D11 issues, so this application does not present nonfunctional hosting controls.
