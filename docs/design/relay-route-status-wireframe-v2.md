# Relay route status: current wireframe v2

The connected route occupies one compact status area in the existing fixed room panel. It has no new control, overlay or notification. The ASCII labels below **render** the exact D1/D2 copy governed by [direction](relay-route-status-direction.md); they are not an independent copy specification.

## Page P1 — Shared play, Standard selected relay (R02)

```text
+----------------------- GAME ------------------------+-- ROOM ------------------+
|                                                     | Super Tilt Bro            |
|                [playing canvas]                     | Host · Guest              |
|                                                     | Direct connection         |
|                                                     | unavailable. Relay keeps |
|                                                     | you playing together.     |
|                                                     | [controls] [voice]        |
|                                                     | [chat]                    |
|                                                     | [Leave room]              |
+-----------------------------------------------------+--------------------------+
```

Play continues. The message is a `role=status` update only when the selected route is relay. It becomes the existing interruption or error text as soon as the transport changes. Supports J1, R02/R08/R10.

## Page P2 — Shared play, Relay only selected (R05)

```text
+----------------------- GAME ------------------------+-- ROOM ------------------+
|                [playing canvas]                     | Super Tilt Bro            |
|                                                     | Relay only is on.        |
|                                                     | Connected through the    |
|                                                     | relay.                   |
|                                                     | [controls] [voice]       |
|                                                     | [chat]                   |
|                                                     | [Leave room]             |
+-----------------------------------------------------+--------------------------+
```

Play continues; the sentence states the choice without blaming a firewall. Supports J2, R05/R10.

## Page P3 — Recovery on relay failure (R06/R08)

```text
+----------------------- GAME ------------------------+-- ROOM ------------------+
|                [paused canvas]                      | Super Tilt Bro            |
|                                                     | Relay capacity is full.  |
|                                                     | [Retry connection]       |
|                                                     | [Stay in room]           |
|                                                     | [Leave room]             |
+-----------------------------------------------------+--------------------------+
```

Use the existing exact error for `Relay service is unavailable`, `Relay capacity is full`, or `Connection interrupted`, with the current conditional Retry/Stay/Leave controls. Retry is the primary recovery when available. Supports J1/J2/J3, R06/R08/R09/R10.

## Compact status mapping

| Selected route and policy | Room status |
| --- | --- |
| Relay + Standard | D1 in [direction](relay-route-status-direction.md) |
| Relay + Relay only | D2 in [direction](relay-route-status-direction.md) |
| Direct | Existing `Peer transport connected. Route: direct.` |
| Unknown | Existing `Peer transport connected.` without route claim |
| Connecting, disconnected or left | Existing preparation/error text, or no peer status after exit |

The same current status may be read in Settings, but opening Settings is never required to learn that play is using a relay. The fixed side panel remains visible; keyboard and screen-reader paths use the same state.

Sources: [direction](relay-route-status-direction.md), [references](relay-route-status-references.md), [journeys](relay-route-status-journeys.md), [scenarios](relay-route-status-scenarios.md), and [v1 critique](relay-route-status-critique-v1.md). Runtime implementation and accessibility remain unproven until tested in the integrated app.
