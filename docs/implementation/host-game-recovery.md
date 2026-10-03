Use the existing verified ROM library, IndexedDB owner and checkpoint protocol to recover a host's progress. Make restoration explicit and establish fresh membership before any guest can control the new game.

Audience: Agent

# Host game recovery implementation

Governing direction: [recovery journey](../design/host-game-recovery.md), [#199](https://github.com/TuringTestee/retro-coop/issues/199), and [five-slot checkpoint safety](five-slot-lobby.md). This plan must be independently reviewed and merged before implementation.

## Ownership and state

- `saves.ts` remains the sole IndexedDB owner. Add one recovery store through a versioned upgrade; do not put automatic captures in manual save slots. Atomically retain two snapshots plus the exact ROM hash, core/settings compatibility identity, title, completed frame, state hash and saved time. Keep the most recently captured hosted game only. Reuse existing state-size/import validation and bounded database deadlines.
- ROM bytes remain in the existing verified ROM library. Included ROMs resolve through their tracked catalog identity. Recheck hash and compatibility before import; a stale title, filename or remembered lobby ID is never identity proof.
- Export snapshot bytes and their frame/hash metadata in one worker operation at a completed boundary. Separate RPCs can observe different frames. Serialize captures and guard completion with the current player, selection, lobby and local-storage generations; exiting, replacing a game, clearing data or an intervening write revokes stale work. Failed writes keep the prior valid capture and surface existing storage feedback without stopping play.
- Capture only for the current host of shared play, every 30 seconds when completed progress changed and at a completed pause. Do not promise a final asynchronous write on browser termination. Timers stop with their owning session. Retention and capture intervals follow the human direction above; no background game is kept alive for saving.
- Persist the chosen display name separately from guest tokens with the same validation as the nickname command. Apply it through existing session authority before host/join requests become eligible. Invalid/unavailable storage falls back safely; no remembered token, slot or membership grants authority.

## Restore through the existing lobby

Create the lobby through the usual single host action. Only an expired/absent live membership with an available recovery record gets the centered restore/start-fresh dialog. An existing live reconnect takes precedence. Start fresh removes that offer without changing manual saves, ROM library or chosen name.

Restore validates the newest capture against the exact loaded ROM/core/settings, falling back to the older capture only with truthful time/notice. Import the state transactionally into the paused host before establishing shared play. Failed import leaves a safe normal load path and does not publish restored progress.

Add the smallest explicit host-authorized initialization of a restored paused timeline to the existing room/game protocol. Require the current host membership, selected matching game and unused lobby timeline; bind the actual imported frame/hash and fresh epoch. This is distinct from a power-on initial Start: progressed state must never be asserted fresh. Reuse existing prepare/checkpoint/acknowledgement/resume barriers so each current controller receives the restored state before input authority commits. Former guests join using the new invitation and new membership; observers do not gate preparation. Do not revive an old epoch or add host migration.

Keep authority in `Rooms`/`GameSession`, native state import/export in the worker/player, and storage in `saves.ts`. Reuse existing recovery/status/dialog components. Remove any replaced save/session logic rather than adding a parallel path.

## Delivery and verification

[One vertical delivery card on Project 1](https://github.com/orgs/TuringTestee/projects/1?pane=issue&itemId=261418406) owns #199: automatic capture, identity retention, explicit restore, new-guest synchronization, and integrated recovery proof. Depends on this merged plan and current checkpoint/rejoin repair; no partial enabling result closes the issue.

Use Chromium only and extend the existing essential persistence/gameplay checks. Prove the three human journeys through the public entry point, including actual previous progress, new session/name, expired old invitation, exact frame/hash agreement and real guest input. Exercise corrupt/missing ROM and state, incompatible identity, clear/write races, unavailable storage, cancellation and brief live reconnect. Inspect narrow/zoom dialog readability and fixed surrounding regions. Publish before/after runtime evidence and portable captures with six-agenda arguments; run bounded preflight and hosted checks, obtain independent review, verify merged main/live integration, then close #199. Do not commit proof logs, screenshots or a duplicate browser suite.
