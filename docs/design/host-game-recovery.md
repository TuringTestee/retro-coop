Remember the player's chosen name and offer to restore their last hosted game when its lobby has expired. Restore the exact game and saved progress into a new lobby; friends join again through a new invitation.

Audience: Human

# Recover a hosted game

Source: [#199](https://github.com/TuringTestee/retro-coop/issues/199) and the owner's requested persistent name and recovery feature. This extends [the shared lobby journey](lobby-refactor.md).

- A brief reconnect keeps the existing lobby and its current authority. A remembered name or save never gives ownership of an old lobby.
- While the host plays, save progress automatically in this browser. Capture at most once every 30 seconds after progress changes, and once when play pauses. Retain the two newest valid captures of the most recently saved hosted game. Manual Q saves remain separate.
- On reload or a replacement guest session, restore the chosen display name before the player hosts or joins. If storage fails or the value is invalid, use a normal guest name and keep play available.
- Hosting still creates a lobby immediately, without choosing a game first. If recoverable progress exists and this browser has no live lobby to reconnect to, show one centered dialog in the new lobby: the game name and saved time, **Restore game**, or **Start fresh**. Keep the lobby usable while people join. Start fresh dismisses and discards that recovery offer; ordinary game loading stays available.
- Restore loads the exact remembered ROM and compatible saved state. Keep the restored game paused until the controlling players prepare and the host resumes. New and returning guests receive its current state through the existing synchronization path. Show the new lobby's invitation; old membership and invites are not restored.
- Missing ROM, incompatible state, corruption, or failed storage must explain that restoration could not complete and return to normal game loading. A valid older capture may be offered with its actual time. Never claim progress was restored until validation and import succeed.
- Identity edits stay in the existing centered name dialog. Recovery uses the existing lobby, game, slots, settings, chat and bottom actions; it adds no settings page or duplicate navigation.

## Acceptance journeys

1. Host and guest play, progress is saved, the hosted lobby expires, and the host reloads with a replacement guest session. Their chosen name survives. Host creates a new lobby, restores the saved game, a guest joins/prepares, and both continue from matching state with real controller input.
2. Brief same-session reconnect resumes the live lobby without a recovery offer or duplicate lobby.
3. Missing/corrupt/incompatible data and unavailable storage preserve the normal host/join/load path. Clearing local data prevents delayed captures from recreating it. A saved name never restores stale controller authority.

Technical boundaries and delivery: [implementation plan](../implementation/host-game-recovery.md).
