Audience: Human

Players should see their role and voice status beside the NES screen, with control mappings available when opened and no automatic microphone capture.

# Voice and play sidebar: direction

The [stable layout amendment](stable-lobby-layout.md) governs loading and feedback geometry: existing screens and responsive order remain, but asynchronous content stays inside reserved regions. Its explicit scroll-region contract supersedes earlier content-driven expansion or page-flow instructions below.

The later [minimal room journey](minimal-room-journey.md) replaces this proposal's persistent control-binding readout with a compact role and Controls action. The voice permission, status and recovery behavior below still applies.

Players should be able to start voice chat and check the controls without leaving the game. The side area stays compact, fixed beside the game on supported desktop widths, and shows only facts and actions needed now.

| Source | Behavior to deliver | Current behavior replaced |
|---|---|---|
| User request, 2026-09-24 | Enable voice chat during shared play. | Voice transport already exists, but its entry is a collapsed room-tool disclosure; users may miss it. |
| User request, 2026-09-24 | Show a very compact, sleek side list of shortcuts and controls while playing. | No playing control reference; Game help hard-codes default keys despite remapping. |
| Existing approved voice direction, `docs/design/browser-nes-ui.md` U7 | Microphone starts only after an explicit click; show off/pending/live/muted/error state and recovery. | Preserve opt-in transport and Settings recovery, make the immediate action easier to find. |
| Existing fixed-page direction | Game and side information occupy fixed regions; no page overlay. | Side room panel already exists but is verbose and scrolls. |

## Recommended decisions

- One playing side rail contains a compact `Controls` card and `Voice` card before room details. It does not appear in discovery, Create game, or a waiting room without active play.
- The compact play card shows the accepted local NES port, a Players action for the room, and a Controls action for the Settings mapping list. Derive the port from the accepted controller assignment, not Host/Guest: Separate may swap P1/P2; Shared P1 may assign either person. A member without a controller sees Observer rather than binding prompts. Settings renders actual keyboard or selected gamepad mappings and says `Unbound` for an empty action. An accepted handoff updates the play role after the shared game resumes.
- `Voice` displays `Off`, `Connecting`, `Mic on`, `Muted`, `Hold to talk`, or a specific error, with one immediate action (`Enable voice`, `Mute`, `Unmute`, `Hold to talk`, or `Try again`) according to state. Keep device choice, remote volume and advanced recovery in the existing detail section. Voice is available to the two room members only when their peer connection is ready. Solo play shows no voice card.
- Do not start microphone capture automatically. Keep the existing peer transport and current room capacity for this voice slice. [Background voice](background-voice.md) replaces the original focus-mute rule; Disable microphone, room exit, or peer replacement stops capture. A player without permission gets a concise explanation and retry; text chat and game remain available.
- Keep `Settings` as the sole mapping list and editor. Change Game help’s fixed default-key sentence to point to Controls or Settings, avoiding contradictory instructions.

## Open choices and recommendation

There is no user decision needed to draw the proposal. Use the current right-side region rather than adding another column. At narrow desktop widths, put the controls and voice cards immediately below the canvas in the same document flow, without a floating overlay. Validate actual fit with screenshots and keyboard navigation before acceptance.
