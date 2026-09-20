Audience: Agent

# Included game: From Below

Keep **From Below (NES, version 1.0)** as the second included choice after Super Tilt Bro, as specified by the [catalog amendment](../design/included-games.md). The user supplied the ROM and confirms they have a license. This document identifies that exact game and its expected presentation; it does not claim browser or network qualification. Thwaite is not selected.

This handoff advances [D03 / issue #7](https://github.com/TuringTestee/retro-coop/issues/7) under [epic #2](https://github.com/TuringTestee/retro-coop/issues/2). The approved [design](../design/browser-nes-platform.md) and [UI stories](../design/browser-nes-ui.md) still govern the platform. D19 owns the included-game implementation after its dependencies are integrated.

## Artifact and provenance

| Field | Value |
|---|---|
| Title | From Below |
| Platform / supplied release | NES / 1.0, supplied filename dated 2020-09-16 |
| Exact SHA-256 | `1a3ac4faf4b35640505344059ae5d91dae07cd47e1fb4d9d2a33c76391f1c555` |
| File length | 40,976 bytes |
| Header | iNES; mapper 0 (NROM); 32 KiB PRG ROM; 8 KiB CHR ROM |
| Creator page | <https://mhughson.itch.io/from-below> |
| Source repository | <https://github.com/mhughson/mbh-firstnes> |
| Permission record | User confirms a license and explicitly authorizes this featured placeholder; license details use a placeholder under the latest user direction |

The file hash identifies the supplied binary, not a reproduced source build. Preserve the original local file outside Git; this documentation change publishes no ROM or download endpoint. A later packaging step must verify the supplied file against this hash. Do not replace it with the Vs. arcade release, a Game Boy game, or a newer build without updating the identity and qualification evidence.

Earlier inspected repository terms did not themselves grant redistribution. The user's later license confirmation is recorded separately; do not infer an SPDX identifier, public-domain status, modification rights, or asset rights from that repository statement. The user subsequently instructed “don’t put license.” The subsequent two-game catalog request supersedes that presentation choice with “License details pending.” Do not request a grant attachment or use it as a delivery blocker. Retain the confirmed content decision, exact artifact identity, credits and runtime qualification. This instruction does not change software dependency notices.

## Game description and credits

Use concise original copy in the featured card: **“Clear falling blocks and hold back the Kraken.”** The supplied creator description identifies these modes:

- **Kraken Battle:** clear lines while timed tentacle attacks push more blocks onto the board.
- **Classic:** falling-block play without the Kraken attacks.
- **Turn Based Kraken Battle:** tentacles advance when a piece is dropped, allowing deliberate play.

The supplied description also lists soft and hard drops, wall kicks, T-spins, and lock delay. These are creator-described features, not independently completed acceptance tests.

Credit Matt Hughson for the game, Tui for music and sound effects, Haller Zoltan for art, and Dejah Payne for box art and the manual. Credits do not authorize importing box art, promotional images, or manual files. Prefer the text card until specific presentation assets are included in the applicable grant.

## Multiplayer presentation

The supplied 2020 binary is treated as **single-player**. Its source-era input code polls controller 0; current master combines controllers, so current source behavior must not be projected onto this older binary. A scoped local JSNES inspection recorded P1 effects and no P2 framebuffer change for title, options, and gameplay probes in [the ticket evidence](https://github.com/TuringTestee/retro-coop/issues/7#issuecomment-5654074203). That is historical, scoped evidence. The [selected-core mode/controller probe](d03-featured-runtime.md) now records all three menus, P1 effects, scoped P2 video invariance, nonzero PCM and restored video replay for the exact binary; it is not exhaustive controller proof or final qualification.

Use the already planned optional **shared P1 handoff** for friends taking turns: one owner at a time, explicit transfer acceptance, and cleared held inputs at transfer. Both browsers still synchronize the same local game. Do not label this title “native two-player co-op,” invent a second board, or imply that voice chat changes its native gameplay. Native P1/P2 support remains platform scope for suitable locally loaded games.

## Included-game journey

The permanent featured entry must remain available with zero active rooms. Starting it creates a guest room with the approved defaults and loads the pinned included artifact in the browser. Joining an existing featured room uses that same artifact automatically, verifies its identity, and follows the existing connection and late-join flow. No local file picker is needed for included content.

The game retains its own menus and controls. “Start” on the website opens playable emulation; it must not be represented as proof that the game has already skipped its title/menu screens. D19 must measure the actual action count and label the resulting state accurately. Download or validation failure keeps the room recoverable with retry and an actionable error rather than a blank canvas. Game instructions and credits must be reachable without interrupting the shared timeline.

## Remaining acceptance and ownership

| Evidence still needed | Owner |
|---|---|
| Exact artifact identity, credits and scoped mode/controller qualification | D03: [recorded evidence](d03-featured-runtime.md), subject to PR acceptance |
| Exact artifact boot, audio, controls, save/restore and rewind in selected core and supported browsers | D02 initial feasibility; D20 final qualification |
| Included download identity, zero-room start, friend join and recovery UI | D19 |
| Shared P1 handoff and accurate single-player labels | D15 and D19 |
| Combined internet gameplay/voice and measured startup journey | D21 |

D03 runtime work has been accepted through its linked issue and PR evidence. D19 and the release qualification owners still require their assigned actual integration checks.
