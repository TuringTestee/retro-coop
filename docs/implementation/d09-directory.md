Audience: Agent

# D09 public room discovery

This is shipped D09 evidence. The later [room access and automatic routing plan](room-access-and-routing.md) supersedes unlisted non-discovery and invite-only admission for new rooms; protected rooms become listed and password-gated.

Players can browse current public rooms, search by room or host name or exact public code, and reserve an available Player 2 place before choosing a matching local game. Unlisted rooms remain invitation-only. [The two-game catalog amendment](included-games.md) owns D19's Super Tilt Bro and From Below launchers; this delivered directory supplies their shared filtering and room rows.

## Ownership and boundaries

`packages/contracts/src/directory.ts` owns code alphabet, length, normalization and case-insensitive search. `rooms.ts` owns protocol parsing and `ReservationRequest`; invite and code requests derive the same attempt identity. Coordinator `Rooms.reserve` owns rate limits, current membership, host availability, capacity checks, slot claim and the unchanged 120-second lease for both entry routes. Directory snapshots reuse the existing metadata-only `preview` projection, never member views; only confirmed public rooms are emitted. Code allocation reserves the map entry synchronously and retries collisions with a bounded failure. Unlisting revokes the old code.

The server sends bounded snapshots (maximum 20 rooms) to subscribed authenticated guest sessions after creation acknowledgement, metadata/visibility changes, reservation changes, recovery and closure. Stable creation order and React room IDs retain row identity. Removing a focused row returns focus to search; unavailable join buttons keep focus using `aria-disabled` and a guarded action, so Chrome does not blur them to the document body. Disconnection preserves stale results with joins disabled; explicit Retry reconnects and subscribes again. Failed heartbeat probes close the socket rather than leaving a silent stale directory actionable.

`RoomClient.joinTarget` owns cancellation and intent-scoped cleanup for code and invitation joins. No ROM or filename is sent. Peer policy, connectivity and gameplay admission remain D10/D11 work; current UI calls the guest place reserved. No public infrastructure is provisioned here.

Current checks follow the [verification strategy](browser-nes-platform.md#verification-strategy).
