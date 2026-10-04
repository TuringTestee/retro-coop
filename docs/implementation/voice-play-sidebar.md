Audience: Agent

# Voice and play settings

Keep voice and control settings in the permanent right side of the lobby/game shell. The current [unified lobby direction](../design/unified-lobbies-direction.md) replaces the earlier compact-card and separate Players/Settings navigation proposed for this sidebar.

[Current voice ownership and replay qualification](d17-voice.md) define default push-to-talk startup through browser permission, microphone/remote audio state, device and playback recovery, and teardown. The [background voice amendment](background-voice.md) owns focus behavior: open microphone preserves explicit mute, while focus loss releases held push-to-talk input. Use those sources rather than maintaining a second media implementation or acceptance checklist here.

Settings must derive microphone state from `VoiceState` and call the existing `VoiceSession`; it must not create another capture or peer transport. Keep meaningful recovery actions available in both desktop and compact layouts without covering the NES screen or opening another page. The current control diagram derives the configured bindings; the Settings editor remains their only mapping owner.

The original sidebar request and its [historical design](../design/voice-play-sidebar-direction.md) explain the move out of collapsed tools. Later unified-lobby and default-voice direction supersede manual-only capture initiation, the two-member ceiling and source-flow layout in that proposal. Real devices and public-network qualification remain separate obligations; local fake-device success cannot establish them.
