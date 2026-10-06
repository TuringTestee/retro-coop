Historical baseline: one lobby list and one persistent lobby. Its directory and slot patterns remain reference material. The old Settings routes, phone composition and preparation placement are superseded by [mobile direction](mobile-controller-direction.md) and [gameplay controls](gameplay-controls.md); this sketch is not the current screen set for those areas.

# Unified lobbies: wireframe v6

## Directory

```text
┌ RETRO COOP        / Lobbies       Your name: [Guest Jade ✎] [☾ Dark] ┐
│ Status or recovery, only when needed                                  │
│ 2 lobbies                              [Search lobbies____________]   │
│ [ + Host a new game                                          → ]       │
│ [ Maple Station        Super Tilt Bro · Public              1/5 ]       │
│ [ Pixel Harbor         Reconnecting · Password             2/5 ] off   │
└────────────────────────────────────────────────────────────────────────┘
```

Host opens a generated public lobby immediately. Clicking an available row joins; a protected row asks for its password in the directory. A disabled row gives its reason. D1–D2, H1.

## Lobby before selection or Start

```text
┌ RETRO COOP   [Lobby name: Maple Station ✎] [Copy invite] [Your name: Guest ✎] [☾] ┐
│ Load a NES game while players join.                              │
├ PLAYERS────────────┬ NES GAME─────────────────────────────┬ SETTINGS ┤
│ P1 · You         ▾ │ ┌───────────────────────────────────┐  │ [Lobby]   │
│ Waiting for game   │ │       [ + Load NES game ]         │  │ Controls  │
│ Open Slot 2      ▾ │ │                                   │  │ Sound     │
│ Open Slot 3      ▾ │ └───────────────────────────────────┘  │ Voice     │
│ Open Slot 4      ▾ │                                         │ Profile   │
│ Open Slot 5      ▾ │                                         │ Access:   │
│                     │                                         │ Public    │
├ CHAT───────────────────────────────────────────────────────────────┤
│ messages (the only scrolling region)                                 │
│ [Message everyone_______________________________________] [Send]     │
├ [Back to Main Page]                                   [Ready] [Start] ┤
```

After selection, the game frame shows the NES preview at full size. The ROM name and **Change game** occupy the fixed toolbar above, not the preview. **Copy invite** follows the lobby name in the header. Clicking either editable name opens a centered dialog with Cancel and Save; the header never changes size. Ready appears after preparation and Start after all occupied controller owners are Ready. One host may start alone. H1, G1, P1–P2, C1.

## Host slot dropdown

```text
[ P1 · Guest Jack       Not ready                    ▴ ]
┌──────────────────────────────────────────────────┐
│ Move as Player 2                                 │
│ Move as Spectator 3                              │
│ Move as Spectator 4                              │
│ Move as Spectator 5                              │
│ Kick Guest Jack                                  │
└──────────────────────────────────────────────────┘
[ Open Slot 3 ▾ ] → [Close slot]
```

The row contains no redundant 03 label. Its name and status wrap within the same fixed slot height. Moves change the actual occupied row; open slot and closed slot menus contain only their legal action. S1–S3.

## Playing and game fill

```text
┌ RETRO COOP   [Lobby name: Maple Station ✎] [Copy invite] [Your name: Guest ✎] [☾] ┐
│ Game state / countdown when needed                                │
├ PLAYERS────────────┬ From Below─────────────────────────────┬ SETTINGS ┤
│ P1 · You         ▾ │ ┌───────────────────────────────────┐ │ [Game]     │
│ Playing            │ │    running NES game · click       │ │ Lobby      │
│ P2 · Jack        ▾ │ │    to fill window                 │ │ Controls   │
│ Playing            │ │                                   │ │ Sound      │
│ Spectators         │ └───────────────────────────────────┘ │ Voice      │
│                    │                                       │ Profile    │
│                    │                                       │  ↑   SEL   │
│                    │                                       │ ←✚→ START B A│
│                    │                                       │  ↓         │
│                    │                                       │ Controller guide│
│                    │                                       │ Current bindings│
│                    │                                       │ Next action key │
├ CHAT────────────────────────────────────────────────────────────────┤
│ messages                                           [entry] [Send]     │
├ [Back to Main Page]                                          [Pause]  ┤
```

The game stays in the center column; settings change only the right column. Clicking the game fills the window and clicking again or Escape restores this layout. A late P2 first sees Prepare to play, then synchronizes. The [current direction](unified-lobbies-direction.md) owns the actual key bindings. M1, P3, E1.

At 320 CSS pixels, five player places use two fixed columns above the center-game/right-menu row. The toolbar wraps within its reserved row. Chat and footer remain fixed; only chat history scrolls. A confirmation covers the center over a dimmed shell rather than using footer space.

The light and dark themes use the same panel geometry. The top-right control shows the opposite theme; local time chooses the first theme until a person switches manually. At narrow widths the header uses two fixed lines for lobby and person names. The controller guide gives each keyboard mapping its own readable line. Voice starts in push-to-talk mode when another person connects, and microphone recovery stays inside Voice settings.

See [direction](unified-lobbies-direction.md), [journeys](unified-lobbies-journeys.md), [scenarios](unified-lobbies-scenarios.md), and [critique](unified-lobbies-critique-v6.md).
