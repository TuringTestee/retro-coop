Public rooms, Create Game, waiting, play and tools use one stable page frame. The host can open or close an empty Guest place. This draft is checked page by page in v3 critique.

Audience: Human

# Create Game wireframe v3 — draft

Based on [references](create-game-library-references.md), [direction](create-game-library-direction.md), [journeys](create-game-library-journeys.md), and [scenarios](create-game-library-scenarios.md).

## P1 Public rooms

```text
RETRO COOP                                    Guest Lilac 2204 [Settings]
PUBLIC ROOMS                                              [Create game]
Search room or game [___________________]  Connection [Standard v]

Game / room                Host          Guest place        Action
Super Tilt Bro             —             Open               [Join as host]
Lilac Harbor               Guest Amber   Open               [Join]
My game                    Guest Blue    Closed             —
Another game               Guest Gold    Occupied           —

If none: No public rooms.                 If offline: Rooms unavailable [Retry]
```

One Create entry; one Join per eligible row. Clicking a row does not create another route. Closed/full rows remain inspectable by their status but cannot Join. Connection applies to the next Join only. P1 → P2 Create, P5/P6 Join, P8 Settings. C01,C13/J1,J2,J3,J9.

## P2 Create Game — wide

```text
RETRO COOP / CREATE GAME                               [Back to rooms]
YOUR GAMES (list scrolls here)   │ SELECTED GAME
> Lilac Harbor game · Recent     │ [last real rendered frame]
  Super Tilt Bro · Included      │  or No preview yet
  From Below · Included          │ Lilac Harbor game · 2.1 MB
  Other downloaded game          │ Saved in this browser
  [Add NES file]                 │
                                 │ Room access   (●) Public ( ) Unlisted
                                 │ Connection    [Standard v]
                                 │ [Create room]
```

List selection updates preview in place; it verifies and loads bytes before Create enables. The preview is display only. A new file uses Add, then appears selected once by hash. Back → P1; Create → P4. C02–C05,C07,C11,C12/J2–J4,J6.

## P3 Create Game — narrow/error/empty states

```text
RETRO COOP / CREATE GAME                               [Back to rooms]
YOUR GAMES  [select game rows; page scrolls]
  No saved games (bundled choices still appear if available)
  [Add NES file]
SELECTED GAME
  No game selected.  OR  [real preview / No preview yet]
  Checking game…  OR  Saved copy unavailable. [Add NES file]
  Available in this tab only (after storage failure)
Room access (●) Public ( ) Unlisted  Connection [Standard v]
[Create room] (disabled until selected and verified)
```

The list, preview and action stack in document flow; errors replace the selected-game status. One Add action is retained even in error. C04,C07,C08,C11,C12/J2–J4.

## P4 Publishing

```text
CREATE GAME / Lilac Harbor game                     [Cancel upload]
Uploading game 1.4 / 2.1 MB
If failed: Connection lost. [Retry upload] [Back to Create Game]
```

Success → P5. Cancel/Back preserve tab selection; no ghost room. C06,C10/J2,J3.

## P5 Host waiting — open / occupied / closed

```text
LILAC HARBOR · PUBLIC · JA2V6CFL                     [Leave room]
Player 1  You · Host
Player 2  Guest place: Open                   [Close place]
                                         [Copy invite]
                                          [Start game]

When occupied: Player 2  Guest Amber · Preparing  [Remove guest]
               [Start game]  (plays alone if guest unprepared)
Remove chosen: Remove Guest Amber? They cannot reconnect.
               [Confirm removal] [Cancel]
When closed:   Player 2  Guest place: Closed        [Open place]
               [Start game]  (plays alone)
```

Close exists only while empty; occupied removal needs inline confirmation. Opening restores admission; Start → P7 and hides slot controls. Leave confirmation appears in this page's action area. C13–C15,C17/J7,J8.

## P6 Guest room / invitation

```text
LILAC HARBOR · PUBLIC · JA2V6CFL                 [Back to rooms]
Player 1  Guest Lilac · Host
Player 2  You · Guest
Downloading game 1.4 / 2.1 MB → Loading → [Prepare to play]

Closed invite: Guest place closed.                 [Back to rooms]
Full/playing invite: This room cannot be joined.  [Back to rooms]
```

Join and download require no guest file picker. A closed invite has no Join. Failure has Retry in the acquisition area. C13–C15/J1,J4,J9.

## P7 Playing

```text
RETRO COOP / SHARED PLAY                         [Room details]
┌──────────────────── GAME CANVAS ─────────────────────┐ │ ROOM DETAILS
│                                                     │ │ Host: You
│                                                     │ │ Guest: Amber
└─────────────────────────────────────────────────────┘ │ [Leave room]
Controls  [Saves] [Rewind] [Game help]
Status: Connected directly.  OR  Reconnecting… [Retry]
```

Room details occupy a fixed region beside canvas on wide screens and below it on narrow screens. If collapsed, the Room details button navigates to its page, never opens a drawer over the canvas. Saves/Rewind/Help → P8 tool page; Leave uses inline confirmation. C16,C17/J10.

## P8 Settings and tools

```text
RETRO COOP / SETTINGS · LOCAL DATA / SAVES / REWIND / GAME HELP
                                                          [Back]
Page task and needed state, e.g. Downloaded games: 2
My game · 2.1 MB [Delete]
After Delete: Delete My game from this browser? [Confirm] [Cancel]
If failed: Could not delete. [Retry]
```

Each tool is a full content page, never a modal. Settings links to Local data; play links to Saves, Rewind, Help. Back returns to the invoking page and focus. A destructive action replaces that row/action area with Confirm and Cancel. C09,C16,C17/J5,J10.
