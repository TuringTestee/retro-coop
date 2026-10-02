The current implementation opens on the lobby list, creates a lobby before selecting a NES game, requires occupied controller owners to prepare before Start, and ends the active session before returning to the list.

Audience: Agent

# Earlier minimal-room implementation

The [unified lobby plan](unified-lobbies.md) owns current UI and Start behavior. The [access and routing plan](room-access-and-routing.md) owns Public or Password protected admission and automatic connection routing. This document remains only as a redirect for older references; its old Create Game page, all-member Ready gate, Public rooms toggle, and manual connection policy are superseded.

A successful exit closes or leaves the room, stops game execution and media, and then navigates. A failed exit retains the playable context and offers recovery. The unified plan's public-entry verification proves this together with the current preparation and play journey.
