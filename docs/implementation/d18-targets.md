Audience: Agent

# Confirmed moderation targets

A delayed host removal must affect only the guest the host confirmed. This D18 slice also binds room changes to the displayed room, so delayed actions cannot change a replacement room.

## Cause and ownership

Previously `kick` named no target. The coordinator correctly authenticated the host but applied the request to whichever guest occupied the slot when it arrived. A voluntarily departing guest could be replaced before that request arrived. The same missing room target affected close, rename and visibility.

`packages/contracts/src/rooms.ts` owns strict command shapes. `Rooms.reserve` now creates an unpredictable membership generation on every admission, independent of the client-selected reservation intent. `Rooms` owns its lifetime, publishes it only to room participants, and uses the same generation for guest chat authorization and removal. `releaseGuest` clears its retry receipt and generation. Reusing an old join intent does not revive old chat/removal authority. Reservation intents continue to own cancellation and peer preparation; no second scheduler or changed reservation deadline is introduced.

`Rooms.hosted` owns host authorization and expected-room checks. The UI and file-replacement path capture the displayed room ID before confirmation. All close/rename/visibility commands name it; kick also names the guest generation. Failure preserves current room state and explains that the target changed. Existing session-token revocation and peer teardown remain the owners of successful removal. This does not claim to ban a person who creates a new anonymous session.

Matching-path inspection covered all four host mutations, file-driven room replacement, chat send/event/receipt cleanup, reservation cancellation, peer epoch creation and all typed callers. Existing room, peer and chat tests now supply explicit targets. No legacy targetless mutation parser remains.

## Governing scope

Epic #2 approved planning PR #3 at `2e8adfcd3259f5bdffdc9a13ef9b983f78cfb965`, merged as `ecf6bd4c7443526f0a163b721a351c854ee90fd4`. This implements the existing U9/S26 confirmation and revocation behavior under D18; it changes no product requirement. D18 depends on integrated D09/D10/D16/D17. The project-specific documentation paths are preserved. Root owns implementation and merge under the existing repository-scoped policy B; substantive independent review and passing checks are required before merge.
