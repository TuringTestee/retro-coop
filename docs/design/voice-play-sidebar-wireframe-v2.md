Audience: Human

The current ASCII screens show the compact Players and Controls actions beside the game; detailed mappings appear in Settings when opened.

# Voice and play sidebar: wireframe v2 amended for minimal play

Players see their role, Players and Controls actions, and voice status beside the game. The canvas stays dominant and no card covers it. The later [minimal room journey](minimal-room-journey.md) replaces this wireframe's former persistent binding list.

Sources: [references](voice-play-sidebar-references.md), [direction](voice-play-sidebar-direction.md), [journeys](voice-play-sidebar-journeys.md), [scenarios](voice-play-sidebar-scenarios.md), [v1 critique](voice-play-sidebar-critique-v1.md).

## P1 — Shared game, connected, microphone off

```text
RETRO COOP                    Public rooms  Settings
+--------------------------------+ +-------------------------+
|                                | | Player 2                |
|                                | | [Players]  Controls     |
|         NES GAME               | +-------------------------+
|                                | | VOICE · Off             |
|                                | | [Enable voice]          |
|                                | +-------------------------+
|                                | | Lilac Lounge            |
|                                | | Peer connected          |
|                                | | Leave room              |
|                                | | Room chat ▸             |
|                                | | Session settings ▸      |
|                                | +-------------------------+
+--------------------------------+
Pause  Mute game  Saves  Game help  Fullscreen
```

Enable voice → P2. Controls → Settings mapping list; Back returns focus to Controls. Solo play omits Voice and room details. If no peer connection, voice says `Connecting` with disabled Enable; session recovery appears when available. The NES player port reflects the accepted assignment. Separate mode may put the guest on P1 or host on P2; the role must follow the assignment, not room role.

## P2 — Request, open mic, muted, push mode

```text
+--------------------------+     +--------------------------+
| VOICE · Requesting mic   |  →  | VOICE · Mic on           |
| [Cancel request]         |     | [Mute]                   |
+--------------------------+     | Voice settings           |
                                 +--------------------------+

+--------------------------+     +--------------------------+
| VOICE · Muted            |     | VOICE · Hold to talk     |
| [Unmute]                 |     | Hold  V  or [Talk]      |
| Voice settings           |     | Voice settings           |
+--------------------------+     +--------------------------+
```

Mic permission succeeds → applicable mode. Mute/Unmute changes state immediately. The Talk button transmits only while held; the mapped key shown is from current controls. Focus changes preserve explicit microphone mute and release held push-to-talk under [Background voice](background-voice.md). Reconnect closes the old track and requires new opt-in. Voice settings holds device, mode, remote volume/mute and Disable microphone; it is the only route to those details.

## P2a — Shared P1 controlled by the partner

```text
+-----------------------------------+
| Observer                          |
| [Players]                         |
+-----------------------------------+
```

This is the accepted assignment, not a second handoff action. Players opens the existing room slot controls. Once both players accept a handoff and play resumes, the new owner sees the assigned P1 role; the other sees Observer. A declined proposal leaves the prior role intact. In Separate P1/P2, the role shows the assigned local port regardless of Host/Guest identity.

## P3 — Voice failure and hearing partner

```text
+-----------------------------------+
| VOICE · Mic unavailable           |
| Microphone permission denied.     |
| [Try again]  Voice settings       |
+-----------------------------------+

+-----------------------------------+
| VOICE · Mic on                    |
| Partner audio could not play.     |
| [Enable voice sound]              |
| Voice settings                    |
+-----------------------------------+
```

Use the actual failure reason: permission, missing device, attachment or connection. Browser site-permission advice appears only for permission denial. Try again re-enters Requesting. Remote mute is shown in Voice settings with one `Unmute remote voice` action. No voice failure pauses the NES game or removes text chat.

## P4 — Narrow play

```text
RETRO COOP                        Settings
+----------------------------------------+
|               NES GAME                 |
+----------------------------------------+
Pause  Mute game  Saves  Game help
+----------------------------------------+
| Player 2    [Players]    Controls      |
+----------------------------------------+
| VOICE · Off        [Enable voice]      |
+----------------------------------------+
| Lilac Lounge · Peer connected          |
| Leave room                             |
| Room chat ▸   Session settings ▸       |
+----------------------------------------+
```

Cards follow the game in reading and keyboard order. Controls opens Settings where long or unbound mappings have readable labels. An absent or disconnected optional device automatically falls back to keyboard/touch; Settings retains its preferred identity and mappings. [The controls contract](../implementation/d07-controls.md#input-and-recovery) governs usable hints and released return holds. No horizontal page overflow or overlay is permitted.

## Final design check

All four pages have a next action and a recovery state for V1–V3, C1–C4 and E1. Each shown action maps to a scenario, with Voice settings restricted to detail controls and Settings/Controls to remapping. Mic permission is requested only at P1; failure information appears at P3. The same role, state and action names are used across widths. Actual visual fit, screen reader output, microphone behavior and update timing require browser proof.

Keep the fixed compact play row and inspect desktop/narrow screenshots and a two-tab voice session. Game help points to Controls or Settings for current mappings.
