Audience: Human

The revised ASCII screens show a compact control and voice rail beside the game, including recovery and controller ownership.

# Voice and play sidebar: current wireframe v2

Players see current controls and voice status beside the game. The canvas stays dominant and no card covers it. This is a proposed design; rendered fit and operation still need implementation proof.

Sources: [references](voice-play-sidebar-references.md), [direction](voice-play-sidebar-direction.md), [journeys](voice-play-sidebar-journeys.md), [scenarios](voice-play-sidebar-scenarios.md), [v1 critique](voice-play-sidebar-critique-v1.md).

## P1 — Shared game, connected, microphone off

```text
RETRO COOP                    Public rooms  Settings
+--------------------------------+ +-------------------------+
|                                | | YOUR CONTROLS · Player 2|
|                                | | Keyboard                |
|                                | | Move  ↑ ← ↓ →           |
|         NES GAME               | | A  X       B  Z         |
|                                | | Start  Enter            |
|                                | | Select Shift            |
|                                | | Edit controls           |
|                                | +-------------------------+
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

Enable voice → P2. Edit controls → Settings/Controls; return updates this readout. Solo play omits Voice and room details. If no peer connection, voice says `Connecting` with disabled Enable; session recovery appears when available. The NES player port and source reflect the accepted assignment and selected device. Separate mode may put the guest on P1 or host on P2; the header must follow the assignment, not room role.

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

Mic permission succeeds → applicable mode. Mute/Unmute changes state immediately. The Talk button transmits only while held; the mapped key shown is from current controls. Blur mutes transmission while retaining the captured track; returning needs deliberate unmute. Reconnect closes the old track and requires new opt-in. Voice settings holds device, mode, remote volume/mute and Disable microphone; it is the only route to those details.

## P2a — Shared P1 controlled by the partner

```text
+-----------------------------------+
| YOUR CONTROLS · Shared P1          |
| Your input is idle.               |
| Alex controls P1 now.             |
| Session controllers ▸             |
+-----------------------------------+
```

This is a readout of the accepted assignment, not a second handoff action. `Session controllers` opens the existing room control. Once both players accept a handoff and play resumes, the new owner sees P1 bindings; the other sees the idle state. A declined proposal leaves the prior card intact. In Separate P1/P2, the card shows the assigned local port regardless of Host/Guest role.

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

## P4 — Narrow play and long mappings

```text
RETRO COOP                        Settings
+----------------------------------------+
|               NES GAME                 |
+----------------------------------------+
Pause  Mute game  Saves  Game help
+----------------------------------------+
| YOUR CONTROLS · Player 2 · Gamepad     |
| Move    Axis 1 − / Axis 1 + / …        |
| A       Button 1                       |
| B       Button 2                       |
| Start   Button 10                      |
| Select  Unbound                        |
| Edit controls                          |
+----------------------------------------+
| VOICE · Off        [Enable voice]      |
+----------------------------------------+
| Lilac Lounge · Peer connected          |
| Leave room                             |
| Room chat ▸   Session settings ▸       |
+----------------------------------------+
```

Cards follow the game in reading and keyboard order. Binding text wraps inside the card; an unbound action still has a label and one Edit controls route. A disconnected device triggers the existing Use keyboard action, after which the readout switches to keyboard. No horizontal page overflow or overlay is permitted.

## Final design check

All four pages have a next action and a recovery state for V1–V3, C1–C4 and E1. Each shown action maps to a scenario, with Voice settings restricted to detail controls and Settings/Controls to remapping. Mic permission is requested only at P1; failure information appears at P3. The same role, state and action names are used across widths. The mapped readout adapts Steam Input's action guidance; the voice card adapts Discord's status/recovery pattern. Actual visual fit, screen reader output, microphone behavior and update timing remain unproven until browser testing.

Recommendation: implement the side cards with small responsive rows and live mapping data first, then inspect desktop/narrow screenshots and a two-tab voice session. Remove redundant fixed-key copy from Game help while doing so.