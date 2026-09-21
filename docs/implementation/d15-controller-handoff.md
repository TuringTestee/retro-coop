Audience: Agent

# Controller modes and handoff

Players can keep the game’s native P1/P2 controls or take turns owning P1. The host requests a change while waiting or paused; both players accept before preparing to resume. Declining, cancelling or losing the connection preserves game progress and prevents automatic resume.

This implements [D15/#19](https://github.com/TuringTestee/retro-coop/issues/19), S35 and the controller portion of AC-15 under the approved plan. Governing sources are [design](../design/browser-nes-platform.md), [UI U7/U9](../design/browser-nes-ui.md), [architecture](browser-nes-platform.md) and [audit D15](browser-nes-audit.md), approved at `2e8adfcd3259f5bdffdc9a13ef9b983f78cfb965` and merged through PR #3 as `ecf6bd4c7443526f0a163b721a351c854ee90fd4`. D11 prerequisite merged through PR #59 as `bae5d860e8a294e827e454e64a7f9a76c5488fd7`.

## Observed author evidence

The final production source `de862986b1de6830d1848146bf803836b3360205` passed [Chrome/Chrome](evidence/d15/chrome.json) in 10.84 seconds and [Chrome/official Firefox 146.0.1](evidence/d15/mixed.json) in 20.23 seconds, with the same built JavaScript/WASM hashes recorded in both results. Both workers observed swapped `[64,128]`, held-input `[0,0]`, and sole-owner `[128,0]` native controller-port RAM. Each final pause matched canonical hashes; no page errors occurred. The scenarios also inject stale-epoch input after transfer and activate consent by keyboard with focus restored to the controller panel.

The [preflight log](evidence/d15/preflight.log) passed all 91 Node tests and native/repository checks in 25.72 seconds under the hard 60-second limit. The unchanged [19-scenario gameplay suite](evidence/d15/gameplay-suite.json) passed in [171.50 seconds](evidence/d15/gameplay-regression.log), below its unchanged 180-second limit, on source `c7a80dd`; the subsequent source repair only returns focus after controller consent. [Rooms](evidence/d15/rooms.json), [directory](evidence/d15/directory.json) and [direct/relay peer regression](evidence/d15/peer.json) passed in 7.06, 2.86 and 69.11 seconds respectively. Those three runs used the c7 ownership-display bundle and checked the updated guest-seat wording.

Inspected matched screenshots: [default separate controllers](evidence/d15/before.png), [shared P1 after handoff](evidence/d15/after.png), and [Firefox guest](evidence/d15/guest-firefox.png). Invitations are masked. The diagnostic has a plain grey display; controller-port RAM and canonical state hashes, rather than visible artwork, prove input behavior.

Initial development probes exposed missing explicit select accessible names (fixed) and a local coturn executable missing from PATH (corrected environment). Superseded CI run `35516512230` was cancelled before completion because source repairs were pending. It supplies no CI acceptance. Current-head CI and fresh independent review remain required; the author draft pass supplies no verdict. The evidence-only commit does not alter production source; current-head rerun results are published on PR #64.

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

This scenario retains its focused command bound and D11 coverage; current workflow scheduling and budgets follow the governing [verification strategy](browser-nes-platform.md#verification-strategy). The change does not claim broad hardware qualification, real-title simultaneous co-op, or a tested alternating-turn title: the interface explains that those behaviors belong to the ROM. D20 retains hardware/game qualification. D12/D13 retain late join and recovery scope. Root is the sole merge owner; fresh independent review and passing current-head CI remain required.

## CI keyboard chooser follow-up

The first complete CI attempt failed at the foundation test’s keyboard file chooser, after core qualification passed. Its [retained event trace](evidence/d15/picker-repair/ci-failure.json) shows Enter reaching the correct button, an unprevented button click and an unprevented hidden file-input click, with focus and user activation intact. The selector and D15 keyboard suppression were therefore not blocking the action. The preceding coordinator 404 is expected from this deliberately static, local-only test server. [Run 35516932664](https://github.com/TuringTestee/retro-coop/actions/runs/35516932664) remains failed evidence, not acceptance.

The harness now awaits Chromium’s `Page.setInterceptFileChooserDialog` acknowledgement after subscribing to the chooser and before pressing Enter. Python Playwright’s ordinary listener subscription uses `send_no_reply`; it supplies no explicit readiness acknowledgement at that call site. A bounded native protocol trace is retained alongside the existing focus/key/click diagnostics. The test still requires the single keyboard action to produce an actual Playwright file chooser, selects the ROM through that chooser, and runs the unchanged local-play workload. No product behavior, selector, timeout, assertion or retry policy changed.

The [focused full foundation result](evidence/d15/picker-repair/foundation.json) passed in 73.92 seconds (74.45 seconds including process cleanup, under the existing 90-second bound). [Raw output](evidence/d15/picker-repair/foundation.log) and [chooser proof](evidence/d15/picker-repair/picker.json) show acknowledged interception, the native single-file chooser event with its input node, successful chooser delivery and no page errors. Local frames/audio, replacements, controls, save/rewind and privacy checks all ran. The original CI browser failure is not fully explained by the available trace: the repair removes an observer-readiness gap without claiming a reproduced Chromium root cause. New-head CI remains the required validation gate.

## Sustained-input qualification follow-up

The repaired chooser passed CI, but the Firefox/Firefox qualification then exposed a workload timing error. [Run 35517990601](https://github.com/TuringTestee/retro-coop/actions/runs/35517990601) completed its browser workload in 633.82 seconds with equal states, yet correctly failed the sustained-input validator. The [original artifact](evidence/d15/sustained-input/failed-ci-600.json) shows 36,203 frames, an initial manual-check pause at frame 508 and only 594 scripted transitions on each peer, below the unchanged required 595. Automation began after resume, while the measured 600 seconds included the variable manual-check phase. Its assumed 300-frame allowance did not cover the slower initial phase. This is a harness workload error, not evidence of dropped product input.

The harness now arms scripted controls while paused and measures the full 30/600-second qualification interval after resume. Input cadence, transition counts, all acceptance thresholds, the delivery-time network and CI bounds were unchanged. The existing eight-second fault/journey smoke still measures both epochs, preserving its 180-second suite allocation. A diagnostic `--initial-manual-frames 508` option exercises the slow setup without changing the default workload. No product source or emulator code changed.

A [focused official Firefox/Firefox run](evidence/d15/sustained-input/firefox-30.json) used the real isolated packet-impairment profile. Its initial phase actually reached 757 frames; the resumed phase sustained 30.02 seconds, generated 31 transitions per peer (required 25), and ended at 2,672 equal committed frames with identical hashes. The [unchanged validator passed](evidence/d15/sustained-input/firefox-30.log), including actual impaired-packet evidence. Browser time was 85.86 seconds, 90.60 seconds including namespace cleanup, under the local 120-second bound. The original 600-second artifact [still fails](evidence/d15/sustained-input/original-rejection.log); it has not been relabelled as acceptance.

The [tested harness hashes and reproduction command](evidence/d15/sustained-input/tested-harness.json) bind the working-tree harness to these observations; the browser artifact names unchanged production source `a8d7b09`. Eight verifier/timing tests include the 508-frame setup case and prove one missing transition still fails. TypeScript and all 91 Node tests pass. This short run is focused repair evidence, not a replacement for the new-head full 600-second CI matrix or independent review.
