# Voice that stays on when focus changes

Players can keep talking while another tab or window has focus. A visible microphone button controls mute, and changing focus does not change that choice.

## Direction and scope

The owner requested this on 2026-09-26: “make sure when users do voice chat, even if it's from the same machien with different browser tab, or from differet machine, there's a mic mute button not affected from tab focus, player should even talk with background -- like a real video meeting.” [Feature #156](https://github.com/TuringTestee/retro-coop/issues/156) tracks delivery. This faithful amendment replaces the focus-mutes-open-microphone policy in [optional voice](../implementation/d17-voice.md). This is the governing policy implemented by #156. Current platform/UI/scenario/sidebar documents point here for the replacement policy. Five-slot membership and stable layout are separate requested features, #157 and #158, and are not claimed complete by this change.

## Talk, switch tabs, and mute

A member hosts or joins a lobby through the main listing or an invitation. The first connected peer starts voice in push-to-talk mode through the browser's microphone permission policy; visiting the main page alone does not start capture. This follows the later default-voice direction implemented in the unified lobby. The microphone control reports whether capture is pending, off, muted, active, or unavailable. Switching to open microphone lets speech keep reaching other members when the member changes tabs or windows. Mute/unmute remains available in Settings → Voice during lobby and gameplay. Muting silences transmission and remains in effect across focus changes. Unmuting is an explicit action.

Push-to-talk still requires a held button or mapped input. Losing focus releases that input without changing the mute choice. Returning does not restore an old held press. Typing in chat cannot activate a mapped talk key. Keyboard push-to-talk cannot receive keys from unrelated tabs; open microphone is the background-conversation mode.

The journey succeeds when the other member continues receiving speech while the speaker uses another tab, explicit mute silences it, and leaving stops capture. Same-machine tabs keep separate memberships and independent mute state. Headphones avoid the predictable feedback from two nearby speakers and microphones.

## Recovery

Permission denial explains how to allow the microphone and offers explicit retry without restarting the game. A pending permission request may finish after a focus change; consent plus the member's current mute choice governs transmission. Explicit cancellation or departure invalidates that request and stops late tracks. Device replacement stays muted until deliberate unmute. A disconnected device reports unavailable and permits another device/retry. Departure, removal, room closure and replacement of the voice session stop capture. Joining again starts a fresh push-to-talk session under the browser's permission policy.

Browser or operating-system loss of access can interrupt capture regardless of app focus policy. Do not claim that a tab can talk after it is discarded, the machine sleeps, or microphone access is revoked. Keep existing playback retry and connection recovery distinct from microphone mute. Browser-provided echo cancellation and noise suppression remain best effort; no recording or transcription is introduced.
