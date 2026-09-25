# Relay route status: direction

Players should see a short, accurate message when their shared game is using a relay. The message belongs beside the game and stays visible while that route is active.

| Behavior | Source | Existing behavior it changes |
| --- | --- | --- |
| When the selected WebRTC route is relay under Standard policy, show `Direct connection unavailable. Relay keeps you playing together.` in the fixed room side panel. | User request for a friendly, short relay explanation; [reference evidence](relay-route-status-references.md). | The room says `Peer transport connected. Route: relay.` before play and hides that status during active shared play. |
| When either player selected Relay only, show `Relay only is on. Connected through the relay.` | Existing privacy policy: direct was not attempted. | The same technical route string makes voluntary relay look like a network failure. |
| On a direct route, keep the existing concise connected status; on failed or unknown routes, keep the existing specific recovery status. | Existing room journey and connection contract. | No new banner or success claim before the selected route is known. |
| Use one `role=status` text area in the room side panel while connected; Settings may show the same status string but is not an alternative required route to find it. | Existing fixed-page layout and just-in-time state requirement. | Connection status currently disappears from the room during shared play and is only in Settings. |

The text has no extra button, icon, advertisement or overlay. Retry connection remains the existing failure action. The message clears or changes immediately after a route transition, disconnect, leave or room close. It does not name a firewall, promise latency, or imply that the relay emulates the game.
