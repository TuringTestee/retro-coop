Audience: Agent

# Lobby voice

Voice shares the existing lobby peer connections. Joining or hosting does not capture on the main page; the first connected lobby peer starts a browser permission request and push-to-talk mode. Settings → Voice owns microphone, playback and recovery controls in the existing shell.

## Ownership and safety

This follows voice feature #21, the [background voice amendment](background-voice.md), and the current [unified lobby direction](../design/unified-lobbies-direction.md). `RoomController` starts voice once per joined lobby. `VoiceSession` owns up to four independent remote audio elements and one capture shared with authenticated peer senders. `Microphone` owns capture generations, desired mute, held push-to-talk input and serialized track replacement. Leaving invalidates pending capture and stops late tracks; removing one peer preserves the remaining peers and the member's mute choice.

Push-to-talk transmits only while fresh mapped input is held. Typing and dialogs cannot activate it. Losing focus releases held input; returning cannot resume an old press. Open microphone continues across tab or window focus changes, while explicit mute stays unchanged. The application cannot override OS sleep, discarded tabs or revoked microphone access.

Permission denial and unavailable devices permit an explicit retry. Changing devices stops the old capture and keeps the new one muted until deliberate unmute. Connection binding, remote playback and device-list failures have separate recovery actions in the same Voice settings, including the compact layout. Feedback and its recovery action are selected together when failures overlap. Playback and device refresh results belong to the latest request; departure invalidates outstanding results. Recovery keeps a visible keyboard focus indication inside its fixed control, and avoids repeating a microphone/device action already present in the selected section. They preserve the existing peer and game timeline. Incoming voice mute and volume are independent of game sound. Echo cancellation and noise suppression are browser capabilities, not acoustic-quality guarantees; no recording or transcription is introduced.

## Replay qualification

Prepare the documented browser core and select the supplied catalog build:

```sh
sh scripts/foundation/prepare.sh
PUBLIC_CATALOG_GAMES=super-tilt-bro-pal npm run build
```

Use Python Playwright 1.58 and its full Chromium installation:

```sh
python3 scripts/voice/journey_browser.py --serve --mode tabs --output /tmp/voice-tabs
python3 scripts/voice/journey_browser.py --serve --mode processes --output /tmp/voice-processes
```

The two modes exercise pages sharing one browser context and two independent browser processes. The probe loads the tracked Super Tilt Bro artifact only for testing, starts real shared emulation, and measures decoded incoming RTP audio energy, mute silence, focus behavior, push-to-talk, text isolation, native permission denial/retry, fake-device replacement, modeled disconnection, compact playback/attachment recovery, rejoin and capture teardown. It saves selected UI states and numeric results outside the repository. Both modes run in the existing entrypoint UI CI job; microphone/voice unit tests cover capture races and mesh ownership.

Generated microphone audio establishes transport and decoding, not human audibility, intelligibility or physical unplug behavior. The device-ended callback and playback rejection are explicit failure models. Actual microphones/headphones, independent public networks, forced-provider relay and long simultaneous game/voice sessions require separate qualification. Do not treat two processes on one machine as independent networks or a passing short probe as acoustic proof. Current results belong on the implementation PR; historical browser matrices do not establish current-head support.
