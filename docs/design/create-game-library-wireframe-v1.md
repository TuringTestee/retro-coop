Players browse rooms on the home page and create rooms on a separate page. The Create Game page shows the last used game's real preview when available, then one unique list of games saved in this browser.

Audience: Human

# Create Game wireframe v1

## P1 Public rooms

```text
RETRO COOP                      Guest Lilac 2204   [Settings]
PUBLIC ROOMS                                      [Create game]
Live  Search room, game, host, or code [____________]

Super Tilt Bro · 0/2 Waiting for host             [Join as host]
Lilac Harbor · 1/2 Waiting for guest             [Join]
Host-shared NES · 2.1 MB download

If empty: No public rooms right now.              [Create game]
If offline: Connection lost.                      [Retry]
```

Transitions: Create game → P2. Join → existing room preparation P5. Empty state duplicates Create game in this first pass for critique. Supports C01.

## P2 Create Game, saved games present

```text
RETRO COOP / CREATE GAME                      [Back to rooms]

RECENT GAME
┌──────────────────────────────────────────────┐
│ [actual last rendered game frame, or         │
│  'No preview yet']                           │
│ Super Tilt Bro · 41 KB · Last used today      │
└──────────────────────────────────────────────┘

YOUR GAMES  (saved in this browser)
(•) Super Tilt Bro       Included       41 KB
( ) Lilac Harbor game   Downloaded     2.1 MB
( ) From Below          Included       41 KB
                              [Add NES file]

Room access    (•) Public   ( ) Unlisted
Guests download your selected game while the room is open.
                                      [Create room]
```

Transitions: choose one row → selected state on P2; Add → P3; Create → P4. Supports C02–C05, C07, C11–C12. “Included” rows are available even without a saved local byte copy; their verified bundled asset loads on selection.

## P3 Add a game and empty/error variants

```text
CREATE GAME                                   [Back to rooms]
RECENT GAME: No recent game yet.
YOUR GAMES: No saved games in this browser.

                              [Add NES file]  or drop one .nes here
Checking selected game…                       [Cancel]

Success:  Selected: My game · 2.1 MB
          Saved in this browser.  OR  Available in this tab only.
Error:    This file is not a supported NES game. [Choose another file]

Room access    (•) Public   ( ) Unlisted
                                      [Create room] (enabled after validation)
```

Transitions: validated file → P2 selected state; Cancel → prior Create state; Create → P4. Supports C04, C07–C08. The first pass's “Choose another file” duplicates Add and is examined in critique.

## P4 Publishing the room

```text
CREATE GAME · Lilac Harbor game · Public
Uploading game… 1.4 / 2.1 MB                 [Cancel upload]

Error: Upload stopped.                        [Retry upload]
                                              [Back to Create Game]
```

Transitions: complete verified upload → P5; Cancel/error → selected P2 or retry P4. Supports C06, C10.

## P5 Host waiting room

```text
LILAC HARBOR · PUBLIC · JA2V6CFL
Player 1 · Host: You       Player 2 · Guest: Open
[Copy invite]
Start now to play alone, or wait for a guest. [Start game]
[Leave room]
```

Transitions: guest ready updates P5 status; Start → play; Leave → P1. Existing guest preparation and shared-play states remain governed by the room-transfer design. Supports J2–J4 after creation.
