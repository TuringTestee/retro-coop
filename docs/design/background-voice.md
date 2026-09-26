# Voice that stays on when focus changes

Players can keep talking while another tab or window has focus. A visible microphone button controls mute, and changing focus does not change that choice.

## Direction and scope

The owner requested this on 2026-09-26: “make sure when users do voice chat, even if it's from the same machien with different browser tab, or from differet machine, there's a mic mute button not affected from tab focus, player should even talk with background -- like a real video meeting.” [Feature #156](https://github.com/TuringTestee/retro-coop/issues/156) tracks delivery. This faithful amendment replaces the focus-mutes-open-microphone policy in [optional voice](../implementation/d17-voice.md). This is the governing policy implemented by #156. Current platform/UI/scenario/sidebar documents point here for the replacement policy. Five-slot membership and stable layout are separate requested features, #157 and #158, and are not claimed complete by this change.

## Talk, switch tabs, and mute

A room member joins through Public rooms or an invitation, then explicitly enables voice in the lobby or game. Browser permission appears only after this action. The microphone control visibly reports whether capture is pending, off, muted, active, or unavailable. Once enabled in open-microphone mode, speech keeps reaching other members when the member changes tabs or windows. The mute/unmute control remains discoverable in both lobby and gameplay; it is also available in push-to-talk mode. Muting silences transmission and remains in effect across focus changes. Unmuting is an explicit action.

Push-to-talk still requires a held button or mapped input. Losing focus releases that input without changing the mute choice. Returning does not restore an old held press. Typing in chat cannot activate a mapped talk key. Keyboard push-to-talk cannot receive keys from unrelated tabs; open microphone is the background-conversation mode.

The journey succeeds when the other member continues receiving speech while the speaker uses another tab, explicit mute silences it, and leaving stops capture. Same-machine tabs keep separate memberships and independent mute state. Headphones avoid the predictable feedback from two nearby speakers and microphones.

## Recovery

Permission denial explains how to allow the microphone and offers explicit retry without restarting the game. A pending permission request may finish after a focus change; consent plus the member's current mute choice governs transmission. Explicit cancellation or departure invalidates that request and stops late tracks. Device replacement stays muted until deliberate unmute. A disconnected device reports unavailable and permits another device/retry. Departure, removal, room closure and replacement of the voice session stop capture; reconnect remains opt-in.

Browser or operating-system loss of access can interrupt capture regardless of app focus policy. Do not claim that a tab can talk after it is discarded, the machine sleeps, or microphone access is revoked. Keep existing playback retry and connection recovery distinct from microphone mute. Browser-provided echo cancellation and noise suppression remain best effort; no recording or transcription is introduced.
