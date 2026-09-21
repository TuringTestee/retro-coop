Audience: Agent

# D09 public room discovery

Players can browse current public rooms, search by room or host name or exact public code, and reserve an available Player 2 place before choosing a matching local game. Unlisted rooms remain invitation-only. [The two-game catalog amendment](included-games.md) owns D19's Super Tilt Bro and From Below launchers; this delivered directory supplies their shared filtering and room rows.

## Ownership and boundaries

`packages/contracts/src/directory.ts` owns code alphabet, length, normalization and case-insensitive search. `rooms.ts` owns protocol parsing and `ReservationRequest`; invite and code requests derive the same attempt identity. Coordinator `Rooms.reserve` owns rate limits, current membership, host availability, capacity checks, slot claim and the unchanged 120-second lease for both entry routes. Directory snapshots reuse the existing metadata-only `preview` projection, never member views; only confirmed public rooms are emitted. Code allocation reserves the map entry synchronously and retries collisions with a bounded failure. Unlisting revokes the old code.

The server sends bounded snapshots (maximum 20 rooms) to subscribed authenticated guest sessions after creation acknowledgement, metadata/visibility changes, reservation changes, recovery and closure. Stable creation order and React room IDs retain row identity. Removing a focused row returns focus to search; unavailable join buttons keep focus using `aria-disabled` and a guarded action, so Chrome does not blur them to the document body. Disconnection preserves stale results with joins disabled; explicit Retry reconnects and subscribes again. Failed heartbeat probes close the socket rather than leaving a silent stale directory actionable.

`RoomClient.joinTarget` owns cancellation and intent-scoped cleanup for code and invitation joins. No ROM or filename is sent. Peer policy, connectivity and gameplay admission remain D10/D11 work; current UI calls the guest place reserved. No public infrastructure is provisioned here.

## Verification

- 25 Node tests cover existing room behavior plus metadata privacy, provisional/unlisted exclusion, live lifecycle, code collisions, shared invitation/code race, fixed reservation deadline, invalid-code rate limits, and duplicate-name/name/code search.
- `scripts/rooms/directory_smoke.py` exercises actual production client and coordinator in independent Chrome tabs: empty state, duplicate room names with distinct codes, search, live rename/focus, reservation before file, matching file, disabled full rows, unlisting/focus recovery, socket loss/stale rows and Retry. Raw result is in `evidence/d09/directory.json`; screenshots are uploaded with PR/CI evidence. The browser removes Chromium's default global mute; the application's existing muted game gain remains in effect.
- Existing room lifecycle and foundation/settings/battery browser suites remain regression gates. The short directory probe remains required evidence; current placement and budgets follow the governing [verification strategy](browser-nes-platform.md#verification-strategy).

An initial browser harness used Playwright offline mode to simulate an established WebSocket outage; Chrome left that socket connected, so the harness now closes the actual tab socket and verifies the visible recovery path. Initial author checks also caught Node strip-only incompatibility in a constructor parameter property and short synthetic protocol IDs; both were corrected before handoff. Browser coverage is local Chrome, not the later cross-browser/accessibility/release acceptance matrix.
