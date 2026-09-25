Retro Coop should connect players directly whenever their networks permit it. If the selected gameplay path uses the relay, show that fact in the game and keep the players playing.

# Direct connection and relay journey

1. A host creates a room and a guest joins with Standard connection privacy. The browsers test direct and relay candidates through WebRTC ICE. ICE prefers direct candidates; the chosen path, rather than the presence of a TURN candidate, determines whether gameplay uses the relay.
2. If the chosen path is direct, shared play starts with no relay mention in the game side panel. The compact side panel shows current rendered FPS and peer network ping. If either metric is not yet available, show a dash instead of an invented value.
3. If direct connectivity is unavailable and the chosen path is relayed, shared play starts normally. The fixed game side panel adds a short notice: “Direct connection unavailable. Relay keeps you playing together.” The notice stays visible while the route is relayed and clears if a later connection becomes direct. FPS and ping remain visible.
4. If either player selects Relay only before connecting, both use relay candidates. The game side panel instead says “Relay only is on. Connected through the relay.” If relay capacity or service is unavailable, show the specific failure and Retry or Stay in room; never silently switch to direct.
5. If the connection is interrupted, replace the relay notice with the existing interruption and recovery status. A new successful route determines the next notice.

The relay notice appears only after the selected path is known. No new setup control or extra page is needed. Connection status and compact metrics share the existing fixed side panel.
