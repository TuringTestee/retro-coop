Audience: Agent

# Voice and play sidebar delivery plan

The [stable layout amendment](../design/stable-lobby-layout.md) governs loading and feedback geometry. The later [minimal room journey](../design/minimal-room-journey.md) owns the current play card and supersedes this plan's former always-visible binding readout.

Make voice chat easy to start during a shared game, show the player's current role and Players action, and open control bindings in Settings when needed. Reuse the existing WebRTC voice and control settings without covering the game.

## Scope and source

Human direction is the 2026-09-24 voice request as amended by the later [minimal room journey](../design/minimal-room-journey.md). The earlier [wireframe v2](../design/voice-play-sidebar-wireframe-v2.md), [journeys](../design/voice-play-sidebar-journeys.md) and [scenarios](../design/voice-play-sidebar-scenarios.md) retain voice recovery context. Existing approved [U7 behavior](../design/browser-nes-ui.md#u7--controls-display-voice-and-settings) still governs explicit capture, mute, permission/device recovery and remote audio. This work adds discoverability without accounts, group calls, recording, speech detection, video, public-network release qualification or a new controller system.

## Architecture and reuse decisions

1. Keep the existing peer media pipeline. Room membership and peer connectivity gate voice. Do not request the microphone until `Enable voice` is clicked. Retain track release on leave/reconnect/peer replacement and the current recovery controls. Focus changes follow [Background voice](background-voice.md); Disable microphone, leave or peer replacement stops tracks.
2. Derive the compact play role from the accepted controller assignment, not Host/Guest. Separate mode can swap P1/P2; Shared P1 can put either person in control. An observer sees no binding prompt. The Players action opens the existing slot view. Controls opens Settings, the sole mapping list and editor; its selected keyboard/gamepad bindings use `controls.ts` labels and show `Unbound` for empty actions. Solo play retains the Controls entry but no voice card.
3. Use the current `playing.with-room` side region and the solo game's right space. Put controls and immediate voice state before lower-frequency room details. The card should not create a new page overlay or shrink the canvas below its current supported minimum. A narrow viewport stacks cards after the game in source order. Keep optional device, remote audio and push mode settings in the existing Voice detail, with a single `Voice settings` entry from the card.
4. Keep one state owner. The new card derives from `VoiceState` and calls the existing `VoiceSession`; it must not clone microphone state or create another peer connection. Avoid rendering two live Enable/Mute controls at once in the play view. The old room Voice disclosure becomes the detail destination or is removed from that view. Settings can retain the full controls when its separate page is open.
5. Remove hard-coded default keys from Game help, replacing them with a pointer to Controls or Settings. Gameplay help still owns game-specific instructions and credits.

## Integrated acceptance

- Host and guest independently join and start the same game. Each sees the assigned NES port and a visible Players action with the game canvas unobscured. Controls opens the current keyboard or selected gamepad bindings in Settings; remap, return with focus, and reopen to see the updated value. Unbound and lost-pad cases have a recovery action.
- With voice off, neither browser has captured a microphone. One player chooses Enable voice, grants access, speaks; the other opts in separately. Two-way decoded audio, mute/unmute, push-to-talk key/button, focus loss, permission/device/playback failure, reconnect and leave preserve game progress. Focus changes preserve explicit mute and release held push-to-talk under [Background voice](background-voice.md); Disable microphone, leave and peer replacement stop tracks.
- Capture matched desktop and narrow screenshots from the running build. Check source/keyboard order, screen-reader labels and status, visible focus, wrapping/overflow and no page overlay. Check the side rail's content at solo, shared, pending, error and disconnected states. Verify the Game help copy no longer contradicts remapped bindings.
- Run focused voice, gameplay and control browser checks, then `timeout 60s sh scripts/preflight.sh`. Required PR checks must pass. After merge, full main core/network qualification remains necessary for the broader release; public-network microphone quality and real hardware remain the existing #25/#27 release gates.

## Review and authorization

The user directly requested the compact controls sidebar and visible voice control, and clarified that faithful requested work needs no second plan approval. Independent review must verify fidelity and feasibility at the current PR head, and the governing documents must merge before implementation. Any new player-facing design beyond that request returns to the user. Required checks and the existing scoped merge authorization still apply.
