Retro Coop should open on one clear list of public game rooms. The two included games start as empty rooms that players can claim, while a player with any supported local NES file can create another room that friends find and join from the same list.

Audience: Human

# Lobby experience amendment

**Status:** Proposed change to the approved browser NES platform and included-game plans. This document is the human product direction for the next UI refactor. It does not describe the current application or authorize implementation until its reviewed version is approved and merged.

## Product behavior

- The main service keeps one joinable 0/2 public room for each healthy included game. The first player who joins becomes Host/P1 in that exact room; the service publishes a new 0/2 room when the last one is claimed. The service lists and coordinates rooms but does not emulate a game or count as a player.
- The host decides when to start. Starting alone keeps the same room but makes Join unavailable for this essential delivery. A guest can join while the host waits; progress-preserving later join is deferred and must have its own approval/evidence before a playing room advertises Join.
- Super Tilt Bro and From Below use the same directory rows and room screens as other games. They have no Play cards, Show lobbies links, separate catalog browser, or preferential lobby controls. From Below identifies its single-controller sharing mode when a second player is relevant.
- **Host your NES file** is the one path for creating a player-owned room. Public is the default; the host may choose Unlisted before dropping or picking a local file. Valid selection automatically creates a waiting room with a generated neutral label that can be edited later. A public room appears in other browsers' directory; an unlisted room joins through its invitation. Local file bytes, filesystem path, and filename are never public room metadata. A guest supplies an exact matching file unless the verified included asset can be downloaded.
- Every public room is a separate row with an exact code, game/label, current host or No host, 0/2–2/2 occupancy, lifecycle status, and one valid next action. Full and temporarily unavailable rooms remain visible with a reason. Search and pagination operate on the same list.

## Design rules

1. Elaborate every player journey through action, feedback, outcome, and recovery. The [journey map](lobby-journeys-v2.md) and [scenario inventory](lobby-scenarios-v2.md) carry the detailed paths.
2. Give every visible feature a discoverable control, usable state, truthful feedback, and failure or exit path. The [feature check](lobby-wireframe-v3.md#feature-to-journey-ui-check) maps those surfaces.
3. Show information when the next decision needs it: host role before claiming 0/2, file requirements before joining a player-owned room, privacy beside Host/Join, and Start's effect in the host room. Later-join timeline choices stay out of the essential UI.
4. Give each journey one clear forward action per state. Remove duplicate calls to action and ambiguous routes; keyboard and assistive input activate that same action.
5. Keep labels, status language, room identity, and control placement consistent. Remove promotion, repeated instructions, and content that does not help a player decide, act, or understand current state.
6. When uncertain, inspect successful comparable applications and adapt a documented pattern. The [reference study](lobby-references-v2.md) records the DST and Warcraft III behavior used here and its limits.

## Reviewable screens and iterations

The [current page-by-page ASCII wireframe](lobby-wireframe-v3.md) shows directory, direct local-file hosting, host/guest room, play, and in-place recovery. Its [earlier iterations](lobby-wireframe-v1.md), [v2](lobby-wireframe-v2.md), and [page critiques](lobby-critique-v1.md) show why labels and states changed; the [earlier lobby proposal](lobby-browser-proposal.md) remains a previous iteration. The five most recent iterations are retained; superseded older drafts can be removed without deleting an approved baseline or source evidence.

The current wireframe has a six-rule design check. It is a proposal, not proof of rendered usability, accessibility, network behavior, or successful gameplay. Implementation acceptance must inspect the real product in independent browsers.

## Scope and compatibility with the existing plan

This amendment replaces the approved included-game launchers, automatic solo start, and assumption that every room begins with a browser host. It preserves browser-local emulation, exact-file matching, private local ROM bytes, public/unlisted access, two human player places, invitations, privacy policy, controller consent, recovery, and the operating budget. Progress-preserving later join is deferred, so a solo-started room cannot accept a guest in this delivery. It adds no server emulation, user-file distribution, accounts, passwords, spectators, or mobile-play promise.

Once approved and merged, this document governs the affected discovery and lobby behavior over conflicting passages in [the platform design](browser-nes-platform.md), [included-game design](included-games.md), and [earlier UI sketches](browser-nes-ui.md). Their unaffected technical and release requirements remain in force. The [delivery amendment](../implementation/lobby-refactor.md) states the work and current verification gates.
