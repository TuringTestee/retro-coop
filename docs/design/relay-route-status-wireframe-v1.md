# Relay route status: wireframe v1

This first pass places the active route in the fixed room panel. It is a status, so the play and recovery controls stay where they already are.

## Page P1 — Shared play, Standard used a relay (R02)

```text
+------------------------ GAME ------------------------+-- ROOM ------------+
|                                                       | Super Tilt Bro       |
|                  [playing canvas]                     | You · Player 1       |
|                                                       | Guest · Player 2     |
|                                                       | Connection           |
|                                                       | Direct connection    |
|                                                       | unavailable. Relay  |
|                                                       | is keeping you       |
|                                                       | connected.           |
|                                                       | [controls] [voice]   |
|                                                       | [chat]               |
|                                                       | [Leave room]         |
+-------------------------------------------------------+----------------------+
```

The next action is normal play; Leave room is the existing exit. Connection failure moves to P3. A changed selected route replaces this message with the direct/unknown status. Supports J1, R02/R03/R07/R08/R10.

## Page P2 — Shared play, Relay only was chosen (R05)

```text
+------------------------ GAME ------------------------+-- ROOM ------------+
|                  [playing canvas]                     | Super Tilt Bro       |
|                                                       | Connection           |
|                                                       | Relay only is on.    |
|                                                       | You're connected     |
|                                                       | through the relay.   |
|                                                       | [controls] [voice]   |
|                                                       | [chat]               |
|                                                       | [Leave room]         |
+-------------------------------------------------------+----------------------+
```

The next action is normal play. Policy changes use the existing Settings route and show preparation until a new selected route is known. Supports J2/J3, R04/R05/R08/R10.

## Page P3 — Relay fails before or during play (R06/R08)

```text
+------------------------ GAME ------------------------+-- ROOM ------------+
|                  [paused canvas]                      | Super Tilt Bro       |
|                                                       | Connection           |
|                                                       | Relay unavailable.   |
|                                                       | [Retry connection]   |
|                                                       | [Stay in room]       |
|                                                       | [Leave room]         |
+-------------------------------------------------------+----------------------+
```

Retry connection is the primary recovery; Stay in room preserves the current reservation when retry must wait. Leave room is the exit. Exact unavailable/full/interrupted text comes from the existing error state. Supports J1/J2/J3, R06/R08/R09/R10.
