# Voice and play sidebar: scenario inventory

The cards serve only active play. The table makes their state changes and recovery concrete.

| ID | Journey | Trigger and visible result | Recovery |
|---|---|---|---|
| S1 | V1 | Peer connects in shared play; `Voice · Off` and `Enable voice` appear. No permission prompt yet. | If peer is not connected, show `Voice · Connecting` and no enabled capture action. |
| S2 | V1 | Enable clicked; `Requesting microphone…` and `Cancel` replace the action. | Denied/missing device → reason and `Try again`; browser site permission hint only then. |
| S3 | V1,V2 | Capture succeeds; `Mic on` + `Mute` (open mode), or `Hold to talk` + mapped binding (push mode). | Mute/disable in Voice detail; focus loss forces muted state. |
| S4 | V2 | Mute/unmute or hold/release; state text changes immediately. | Track ends or peer replaced → off/error and explicit new opt-in. |
| S5 | V3 | Incoming audio muted or playback denied; Voice detail shows status and direct recovery. | Retry playback or unmute; no gameplay reset. |
| S6 | C1 | Game loaded; card renders current keyboard binding labels including `Unbound`. | `Edit controls` opens Settings; return shows current saved values. |
| S7 | C2 | Selected gamepad exists; card shows pad bindings and device identity. | Input fault offers existing `Use keyboard`; card follows changed device. |
| S8 | C1,C2 | Binding changes while in Settings, including push-to-talk; side readout updates on return. | Conflict/unusable mapping remains an existing Settings error, not a silent wrong hint. |
| S9 | C3 | Narrow width/zoom; side cards follow canvas and retain readable labels, focus order and action reachability. | Wrap within viewport; no new overlay or document horizontal scroll. |
| S10 | E1 | Leave, kick, expiry, connection failure; card reflects disconnected/off and releases capture. | Existing room retry/leave or local resume actions remain available. |
| S11 | V1,C1 | Solo play; no voice card; controls card still visible. | A later shared session adds voice after peer state exists. |

## Visible feature coverage

| Feature | Entry and usable state | Feedback | Failure or exit |
|---|---|---|---|
| Enable voice | Playing room card, connected peer | Pending → live/muted | Error + Try again; disable/leave |
| Mute/Unmute or Hold to talk | Playing voice card, capture ready | Text state and pressed state | Connection loss stops capture; retry after recovery |
| Voice detail | Playing card’s `Voice settings` route | Device/remote controls and errors | Back to play; no overlay over game |
| Controls reference | Loaded game beside canvas | Current device and bindings | Unbound label and Edit controls |
| Edit controls | One link to Settings | Updated reference after return | Existing Settings cancel/conflict path |

Defects to resolve in screens: current Voice disclosure hides S1; current Game help hard-coded keys conflict with S8; current room side text competes with S6; narrow shared-play layout currently grows the document and must be checked against S9.
