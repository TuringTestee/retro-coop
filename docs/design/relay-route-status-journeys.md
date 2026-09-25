# Relay route status: affected journeys

The room's connection status follows the real peer route through preparation, play and recovery.

| Journey | Arrival → decision → action → feedback → outcome → recovery |
| --- | --- |
| J1 Standard connection falls back to relay | Host and guest join one room with Standard selected → each prepares/starts through the existing room action → the browsers establish a peer connection and the selected candidate pair is relay → the fixed room side panel says `Direct connection unavailable. Relay is keeping you connected.` during shared play → both continue playing and can use voice/chat as before → if the connection later fails, the success message is replaced by the existing failure text and `Retry connection`; if it reconnects directly, the relay message clears. |
| J2 Deliberate Relay only | A player chooses Relay only beside the existing Join/Create action or in Connection settings → both peers use that policy before candidate exchange → after the selected relay route connects, the fixed room side panel says `Relay only is on. You're connected through the relay.` → shared play continues → if relay is unavailable/full, show the existing specific error and Retry/Stay in room; never claim a connection or switch to direct silently. |
| J3 Player checks or exits | During a connected shared game, the player reads the route in the fixed room side panel; Settings repeats the same current status only if opened for other connection choices → the player may keep playing, change policy through the existing Settings control, or leave through the existing room action → a policy reconnect shows preparation until its new route is known, then the matching status → leaving or room closure removes the route message with the room. |

Each journey uses the existing Join/Create, Prepare/Start, Retry, Settings and Leave paths. The status itself is informational and adds no competing action.
