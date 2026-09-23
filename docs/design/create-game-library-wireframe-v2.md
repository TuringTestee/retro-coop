Players find a room on Public rooms or move to Create Game to host. Create Game reuses a verified browser game, accepts one new NES file, and shows an actual recent frame when available. This is the current design proposal.

Audience: Human

# Create Game wireframe v2 — current

Uses [references](create-game-library-references.md), [direction](create-game-library-direction.md), [journeys](create-game-library-journeys.md), [scenarios](create-game-library-scenarios.md), and [v1 critique](create-game-library-critique-v1.md). [v1](create-game-library-wireframe-v1.md) remains for comparison.

## P1 Public rooms

```text
RETRO COOP                         Guest Lilac 2204  [Settings]
PUBLIC ROOMS                                     [Create game]
Live  Search room, game, host, or code [____________]

Super Tilt Bro · 0/2 Waiting for host            [Join as host]
Lilac Harbor · 1/2 Waiting for guest             [Join]
Host-shared NES · 2.1 MB download

No public rooms right now.  OR  Connection lost. [Retry]
```

Create game → P2. Join → existing room preparation. One Create entry remains even when the list is empty. C01/J1–J3.

## P2 Create Game: recent game and library

```text
RETRO COOP / CREATE GAME                     [Back to rooms]

RECENT GAME
┌───────────────────────────────────────────────┐
│ [real saved frame]  OR  No preview yet         │
│ Lilac Harbor game · Last used today           │
└───────────────────────────────────────────────┘

YOUR GAMES  (in this browser)
(•) Lilac Harbor game     Downloaded     2.1 MB
( ) Super Tilt Bro        Included       41 KB
( ) From Below            Included       41 KB
                                               [Add NES file]

Selected game: Lilac Harbor game · 2.1 MB
Room access: (•) Public   ( ) Unlisted
Guests download this game while the room is open.
                                               [Create room]
```

Selecting a row verifies its bytes and updates Selected game; Create room → P4. Add opens the system picker; one-file drop works on this page. Back returns to P1. The preview displays recent history but is not another selection control. C02–C05, C11–C12/J2–J4.

## P3 Create Game: empty, validating, unavailable, tab-only

```text
RECENT GAME: No recent game yet.
YOUR GAMES: Bundled games unavailable; no saved games here.
                                               [Add NES file]
Checking selected game…                        [Cancel]

After success: Selected game: My game · 2.1 MB
               Saved in this browser.
               OR Available in this tab only; add it again after reload.
If invalid:    This file is not a supported NES game. [Add NES file]
If saved copy missing/corrupt:
               This saved game is unavailable.        [Add NES file]

Room access: (•) Public   ( ) Unlisted
                                               [Create room] disabled until verified
```

Validation never replaces a previous good selection until success. One Add control remains after an error. A missing saved entry is deselected, and no room is created. C04, C07–C08/J2–J4.

## P4 Publishing

```text
CREATE GAME · My game · Public
Uploading game… 1.4 / 2.1 MB                 [Cancel upload]

If stopped: Upload failed: connection lost.   [Retry upload]
                                               [Back to Create Game]
After Cancel: Upload cancelled. No room was published.
```

Successful verified upload → P5. Cancel aborts upload and returns to P2 with the selected bytes in this tab. Error permits Retry or Back; neither leaves a public ghost row. C06/C10/J2–J3.

## P5 Host waiting room

```text
LILAC HARBOR · PUBLIC · JA2V6CFL
Player 1 · Host: You       Player 2 · Guest: Open
[Copy invite]
Start now to play alone, or wait for a guest. [Start game]
[Leave room]

When guest joins: Player 2 · Guest: Guest Amber 2078
Guest downloading… → loading… → prepared.
When prepared: Start together when you are ready. [Start game]
```

This reuses the approved waiting-room and guest acquisition states. Start → play; Leave → P1. C06/J2–J4.

## Final rule check

| Rule | Screen/journey evidence |
| --- | --- |
| Complete journeys | J1–J6 trace P1–P5 and Settings → Local data; P3/P4 show failure and exit routes. |
| Feature support | C01–C12 map every new control and visible state to entry, feedback and recovery. |
| Information just in time | Download size stays by Join; upload effect/access appear by Create room; tab-only notice appears after a failed local save. |
| One clear forward path | One Create entry on P1, one Add action on P2/P3, one Create room action after verified selection; preview is display only. |
| Concise and consistent | No inline host bar, promotional copy, duplicate picker, or invented artwork. Access and room labels match P1/P5. |
| Borrow before inventing | Separate browse/host from DST, game choice before lobby from Warcraft III, visibility and host Start from AoE2. Preview rendering is explicitly our adaptation. |

**Implementation limits:** These sketches do not prove that IndexedDB will persist, a frame will be nonblank, or keyboard focus will work. An integrated browser test must verify those outcomes. Recommended improvement after this release: let players rename a game's local library label without changing the public room name, if testing shows the current generated labels make saved games hard to recognize. That is not required for this flow.
