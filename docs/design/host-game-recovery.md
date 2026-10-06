Keep the player’s chosen name and recover hosted progress after interruption. A live rejoin reacquires the exact game; an expired lobby uses a new invitation. If the host’s progress cannot be recovered, restart the lobby game clearly instead of trapping everyone in preparation.

Audience: Human

# Recover a hosted game

Source: [#199](https://github.com/TuringTestee/retro-coop/issues/199) and the owner's requested persistent name and recovery feature. This extends [the shared lobby journey](lobby-refactor.md).

- A brief reconnect with a retained emulator keeps the existing lobby and its current authority. A full refresh loses that emulator even when membership survives; it must reacquire the selected game and recover its timeline before preparing. A remembered name or save never gives ownership of an old lobby.
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

## Refresh and preparation recovery

Source: [#263](https://github.com/TuringTestee/retro-coop/issues/263), reproduced on current production for the host. This supplements the expired-lobby journey above; it does not revive old membership or permit guests to reset a healthy host.

- Loading the exact already-selected cartridge is acquisition, not game replacement. Apply this distinction to hosts, players and watchers, for included and uploaded games. Preserve the prohibition on replacing a running game.
- Show one large centered spinner and the actual preparation stage inside the game frame while downloading, loading or synchronizing. Disable the preparation action until its prerequisites hold; keep cancellation or a useful error remedy. Do not leave an enabled action that sends nothing.
- A player or watcher refresh uses the current host’s verified checkpoint. A host with retained native state follows ordinary preparation. A refreshed host without its native timeline validates the newest compatible automatic capture, or its valid older copy, before restoring a paused shared timeline. State the capture time; do not promise unsaved progress survived.
- If that host cannot recover any valid progress by the existing preparation deadline, automatically restart the selected game from its beginning in the same lobby. Keep its access/password, invitation, names, slots, saved copies and chat; invalidate the failed game epoch and stale preparation. Explain that the old progress could not be recovered. Everyone required prepares before play resumes. A disconnected guest cannot initiate this fallback.
- Errors name the failed stage and relevant remedy. A failed ROM download/storage read remains retryable; a coordinator timeout names missing participants or acknowledgements. Exit, game/role changes and a newer recovery attempt revoke pending callbacks and clear the spinner. Never clear all browser data to repair this path.

Acceptance: actual host/P2/watcher refresh during current public play, both included and uploaded cartridges, with and without valid automatic captures. Observe restored/fresh native frame and hash agreement, real P1/P2 input and responsive preparation. Exercise corrupt/incompatible capture, acquisition retry, deadline fallback, cancellation, repeated refresh and healthy-host protection. Show matched failure/success captures and the centered loading state. Expired-lobby recovery and ordinary reconnect remain required.
