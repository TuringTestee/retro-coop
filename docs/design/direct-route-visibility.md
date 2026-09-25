Players should see live FPS and peer ping while playing together. The game should call out relay use only when the selected gameplay path is relayed.

# Direction and source

The user requested on September 25, 2026: “learn from war3 or aoe, try not to rely -- only when absolutely needed, and flag logs for debugging, and make sure the game shows what we added as warning message”; then “make sure you do exactly how war3 or aoe2 to handle direct game connection, and show FPS and network ping on the sidebar”; then “also show if rely (don't mention rely if not, because its uncommon”. These are the governing requests for this change.

The [existing relay direction](relay-route-status-direction.md) owns the exact relay messages and their placement. The [existing relay journeys](relay-route-status-journeys.md) own route change and recovery. This document adds only the metric journey below. The browser uses the same player-hosted model—server discovery, direct gameplay when possible—through WebRTC ICE. It cannot reuse a native game's network protocol.

# Game sidebar metric journey

1. When shared play starts, the fixed side panel shows “FPS — · Ping —” until real samples arrive. It does not mention relay merely because a TURN candidate was offered.
2. After rendered frames and the selected peer connection produce samples, the values update as “FPS 60 · Ping 42 ms” (example numbers). FPS counts frames actually drawn per elapsed second. Ping is the selected peer path's current round-trip time, not the room server's response time or the first handshake delay.
3. If play pauses or the path has no current RTT sample, the relevant value becomes a dash. It updates again on resume or reconnection. A new game resets both readings.
4. If the selected path is relayed, the existing relay direction's message appears near these metrics. Direct play has no relay warning. Failures use the existing recovery journey.

There is no extra setup step, control, page, or duplicate connection status.
