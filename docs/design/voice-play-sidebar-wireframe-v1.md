Audience: Human

This first ASCII pass places controls and voice beside the game for critique.

# Voice and play sidebar: wireframe v1

This first screen set tests where play controls and voice belong. It is a proposal, not a rendered implementation.

## P1 — Shared play, voice off (S1, S6)

```text
RETRO COOP                         Public rooms  Settings
+--------------------------------+ +---------------------+
|                                | | CONTROLS · Keyboard |
|          NES GAME              | | Move       ↑ ← ↓ →  |
|                                | | A  X       B  Z     |
|                                | | Start Enter  Select ⇧|
|                                | | Edit controls       |
|                                | +---------------------+
|                                | | VOICE · Off         |
|                                | | [Enable voice]      |
|                                | +---------------------+
|                                | | Lilac Lounge · P1   |
|                                | | Peer connected      |
|                                | | Leave room          |
|                                | | Room chat           |
|                                | +---------------------+
+--------------------------------+
 Pause  Mute game  Saves  Game help  Fullscreen
```

Enable voice → P2. Edit controls → Settings → P1 with current values. Leave room → existing confirmation/release. Solo play omits Voice and room details; controls remain.

## P2 — Voice request and live (S2, S3, S4)

```text
+---------------------+   +---------------------+
| VOICE · Requesting  |   | VOICE · Mic on      |
| [Cancel request]    | → | [Mute]              |
+---------------------+   | Voice settings      |
                          +---------------------+
```

Permission granted → live. Denied/device error → P3. Mute → `VOICE · Muted` with `Unmute`. Push mode replaces `Mute` with a hold control and shows the mapped talk binding while held/released state changes.

## P3 — Voice error (S2, S5, S10)

```text
+-------------------------------+
| VOICE · Microphone unavailable|
| Permission denied             |
| [Try again]  Voice settings    |
+-------------------------------+
```

Try again → P2. Settings → device/remote audio recovery → return to play. Peer lost instead shows `Connecting` and room retry/leave, with capture off.

## P4 — Narrow play (S7, S9)

```text
RETRO COOP              Settings
+----------------------------+
|         NES GAME           |
+----------------------------+
Pause  Mute  Saves
+----------------------------+
| CONTROLS · Keyboard        |
| Move ↑ ← ↓ →   A X   B Z   |
| Start Enter  Select Shift  |
| Edit controls              |
+----------------------------+
| VOICE · Off [Enable voice] |
+----------------------------+
| Room status / Leave / Chat |
+----------------------------+
```

The page places cards after the game without overlapping it. Keyboard order follows this visual order. Long bindings wrap rather than crop. Gamepad selection replaces keyboard labels with current pad values.