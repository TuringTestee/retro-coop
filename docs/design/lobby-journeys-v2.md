Retro Coop's lobby list should carry a visitor into a real session, whether the session starts empty, already has a host, or uses another player's local NES file. The host decides when to start; every failure leaves a clear next action.

Audience: Human

# Lobby journeys after the server-room direction

This is the journey artifact based on [direction and reference evidence](lobby-server-rooms-direction.md). It is a proposed interaction map, not a claim that the current app implements these paths.

The approved [room game download journeys](room-rom-transfer.md#journeys) replace J2's matching-file recovery and J5's bring-your-own-file outcome for host-provided custom rooms; transfer issues #87–#91 are integrated. The proposed [Create Game journeys](create-game-library-journeys.md) replace the immediate-host entry in J5 after their own approval and implementation. Included-game claim, host Start and friend discovery still apply.

| Journey | Entry and decision | Action and feedback | Outcome and recovery |
|---|---|---|---|
| J1: Be first in an included-game room | Open the public list; see Super Tilt Bro or From Below at **0/2 · Waiting for host**. | Select **Join as host**. The service atomically assigns this visitor Host/P1; the browser downloads and verifies the included file. | Enter the same room at 1/2 with **Start game**, **Copy invite**, and **Leave**. If another visitor claimed first, show the new room state and offer Guest join or a fresh 0/2 room. If the asset fails, keep or release the claim honestly and offer Retry/Leave. |
| J2: Join an existing host | Open the same list; identify a specific waiting room by game, host, code, occupancy, and state. | Select **Join** on a waiting 1/2 room. Reserve P2 and prepare the exact game locally. | Enter that room as Guest/P2 and see the host's readiness. Correct an unavailable/mismatched file, retry a failed connection, or leave without changing the host's game. A playing room has Join unavailable. |
| J3: Start and play as host | From a 1/2 room, decide whether to wait or play now. | Select **Start game**. Show loading and the actual start result; do not imply a second player exists. | Play solo in the same room. The room remains listed as Playing with Join unavailable; the host may pause or leave. A ready guest present before Start enters the shared start barrier. |
| J4: Add a guest to ongoing play — deferred | Find a playing 1/2 room. | See Playing · Join unavailable; choose another waiting room. | A future progress-preserving late-join design must define transfer, consent, failure, and recovery before enabling this action. It is outside the essential refactor. |
| J5: Host a personal NES file | See **Host your NES file** beside the public list; Public is the default and Unlisted can be chosen before file selection. | Drop or choose a local `.nes` file. Validation automatically creates a waiting room with a generated neutral label; show progress and the confirmed row or invite. | Other browsers see a public room in the ordinary list and join with their own exact matching file. Never publish a local path or file bytes. Invalid file, capacity, cancellation, or stale creation retains the picker and offers correction without a ghost room. The host may rename after creation. |
| J6: Find a friend's room | Search by room/host or exact public code; an unlisted room arrives by invitation. | Open the matching row or invite preview; inspect game, host, slots, status, and network privacy, then Join if available. | Join that exact session. Duplicated labels stay separate by code; full, closed, or stale results explain the limit and offer a valid alternative. An unlisted room never appears in public search. |
| J7: Manage, finish, and return | In a room or game, check membership, game help, controls, communication, and current state. | Host may change room access, remove a guest, or close; each player may leave. Shared or destructive actions state their effect. | Return to the public list with a useful status. An empty service-created room remains available or is replenished; a human room closes when its host leaves. Disconnect, restart, save, and audio failures have local recovery where safe. |

## Cross-journey rules

- The directory has one list of all public rooms, including service-created and human-created sessions. Full or playing rooms may remain visible, with their real joinability shown; no special card duplicates an included game.
- The server maintains at least one 0/2 room for each healthy included game. A claim of the last empty room triggers replenishment without moving the claimant into a different room. If capacity prevents it, explain that new rooms are temporarily unavailable.
- From Below remains a one-player cartridge. A second browser joins the room for agreed controller sharing or handoff, not fictional simultaneous P2 gameplay.
- Player-owned file rooms never imply that the site supplies that game. A supplied path such as `a player-selected local NES file` is private local input, not a public title, URL, or downloadable asset.

## Step 3 principle check

| Decision point | One primary forward action | Information needed now | Result/recovery traced above |
|---|---|---|---|
| Empty included-game row (J1) | Join as host | Game, 0/2, first joiner becomes Host/P1 | Claim and race recovery |
| Waiting 1/2 row (J2) | Join | Current host, game, open slot, matching-file requirement | Guest preparation or correction |
| Playing 1/2 row (J4, deferred) | Choose another waiting room | Playing status and Join unavailable reason | No false later-join promise |
| Local-file hosting (J5) | Drop or choose file | Public/Unlisted choice and peer privacy before selection; validation result after | Generated waiting room or retained picker with correction |
| Host waiting room (J3) | Start game | Whether Start begins solo or with a ready guest | Same room plays, or loading/start failure |
| Guest waiting room (J2) | Wait for host after preparing game | Host identity and readiness | Shared start, Cancel/Leave, or mismatch correction |

J6 invitation is a different entry to the same room, not a second forward action in the public list. J7's help, settings, communication, and exit actions appear in their usable room/play states. No promotional step is needed. The next scenario inventory must check the small tasks and failures explicitly.
