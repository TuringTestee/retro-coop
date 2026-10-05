Retro Coop opens on a lobby list, creates a public lobby immediately, and keeps players, game, game menu, chat, and actions in one fixed shell through play.

Audience: Agent

# Unified lobbies: implementation plan

Governing design: [direction](../design/unified-lobbies-direction.md), [journeys](../design/unified-lobbies-journeys.md), [scenarios](../design/unified-lobbies-scenarios.md), and [current wireframe](../design/unified-lobbies-wireframe-v6.md).

## Authority and state

- A lobby is created with a random public name and no game. The host may rename it in the fixed header and change access in the right menu. The directory shows current occupancy, open places, access, game name, and an unavailable reason. Direct/relay routing stays automatic.
- The host alone selects or changes a NES game before Start. Exact file and revision checks reject stale readiness. Selection failure retains the lobby; a member acquires the exact selected game, including when joining live play. The client may load the matching catalog game after play has begun but may not replace the running game.
- Five fixed physical slots determine P1, P2 when supported, and spectators. Host moves swap actual occupants. Removing a person compacts surviving occupants through open places. During play, a changed controller owner triggers a freeze at a completed frame, checkpoint transfer, and new barrier before resuming; the departed owner is never asked to acknowledge. Ordinary spectator joins do not pause active owners.
- Start requires the selected game, connected and loaded occupied controller owners, current Ready offers, and host authority. Empty controller slots and spectators do not block a solo host. The host waits or kicks anyone required but unprepared. A live join may enter an open place; a late controller chooses Prepare to play and synchronizes before taking input.
- Exit confirmation is centered and blocks the shell. Successful exit stops room membership, emulator work, input, audio, and voice before returning to the directory. Failed exit leaves the current context available.

## UI boundaries

`AppShell` fixes header, status, stage and enlarged footer tracks. `LobbyDirectory` owns the first Host row and clickable lobby rows. `SessionStage` fixes players, toolbar, center game, right settings column and chat. The right `Settings` component remains open and switches Game, Lobby, Controls, Sound, Voice and Profile in place. The game starts unmuted. The header groups editable lobby and personal names in fixed containers; editing opens a centered dialog without changing header size. Copy invite follows the lobby name in the header. The game toolbar shows the ROM name and, before play, Change game; neither overlays the NES frame. If clipboard access fails, Copy invite offers a selectable link in a centered dialog without replacing settings. The full-window game view toggles from the game frame and returns by click or Escape. Only chat history scrolls. At narrow widths, slots occupy a fixed top row, then game/settings, then chat; the toolbar wraps within its reserved row.

The theme bootstrap reads only an explicit manual preference; otherwise it selects by browser-local hour on each visit. The header control persists manual changes. A connected peer starts Voice in push-to-talk mode once per lobby; the user may disable it, and connection failures never gate gameplay. The game guide derives keyboard labels from the active bindings. P pauses or resumes the emulator (separate from NES Start); M mutes game audio, Save (Q) captures completed native progress into quick slot 1 with storage generation and compare-and-swap guards. Host Load (E) confirms that copy and uses the coordinated consent/checkpoint barrier; local loading retains its direct guarded import. The Game section exposes these actions once the matching ROM is loaded, including before Start for later use. Local data owns portable save import/export and deletion; shared rewind remains deferred.

The worker's `fresh` state describes an unplayed timeline, not immutable memory. Restoring battery data preserves `fresh`, while running a frame or importing a full save ends it. Preview renders on a temporary timeline and restores the exact starting hash. If preview fails, `LocalPlayer` proceeds only when a second hash proves that frame, freshness and canonical state are unchanged.

## Verification

Run the README pre-flight and the [platform verification strategy](browser-nes-platform.md#verification-strategy). The public-entry browser journey must cover directory host/join, password recovery, name dialogs, game selection and cancellation, Ready/Start with an unready controller and an unready spectator, live join, playable game, centered exit, and return. Check fixed regions and readable text at desktop, narrow phone, and effective 320 CSS pixels under zoom. A delayed saved-game read must not load after cancellation, another choice, or leaving the lobby. Keep actual commands, captures, and current-head results on the PR rather than in this plan.
