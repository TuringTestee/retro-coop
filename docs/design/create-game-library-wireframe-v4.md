Public rooms, Create Game, waiting, play and tools use one stable page frame. The host can open or close an empty Guest place. This is the current proposal after [v3 critique](create-game-library-critique-v3.md); [v1](create-game-library-wireframe-v1.md), [v2](create-game-library-wireframe-v2.md) and [v3](create-game-library-wireframe-v3.md) remain as design history.

Audience: Human

# Create Game wireframe v4 — current

Based on [references](create-game-library-references.md), [direction](create-game-library-direction.md), [journeys](create-game-library-journeys.md), and [scenarios](create-game-library-scenarios.md).

## P1 Public rooms

```text
RETRO COOP                                    Guest Lilac 2204 [Settings]
PUBLIC ROOMS                                              [Create game]
Search room or game [___________________]  Connection [Standard v]

Game / room                Host          Guest place        Action
Super Tilt Bro             —             0/2 Waiting host   [Join as host]
Lilac Harbor               Guest Amber   Open               [Join]
My game                    Guest Blue    Closed             —
Another game               Guest Gold    Occupied           —

If none: No public rooms.  If search misses: No matching rooms.
If offline: Rooms unavailable [Retry]
```

One Create entry; one Join per eligible row. Clicking a row does not create another route. Closed/full rows remain inspectable by their status but cannot Join. Connection applies to the next Join only. P1 → P2 Create, P5/P6 Join, P8 Settings. C01,C13/J1,J2,J3,J9.

## P2 Create Game — wide

```text
RETRO COOP / CREATE GAME                               [Back to rooms]
YOUR GAMES (list scrolls here)   │ SELECTED GAME
> Lilac Harbor game              │ [last real rendered frame]
  Super Tilt Bro · Included      │  or No preview yet
  From Below · Included          │ Lilac Harbor game · 2.1 MB
  Other downloaded game          │ Saved in this browser
  [Add NES file]                 │
                                 │ Room access   (●) Public ( ) Unlisted
                                 │ Connection    [Standard v]
                                 │ Checking game… then [Create room]
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
  Checking game…  OR  Saved copy unavailable.
  Available in this tab only (after storage failure)
After selection verifies:
  Room access (●) Public ( ) Unlisted  Connection [Standard v]
  [Create room]
```

The list, preview and action stack in document flow; errors replace the selected-game status. One Add action is retained even in error. C04,C07,C08,C11,C12/J2–J4.

## P4 Publishing

```text
CREATE GAME / Lilac Harbor game                     [Back to Create Game]
Uploading game 1.4 / 2.1 MB
While active: [Cancel upload]
If failed: Connection lost. [Retry upload]
```

Success → P5. Cancel/Back preserve tab selection; no ghost room. C06,C10/J2,J3.

## P5 Host waiting — open / occupied / closed

```text
LILAC HARBOR · PUBLIC · JA2V6CFL                     [Leave room]
Player 1  You · Host
Player 2  Guest place: Open                   [Close place]
[Copy invite]                               [Start game]

When occupied: Player 2  Guest Amber · Preparing  [Remove guest]
               While preparing: Start now plays alone and releases the guest.
               When prepared: Start plays together.
Remove chosen: Remove Guest Amber? They cannot reconnect.
               [Confirm removal] [Cancel]
When closed:   Player 2  Guest place: Closed        [Open place]
Leave chosen:  Close this room for everyone? [Confirm leave] [Cancel]
```

The one Start game action stays at the bottom of the slot area in every waiting state. Close exists only while empty; occupied removal needs inline confirmation. Copy invite is hidden while Closed. Opening restores admission; Start → P7 and hides slot controls. Leave confirmation replaces the Start action area. C13–C15,C17/J7,J8.

## P6 Guest room / invitation

```text
LILAC HARBOR · PUBLIC · JA2V6CFL                    [Leave room]
Player 1  Guest Lilac · Host
Player 2  You · Guest
Downloading game 1.4 / 2.1 MB → Loading → [Prepare to play]
If failed: Download interrupted. [Retry download]

Open invitation before joining: Guest place Open
Connection [Standard v]                              [Join room]

Closed invite: Guest place closed.                 [Back to rooms]
Full/playing invite: This room cannot be joined.  [Back to rooms]
```

Join and download require no guest file picker. A closed invite has no Join. Failure has Retry in the acquisition area. C13–C15/J1,J4,J9.

## P7 Playing

```text
RETRO COOP / PLAYING
┌──────────────────── GAME CANVAS ─────────────────────┐ │ ROOM DETAILS
│                                                     │ │ Host: You
│                                                     │ │ Guest: Amber
└─────────────────────────────────────────────────────┘ │ [Leave room]
Controls  [Saves] [Game help]
Local play only: [Rewind]
Status: Connected directly.  OR  Reconnecting… [Retry]
```

Room details occupy a stable region beside canvas on wide screens and below it on narrow screens. Saves/Rewind/Help → their own pages; Leave uses inline confirmation in the room region. C16,C17/J10.

## P8 Settings

```text
RETRO COOP / SETTINGS                              [Back to previous page]
Input device [Keyboard v]  Edit mappings [Keyboard v]
Move: Arrow keys                          [Change Move]
Display filter [Nearest neighbor v]  Game volume [80% slider]
[Local data]
```

Other existing mapping rows, voice and connection settings continue in this page below the first visible region when applicable. Settings → P9. Back restores invoking page and focus. C16/J10.

## P9 Local data

```text
RETRO COOP / LOCAL DATA                         [Back to Settings]
Saved games in this browser: 2
My game · 2.1 MB                                      [Delete]
Other game · 1.4 MB                                   [Delete]
After Delete: Delete My game from this browser? [Confirm] [Cancel]
If failed: Could not delete My game. [Retry]
```

Delete confirmation replaces the relevant row action, not the entire page. Existing save, battery and preference records, export actions, and Delete all remain farther down this page when present; each has its current usable-state rule and an inline confirmation where destructive. C09,C16,C17/J5,J10.

## P10 Saves / Rewind / Game help (separate pages)

```text
RETRO COOP / SAVES                        [Back to playing]
Slot 1 · Saved today               [Export] [Delete]
Local play only:                   [Load]
Empty slot                         [Save current point]
After local Load: Replace current game progress? [Confirm load] [Cancel]

RETRO COOP / REWIND                       [Back to local play]
Available rewind points: 3
Point 2 · 10 seconds ago            [Restore]
After Restore: Replace current game progress? [Confirm restore] [Cancel]

RETRO COOP / GAME HELP                    [Back to playing]
Arrows move · X is A · Z is B · Enter is Start · Shift is Select
Game-specific instructions/credits if available
```

These are three distinct page states. The action or information is shown only when that page opens; confirmations replace their relevant action row. Load a saved point and Rewind exist only in local play; the current player rejects shared save loading. Existing Save import/export, current-save export and backup retry remain in Saves when applicable, below its first visible region. C16,C17/J10.

## Final rule check and limits

J1–J10 map to P1–P10, with errors and exit paths in their action regions. Every visible control has an entry and result in [scenarios](create-game-library-scenarios.md). Selection updates a stable preview; a single Create, Join, Start or Back action advances each state. The page layout borrows Warcraft III's list/preview and open-slot pattern, while keeping Retro Coop's two-player rule. The absence of overlays and correct slot admission are still implementation claims to verify in a wide/narrow two-browser test. A later improvement may allow a local rename if saved game labels prove hard to recognize; no rename control belongs in this release.
