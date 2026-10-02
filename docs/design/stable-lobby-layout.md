Loading, errors, and changing lobby information must update inside stable regions without moving nearby controls. The [unified lobby direction](unified-lobbies-direction.md) owns the current screens; the earlier screen map below is historical.

Audience: Human

# Stable lobby layout

The [minimal room journey](minimal-room-journey.md) changes which content appears in these regions. This document continues to own their fixed geometry; older wireframe, journey and scenario links below are historical where #169 removes a control or preview. Room access is Public or Password protected; the product chooses the connection path.

## Source and scope

This proposal governs [feature #158](https://github.com/TuringTestee/retro-coop/issues/158). The user's exact request is: “enhance the UI so the UI component is FIXED on slots, never allow any component to push other down/up espeically during loading. Everything should have a deterministic fixd postion.” Review and merge this direction and its [implementation plan](../implementation/stable-lobby-layout.md) before affected implementation.

Preserve the existing Public rooms, Create Game, invitation, room, playing, and secondary-task screens from [the current page wireframes](create-game-library-wireframe-v4.md), [journeys](create-game-library-journeys.md), [scenarios](create-game-library-scenarios.md), and [playing sidebar direction](voice-play-sidebar-direction.md). This amendment strengthens their fixed-region requirement: narrow stacking and scrolling remain, but asynchronous content must not change region positions or push sibling actions around. No new screen, floating panel, overlay, or navigation model is added.

[Feature #157](https://github.com/TuringTestee/retro-coop/issues/157) owns five-member room behavior and stable slot identities; its integrated implementation is a prerequisite for final five-row geometry acceptance. [Voice fix #156](https://github.com/TuringTestee/retro-coop/issues/156) owns microphone behavior. This layout work preserves its focus-independent mute state and keeps its immediate action easy to reach. [Issue #131](https://github.com/TuringTestee/retro-coop/issues/131) is an existing concrete regression in scope: paused host and guest views clip the bottom of Leave at 1366×682.

## Position and overflow contract

For a fixed page, viewport, zoom, and scroll position, the header, content regions, slot rows, status areas, and action areas keep the same bounds while their contents change. Loading does not insert a new row above an action. Empty, pending, success, and error feedback use the same reserved area. Buttons with changing labels keep their reserved position and size. Long names, messages, and loading percentages cannot resize their parent regions.

A deliberate navigation, viewport resize, zoom change, or user scroll can change what is visible. Each responsive layout still has predictable regions; it does not choose its geometry from the length or presence of a message. The game retains its aspect ratio, and opening existing details changes content inside its assigned scroll region rather than moving another region.

| Existing screen | Regions that remain stable | Overflow and recovery |
|---|---|---|
| Public rooms and invitation | Heading/navigation, search and room access cues, service status, room list or invite details, and page actions | Loading, stale, empty, and failed results use reserved status/list space. The list scrolls within its region; pagination and Join/Back do not move when results arrive. |
| Create Game | Heading/Back, library, Public or Password protected access, validation/upload feedback, and Create/Cancel actions | Library growth and long errors scroll inside their assigned areas; selection and upload progress cannot move Create. Narrow layouts use a deterministic stacked arrangement. |
| Waiting or playing room | Room heading, five numbered slot rows, each row's role/status/actions, game/controls, voice, chat, connection feedback, and room actions | Slot loading, role changes, reconnect, closure, and removal confirmation replace content within their regions. Slots never collapse. Chat growth and connection errors cannot push microphone or Leave controls out of view. |
| Settings, Local data, Saves, Rewind, Help, and release/recovery pages | Existing heading/Back, task content, feedback, and inline confirmation/action areas | Long settings/content and errors remain scrollable. Confirm/cancel occupies reserved action space. Returning restores usable focus without changing the underlying room or microphone state. |

On supported desktop playing layouts, the complete immediate voice action and Leave button remain visible, including paused and reconnecting states. At narrow or heavily zoomed sizes, arrange the same content in the existing stacked order and use an explicit content scroll region with reachable actions. Do not shrink text or controls to force every region on screen, suppress errors, or hide content with clipping. Scrolling is a user action, not an asynchronous layout shift. Focus must bring a complete control and its label into view without placing it beneath a fixed action region.

## Journeys and completion

| Journey | Entry, actions, and visible outcome | Recovery and completion |
|---|---|---|
| L1: Find or create a game | Open Public rooms; observe loading, live, empty, and stale results; open Create Game; select a saved/included/local game; wait for validation and upload. Headings, status regions, and next actions stay in place. | Inject a directory/download/upload error, retry or cancel, and preserve the same region bounds and prior valid selection. Complete when the visitor reaches the intended room or returns with an actionable recovery state. |
| L2: Manage five slots and play | Enter the #157 room; fill five slots; observe downloads/readiness; close/reopen or reassign a slot; start, pause, and reconnect while using voice and chat. Five slot rows and immediate actions retain their assigned positions. | Failed acquisition, pending role changes, long names, permission denial, reconnect messages, and leave/remove confirmation remain readable within their regions. Complete when the intended action succeeds or can be retried without hunting for a moved control. |
| L3: Use a short or zoomed window | Open the playing room at 1366×682, pause as both host and guest, and inspect Leave, connection feedback, and microphone controls. Repeat the existing pages at narrow widths and enlarged desktop zoom, navigating by keyboard. | Every action is fully visible or can be brought fully into its designated scroll viewport. Tab/Shift+Tab and existing Back/Cancel restore meaningful focus; no horizontal page overflow, overlapping labels, or unreachable content. Complete after the same intended task succeeds at each tested size. |

Acceptance needs actual before/after screenshots and measured region bounds through transitions, not an attractive final screenshot alone. Include short recordings or sampled geometry showing that a delayed response does not move actions. Issue #131 is resolved only after host and guest paused screenshots at its reported viewport show the entire Leave button and its bounds check passes. The [implementation plan](../implementation/stable-lobby-layout.md) owns the state matrix and test method.
