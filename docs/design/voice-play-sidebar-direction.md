Audience: Human

Players should see their current game controls and voice status beside the NES screen, with no overlay or automatic microphone capture.

# Voice and play sidebar: direction

Players should be able to start voice chat and check the controls without leaving the game. The side area stays compact, fixed beside the game on supported desktop widths, and shows only facts and actions needed now.

| Source | Behavior to deliver | Current behavior replaced |
|---|---|---|
| User request, 2026-09-24 | Enable voice chat during shared play. | Voice transport already exists, but its entry is a collapsed room-tool disclosure; users may miss it. |
| User request, 2026-09-24 | Show a very compact, sleek side list of shortcuts and controls while playing. | No playing control reference; Game help hard-codes default keys despite remapping. |
| Existing approved voice direction, `docs/design/browser-nes-ui.md` U7 | Microphone starts only after an explicit click; show off/pending/live/muted/error state and recovery. | Preserve opt-in transport and Settings recovery, make the immediate action easier to find. |
| Existing fixed-page direction | Game and side information occupy fixed regions; no page overlay. | Side room panel already exists but is verbose and scrolls. |

## Recommended decisions

- One playing side rail contains a compact `Controls` card and `Voice` card before room details. It does not appear in discovery, Create game, or a waiting room without active play.
- `Controls` lists the current player’s directional cluster, A, B, Start, Select, and Push to talk only when voice uses that mode. Derive the local NES port from the accepted controller assignment, not from Host/Guest: Separate may swap P1/P2; Shared P1 may assign either person. When the other person owns Shared P1, say `Your input is idle · Shared P1 is with [name]` instead of suggesting these keys will control the game. An accepted handoff updates the card after the shared game resumes. Render values from the actual keyboard or selected gamepad mappings. If an action is unbound, say `Unbound`, with one `Edit controls` route to Settings. Use real text and accessible labels; styling may use restrained keycap shapes and accent color.
- `Voice` displays `Off`, `Connecting`, `Mic on`, `Muted`, `Hold to talk`, or a specific error, with one immediate action (`Enable voice`, `Mute`, `Unmute`, `Hold to talk`, or `Try again`) according to state. Keep device choice, remote volume and advanced recovery in the existing detail section. Voice is available to the two room members only when their peer connection is ready. Solo play shows no voice card.
- Do not start microphone capture automatically. Keep the existing peer transport, focus/blur safety, and two-person limit. Blur mutes transmission but keeps the captured track until Disable microphone, room exit, or peer replacement. A player without permission gets a concise explanation and retry; text chat and game remain available.
- Keep `Settings` as the sole mapping editor. Change Game help’s fixed default-key sentence to point to the current side reference, avoiding contradictory instructions.

## Open choices and recommendation

There is no user decision needed to draw the proposal. Use the current right-side region rather than adding another column. At narrow desktop widths, put the controls and voice cards immediately below the canvas in the same document flow, without a floating overlay. Validate actual fit with screenshots and keyboard navigation before acceptance.