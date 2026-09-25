# Relay route status: scenario inventory

The current room side panel owns the visible route status. These scenarios refine its existing connection story without changing how players join, play or leave.

| ID / journey | Trigger | Visible result | Recovery or exit |
| --- | --- | --- | --- |
| R01 / J1 | Standard is preparing; no selected route yet | Existing `Connecting…` text; no relay success claim | Existing Retry if preparation fails |
| R02 / J1 | Standard connects through selected relay candidate pair | `Direct connection unavailable. Relay is keeping you connected.` beside shared play | Continue play; failure replaces text and exposes Retry |
| R03 / J1 | Standard connects directly | Existing connected status, without a relay explanation | Continue play; a later route change refreshes status |
| R04 / J2 | Relay only selected, connection still preparing | Existing Relay only preparation text | Retry/Stay in room on relay failure |
| R05 / J2 | Relay only connects via selected relay pair | `Relay only is on. You're connected through the relay.` beside shared play | Continue play; failure replaces text and exposes Retry |
| R06 / J2 | Relay unavailable or at capacity | Existing specific Relay unavailable/full text; no connected claim | Existing Retry connection or Stay in room; never silently use direct |
| R07 / J1,J2,J3 | Selected route is unknown even though transport reports connected | `Peer transport connected.` only; do not infer relay | Play continues; subsequent stats or reconnect can establish route |
| R08 / J3 | Transport disconnects, policy changes or reconnect begins | Remove relay success text; show existing interruption/preparation state | Existing Retry or reconnection path |
| R09 / J3 | Player leaves, room closes or starts solo | No peer-route message on the directory or solo game | Existing room exit/recovery path |
| R10 / J1,J2,J3 | Narrow desktop, keyboard or screen reader | Same visible text in fixed panel; one `role=status` update, no overlay or focus theft | Existing controls remain keyboard accessible |

| Visible feature | Entry | Usable state | Feedback | Failure / exit |
| --- | --- | --- | --- | --- |
| Relay route message | Existing room side panel | Selected relay route and connected peer | One of the R02/R05 sentences | R06/R08/R09 replace or clear it |
| Retry connection | Existing connection settings | Failed connection | Existing preparation and resulting route status | Stay in room or Leave |
| Connection policy | Existing Create/Join and Settings controls | Before peer contact or during policy reconnect | Preparation, then R02/R03/R05 or failure | Existing Retry/Stay in room |

Defects to resolve in the wireframe: the present technical `Route: relay` string is terse and disappears during play; Settings is the only way to read it then. Do not add a second alert, an early firewall warning, or a duplicate Retry button.
