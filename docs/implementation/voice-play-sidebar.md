Audience: Agent

# Voice and play sidebar delivery plan

Make voice chat easy to start during a shared game, and show the player's current control bindings in a small side panel. Reuse the existing WebRTC voice and control settings, then prove the flow in two browsers without covering the game.

## Scope and source

Human direction is the 2026-09-24 request for voice chat and a very compact, sleek side list of shortcuts and controls. The current design is [wireframe v2](../design/voice-play-sidebar-wireframe-v2.md), backed by [journeys](../design/voice-play-sidebar-journeys.md) and [scenarios](../design/voice-play-sidebar-scenarios.md). Existing approved [U7 behavior](../design/browser-nes-ui.md#u7--controls-display-voice-and-settings) still governs explicit capture, mute, permission/device recovery and remote audio. This plan adds discoverability and a live shortcut readout; it does not add accounts, group calls, recording, speech detection, video, public-network release qualification or a new controller system.

Current source snapshot: `apps/client/src/VoiceControls.tsx` owns voice actions; `RoomPanel.tsx` renders Voice behind a room-tool disclosure; `main.tsx` owns play layout, Settings, and Game help; `controls.ts` owns bindings and labels; `style.css` owns fixed play geometry. Browser voice work already exists in `scripts/voice/browser_smoke.py`; gameplay/browser and settings/foundation probes cover the adjacent journeys. Snapshot base for this draft is `aa2c897`; PR #113's test-only repair merged at `0b57fb9` while this plan was authored. Rebase before implementation and recheck paths.

## Architecture and reuse decisions

1. Keep the existing peer media pipeline. Room membership and peer connectivity gate voice. Do not request the microphone until `Enable voice` is clicked. Retain track release on leave/reconnect/peer replacement and the current recovery controls. Window blur mutes transmission but retains capture; Disable microphone, leave or peer replacement stops tracks.
2. Build one presentational play-side component that receives the current `Controls`, accepted controller assignment, room role, and voice state. Separate mode can swap P1/P2; Shared P1 can put either person in control. When the partner owns Shared P1, show an idle input state instead of active binding prompts. The existing Session controllers path remains the only handoff editor. Use `controls.ts` labels and the selected keyboard/gamepad bindings; do not duplicate a default-key table. Unbound actions display `Unbound`. The reference is visible in solo play too, but voice only appears when a room has started. The existing Settings page remains the only mapping editor.
3. Use the current `playing.with-room` side region and the solo game's right space. Put controls and immediate voice state before lower-frequency room details. The card should not create a new page overlay or shrink the canvas below its current supported minimum. A narrow viewport stacks cards after the game in source order. Keep optional device, remote audio and push mode settings in the existing Voice detail, with a single `Voice settings` entry from the card.
4. Keep one state owner. The new card derives from `VoiceState` and calls the existing `VoiceSession`; it must not clone microphone state or create another peer connection. Avoid rendering two live Enable/Mute controls at once in the play view. The old room Voice disclosure becomes the detail destination or is removed from that view. Settings can retain the full controls when its separate page is open.
5. Remove hard-coded default keys from Game help, replacing them with a pointer to the current controls card. Gameplay help still owns game-specific instructions and credits.

## Delivery and dependencies

The Project epic #2 remains the parent. This scope needs one new integrated play-communication gate, because it changes visible in-game behavior across voice, controls, role and width. Do not fold acceptance into open lobby gate #66, which owns the room creation/join release flow. The planner published three draft cards in [Retro Coop Project #1](https://github.com/orgs/TuringTestee/projects/1): `PVTI_lADOE0HVec4BkDjlzg8euHU` for live mapped controls and fixed layout, `PVTI_lADOE0HVec4BkDjlzg8euHw` for visible voice entry and state/recovery, and `PVTI_lADOE0HVec4BkDjlzg8euIc` for the integrated two-browser gate. All are verified P1/Blocked pending approved merged PR #114; the voice card additionally depends on the controls layout, and the gate depends on both delivery cards. Their bodies identify owner roles, journeys, acceptance and evidence. UI and voice cards can share a PR if it stays reviewable; the integrated gate depends on both. Preserve the project's existing merge authorization B, independent reviewer, and CI budgets.

## Integrated acceptance

- Host and guest independently join and start the same game. Each sees their assigned NES port, including swapped Separate P1/P2 and the active/idle Shared P1 handoff states, and current keyboard or selected gamepad bindings, with game canvas unobscured. Remap a binding, return, and see the updated value. Unbound and lost-pad cases have a recovery action.
- With voice off, neither browser has captured a microphone. One player chooses Enable voice, grants access, speaks; the other opts in separately. Two-way decoded audio, mute/unmute, push-to-talk key/button, focus loss, permission/device/playback failure, reconnect and leave preserve game progress. Blur mutes capture without stopping the track; Disable microphone, leave and peer replacement stop tracks.
- Capture matched desktop and narrow screenshots from the running build. Check source/keyboard order, screen-reader labels and status, visible focus, wrapping/overflow and no page overlay. Check the side rail's content at solo, shared, pending, error and disconnected states. Verify the Game help copy no longer contradicts remapped bindings.
- Run focused voice, gameplay and control browser checks, then `timeout 60s sh scripts/preflight.sh`. Required PR checks must pass. After merge, full main core/network qualification remains necessary for the broader release; public-network microphone quality and real hardware remain the existing #25/#27 release gates.

## Review snapshot and approval

This draft describes new visible behavior. An independent Vaseline review must score its fidelity and feasibility at an exact PR head. The user must approve that reviewed version and the governing docs must merge before the implementation PR starts. Technical review does not substitute for that approval. The current main CI for merged PR #113 is still running, and this plan does not claim it passed.
