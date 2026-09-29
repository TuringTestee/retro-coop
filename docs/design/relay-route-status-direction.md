# Relay route status: direction

The [minimal room journey](minimal-room-journey.md) supersedes persistent connected-route messages in ordinary play. Show plain connection failure and recovery when needed; the exact messages below remain historical evidence for the earlier requested design.

The current shipped game shows a short route message beside play. **Until the minimal room journey is implemented, this file defines the exact connected-route copy (D1 and D2).** After #169 removes routine connected-route copy, these messages are historical. Failure and recovery feedback remains required. Journeys, scenarios and ASCII screens below refer to those IDs for the shipped behavior.

| ID / behavior | Source | Existing behavior it changes |
| --- | --- | --- |
| D1 — When the selected WebRTC route is relay under Standard policy, show `Direct connection unavailable. Relay keeps you playing together.` in the fixed room side panel. | User request for a friendly, short relay explanation; [reference evidence](relay-route-status-references.md). | The room says `Peer transport connected. Route: relay.` before play and hides that status during active shared play. |
| D2 — When the selected WebRTC route is relay and either player selected Relay only, show `Relay only is on. Connected through the relay.` | Existing privacy policy: direct was not attempted. | The same technical route string makes voluntary relay look like a network failure. |
| On a direct route, keep the existing `Peer transport connected. Route: direct.` status; on failed or unknown routes, keep the existing specific recovery status. | Existing room journey and connection contract. | No new banner or success claim before the selected route is known. |
| Use one `role=status` text area in the room side panel while connected; Settings may show the same status string but is not an alternative required route to find it. | Existing fixed-page layout and just-in-time state requirement. | Connection status currently disappears from the room during shared play and is only in Settings. |

The text has no extra button, icon, advertisement or overlay. Retry connection remains the existing failure action. The message clears or changes immediately after a route transition, disconnect, leave or room close. It does not name a firewall, promise latency, or imply that the relay emulates the game.
