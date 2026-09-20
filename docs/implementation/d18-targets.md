Audience: Agent

# Confirmed moderation targets

A delayed host removal must affect only the guest the host confirmed. This D18 slice also binds room changes to the displayed room, so delayed actions cannot change a replacement room. Operator tooling and remaining D18 adversarial qualification stay open under issue #22.

## Cause and ownership

Previously `kick` named no target. The coordinator correctly authenticated the host but applied the request to whichever guest occupied the slot when it arrived. A voluntarily departing guest could be replaced before that request arrived. The same missing room target affected close, rename and visibility.

`packages/contracts/src/rooms.ts` owns strict command shapes. `Rooms.reserve` now creates an unpredictable membership generation on every admission, independent of the client-selected reservation intent. `Rooms` owns its lifetime, publishes it only to room participants, and uses the same generation for guest chat authorization and removal. `releaseGuest` clears its retry receipt and generation. Reusing an old join intent does not revive old chat/removal authority. Reservation intents continue to own cancellation and peer preparation; no second scheduler or changed reservation deadline is introduced.

`Rooms.hosted` owns host authorization and expected-room checks. The UI and file-replacement path capture the displayed room ID before confirmation. All close/rename/visibility commands name it; kick also names the guest generation. Failure preserves current room state and explains that the target changed. Existing session-token revocation and peer teardown remain the owners of successful removal. This does not claim to ban a person who creates a new anonymous session.

Matching-path inspection covered all four host mutations, file-driven room replacement, chat send/event/receipt cleanup, reservation cancellation, peer epoch creation and all typed callers. Existing room, peer and chat tests now supply explicit targets. No legacy targetless mutation parser remains.

## Proof and reproduction

Source candidate: `e81cce7` over integrated base `31713b08b851312e0f82d7723e81e90500c7da8f`. The four new coordinator regressions fail against the original base ([raw output](d18-targets/before.txt)) and pass after the repair as part of all 53 Node tests ([output](d18-targets/node.txt)). Before reproduction: copy `apps/coordinator/src/moderation.test.ts` into a detached base checkout and run `node --test apps/coordinator/src/moderation.test.ts`. This fails on behavior assertions, not setup.

`npm run typecheck`, `npm test`, and `npm run build` pass. The [native browser result](d18-targets/browser.json) uses bundled full Chromium 145.0.7632.6 through Playwright 1.58, actual room WebSockets and actual fake-device media transport. It holds a real UI-confirmed kick at its outgoing socket, lets the first guest leave and a replacement join, then releases the old request. The replacement retains its peer and microphone. A new confirmed kick closes both peers and all tracks; the removed session cannot rejoin, while the earlier guest can. No host worker, load or imported timeline is replaced. Both directions report received audio energy before removal. The [inspected screenshot](d18-targets/stale.png) shows the stale-target explanation alongside the current occupied room and live voice; the invitation is masked.

Reproduce after building: `PLAYWRIGHT_BROWSERS_PATH=<pinned browsers> python scripts/rooms/moderation_smoke.py --output /tmp/moderation.json`. Runtime was 2.53 seconds. Chrome global audio muting is removed; game output is muted in the app and remote voice volume set to zero through its control. Fake microphone transport verifies lifecycle/decoding, not human listening or physical devices. The focused CI check has a 60-second hard timeout within the existing shared 30-minute budget. The complete source/evidence preflight passed in 11.57 seconds after normalizing trailing whitespace in the retained before-failure log; the first hygiene-only failure took 0.02 seconds. Current final-head gate and review status are recorded on the PR. After integrating actual rewind merge `bc60beda8aeaa6523bfe72f5f07e3db1bf842c7a`, source `c986b82465534dbc3ec67ca631488c09255ea179` passed a fresh build and the same browser check in 2.60 seconds ([result](d18-targets/integrated-browser.json)). The matched [before](d18-targets/before.png) and [after](d18-targets/after.png) screenshots were inspected: current guest and live voice remain visible while the failed stale action receives its explanation. Only evidence files changed afterward. CI and independent review remain pending.

## Governing scope

Epic #2 approved planning PR #3 at `2e8adfcd3259f5bdffdc9a13ef9b983f78cfb965`, merged as `ecf6bd4c7443526f0a163b721a351c854ee90fd4`. This implements the existing U9/S26 confirmation and revocation behavior under D18; it changes no product requirement. D18 depends on integrated D09/D10/D16/D17. The project-specific documentation paths are preserved. Root owns implementation and merge under the existing repository-scoped policy B; substantive independent review and passing checks are required before merge.
