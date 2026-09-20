Audience: Agent

# Optional voice

Two room members can explicitly enable microphone audio, mute either side, choose a microphone or use push-to-talk. Voice shares the existing peer connection. Permission, device and playback failures have their own recovery controls and preserve the local game and text chat.

This implements D17 / issue #21 under approved epic #2 and planning PR #3. The functional browser tests do not establish AC-16's 30-minute listening sessions, public-network reliability, echo quality or release-platform qualification. Those remain release gates in #25 and #27; the peer investigation in #53 also remains relevant.

## Ownership and behavior

`Microphone` owns capture, track transmission, cancellation and device replacement. Each capture has a generation; leaving or replacing the peer invalidates pending permission results and stops late tracks. A serialized sender operation cannot attach a previous generation's track to a new peer. Tracks start disabled, then transmit only in the current explicit open-mic or held push-to-talk state.

`VoiceSession` owns one remote audio element, device enumeration and the existing keyboard/gamepad push-to-talk bindings. It supplies media lifecycle hooks to `PeerConnection`; the host offers one audio transceiver, and the guest binds the corresponding sender before answering. No additional peer connection, signaling service, recording or transcript is introduced. `RoomClient` owns the session, and room departure, replacement and disposal close it. The same `VoiceControls` component is shown in the room and Settings.

Enable voice requests permission only after a click. Permission denial, unavailable devices and sender attachment failures allow another explicit attempt. Playback denial has a separate sound retry. Device changes replace capture but stay muted until deliberate unmute. Blur/hidden state releases push-to-talk and mutes open mic; focus return never unmutes. Leave, kick, expiry and peer replacement stop microphone tracks. Reconnecting makes voice opt-in again. Remote mute and volume affect only incoming voice, independently of the game's mute setting.

The selected gamepad reuses the controls mapping and neutral-input arming. Keyboard push-to-talk does not activate while typing or inside a dialog. An on-screen hold button supports pointer and keyboard release/cancellation. Echo cancellation and noise suppression are requested as browser capabilities, not promised as elimination of echo.

## Integration repairs and limits

The first actual Chrome–Firefox product test disconnected signaling before microphone capture. Firefox emitted an empty ICE candidate as the end-of-candidates marker; the shared schema required every candidate string to begin with `candidate:`. The [WebRTC specification](https://www.w3.org/TR/webrtc/) defines the empty string as a valid completion indication. The shared validator now accepts exactly that marker and forwards it within the existing authenticated epoch, quotas and privacy policy. The relay validator accepts this address-free indication while continuing to reject non-relay addresses and malformed strings. The recorded before/after browser evidence covers the full room and two-way audio path.

Firefox intentionally excludes loopback TURN addresses by default ([Mozilla's localhost policy change](https://bugzilla.mozilla.org/show_bug.cgi?id=1973521)). The local forced-TURN fixture therefore enables `media.peerconnection.ice.loopback` only for its Firefox relay runs. This is test-environment configuration, not a production browser instruction or public-provider qualification. Direct tests retain the default network setting.

If a browser cannot negotiate an audio transceiver at all, the UI reports the separate voice failure and leaves text/game transport available. Binding retry uses an already negotiated transceiver; it does not recreate the peer or reset emulation. Browser/platform support failures are not hidden as successful voice recovery.

## Verification and reproduction

Prepare the application with `npm ci`, `sh scripts/foundation/prepare.sh` and `npm run build`. Use Python Playwright 1.58 with its browser dependencies and Chrome installed for `--chrome`. The fixture uses browser-provided fake microphone devices, not an actual person's microphone. The tests remove Chrome's global mute flag; game output is muted in the application, and incoming voice volume is set to zero through its own UI. Positive inbound RTP packet counts and decoded audio energy prove transported/decoded audio, not human audibility or intelligibility.

Run `python scripts/voice/browser_smoke.py --chrome --pair Chrome-Firefox --output /tmp/voice.json`; use `Chrome-Chrome` or `Firefox-Firefox` for the other pairs. Add `--relay --turnserver /path/to/turnserver` for a local authenticated coturn relay. The fixture's temporary credentials, addresses and raw TURN log are not published; failure evidence contains bounded event types, numeric error codes and transport counters. No ROM, SDP, microphone samples or chat contents enter the evidence.

Focused tests cover canceled and late permission results, blur/mute/push-to-talk, device replacement/end and denial. The real application probe covers two-way decoded audio, no implicit capture, keyboard/button push-to-talk and text isolation, remote mute/volume, explicit permission/device/attachment/playback retry, preserved peer and frame progress, late canceled capture, device replacement starting muted, narrow layout and teardown. Current results and inspected paired screenshots are linked in the PR evidence. Run the complete committed-candidate gate with `timeout 60s sh scripts/preflight.sh`; CI retains its shared 30-minute deadline.

Release validation still needs actual speakers/headphones and game audio, two independent networks, direct and forced-provider relay, supported Windows/macOS browser versions, 30-minute simultaneous gameplay/voice, kick/expiry/reconnect during gameplay and the planned startup samples. The developer/operator owns those #25/#27 gates before public launch. No green local smoke substitutes for them.
