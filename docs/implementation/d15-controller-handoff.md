Audience: Agent

# Controller modes and handoff

Players can keep the game’s native P1/P2 controls or take turns owning P1. The host requests a change while waiting or paused; both players accept before preparing to resume. Declining, cancelling or losing the connection preserves game progress and prevents automatic resume.

This implements [D15/#19](https://github.com/TuringTestee/retro-coop/issues/19), S35 and the controller portion of AC-15 under the approved plan. Governing sources are [design](../design/browser-nes-platform.md), [UI U7/U9](../design/browser-nes-ui.md), [architecture](browser-nes-platform.md) and [audit D15](browser-nes-audit.md), approved at `2e8adfcd3259f5bdffdc9a13ef9b983f78cfb965` and merged through PR #3 as `ecf6bd4c7443526f0a163b721a351c854ee90fd4`. D11 prerequisite merged through PR #59 as `bae5d860e8a294e827e454e64a7f9a76c5488fd7`.

## Authority and input

`GameSession` owns the assignment, proposal, consent deadline and existing start/pause barrier. `Rooms` authenticates current members and requires both connected participants. Commands bind to the current peer epoch, game epoch and assignment revision or unpredictable proposal identifier. Only the host proposes/cancels; either participant can decline. Both must explicitly accept, including the host. Proposals expire after 15 seconds and block competing proposals and readiness. Starting/playing/pausing/late-join states reject assignment changes.

A proposal clears existing readiness and increments the revision, invalidating previously prepared readiness even when declined. Ownership changes only when both accept. Connection changes clear pending consent. Guest departure resets default assignments so a replacement cannot inherit the departed guest’s P1 authority; the game remains stopped until deliberate preparation/resume. Room `slot` identifies a membership seat, not a controller port.

The existing `GameClient` snapshots the acknowledged assignment at prepare and uses the single `GameScheduler`. Separate mode routes the owner to P1 and the other participant to P2. Shared mode discards nonowner input at sampling and maps P2 to zero even if a peer forges nonzero input. Each resume creates a new epoch; prior queued packets cannot affect the resumed game. No checkpoints, new scheduler or server emulation are introduced.

Keyboard auto-repeat cannot recreate a released key. Selected gamepad buttons and axes remain suppressed until each physical input is observed released, including while paused. Other newly pressed inputs remain usable. Consent controls use labelled native controls, keyboard activation and status announcements; current ownership names host/guest independently of P1/P2. Game audio stays muted through the existing in-app setting.

## Verification

Focused Node tests cover malformed commands, host authority, explicit two-party consent, readiness clearing, competing/playing/stale requests, timeout/cancel/decline/disconnect/replacement, fresh resume epochs, all role/mode/owner combinations, forged nonowner input and held-pad release.

The production browser scenario reads independently emulated controller ports from the diagnostic ROM’s RAM. It starts with native separate P1/P2, swaps the ports, switches to Shared P1 with the guest owner, verifies held keyboard/gamepad neutrality, releases/represses the pad, and passes P1 to the host. Both real browser workers must report the expected controller bytes and equal paused canonical hashes. Decline/cancel must preserve the original hash and one acceptance must not advance frames. Both consent actions use the keyboard. Matched desktop screenshots show assignments before/after and the guest view.

Reproduce after the standard foundation preparation and production build:

```sh
npm run build
python3 scripts/gameplay/browser_smoke.py --controllers --output /tmp/controllers-chrome.json
python3 scripts/gameplay/browser_smoke.py --controllers --pair Chrome-Firefox --firefox-executable /path/to/official/firefox --output /tmp/controllers-mixed.json
timeout --foreground 60s sh scripts/preflight.sh
```

Use the repository’s pinned Python Playwright/browser environment and official Firefox driver described in the D11 evidence. The browser command writes raw results and screenshots alongside its output. Native source is unchanged; exact accepted PR #59 WASM can be copied into the owned generated directory before building. Local test output directories and native targets must remain isolated.

CI runs this scenario separately under 45 seconds, preserving the existing 180-second D11 suite and the workflow-wide hard 30-minute deadline. The change does not claim broad hardware qualification, real-title simultaneous co-op, or a tested alternating-turn title: the interface explains that those behaviors belong to the ROM. D20 retains hardware/game qualification. D12/D13 retain late join and recovery scope. Root is the sole merge owner; fresh independent review and passing current-head CI remain required.
