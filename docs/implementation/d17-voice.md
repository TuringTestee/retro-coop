Audience: Agent

# Optional voice

Two room members can explicitly enable microphone audio, mute either side, choose a microphone or use push-to-talk. Voice shares the existing peer connection. Permission, device and playback failures have their own recovery controls and preserve the local game and text chat.

This implements D17 / issue #21 under approved epic #2 and planning PR #3. The functional browser tests do not establish AC-16's 30-minute listening sessions, public-network reliability, echo quality or release-platform qualification. Those remain release gates in #25 and #27; the peer investigation in #53 also remains relevant.

## Ownership and behavior

`Microphone` owns capture, track transmission, cancellation and device replacement. Each capture has a generation; leaving or replacing the peer invalidates pending permission results and stops late tracks. A serialized sender operation cannot attach a previous generation's track to a new peer. Tracks start disabled, then transmit only in the current explicit open-mic or held push-to-talk state.

`VoiceSession` owns one remote audio element, device enumeration and the existing keyboard/gamepad push-to-talk bindings. It supplies media lifecycle hooks to `PeerConnection`; the host offers one audio transceiver, and the guest binds the corresponding sender before answering. No additional peer connection, signaling service, recording or transcript is introduced. `RoomClient` owns the session, and room departure, replacement and disposal close it. The same `VoiceControls` component is shown in the room and Settings.

Enable voice requests permission only after a click. Permission denial, unavailable devices and sender attachment failures allow another explicit attempt. Playback denial has a separate sound retry. Device changes replace capture but stay muted until deliberate unmute. Blur/hidden state releases push-to-talk and mutes open mic; focus return never unmutes. Leave, kick, expiry and peer replacement stop microphone tracks. Reconnecting makes voice opt-in again. Remote mute and volume affect only incoming voice, independently of the game's mute setting.

A removed microphone keeps an explicit unavailable option in the device selector. The browser removal model originally reproduced a misleading Default selection while the previous device ID remained active; the corrected selector lets Default become a real new choice, followed by explicit capture retry. This models device removal and does not claim a physical unplug test.

A reconnect regression initially reproduced a retained held key after peer replacement. Closing the voice session now clears keyboard, pointer and gamepad arming state before a new opt-in; the browser test proves old held input cannot transmit after rejoin, then verifies a fresh press works.

The selected gamepad reuses the controls mapping and neutral-input arming. Keyboard push-to-talk does not activate while typing or inside a dialog. An on-screen hold button supports pointer and keyboard release/cancellation. Echo cancellation and noise suppression are requested as browser capabilities, not promised as elimination of echo.

## Integration repairs and limits

The first actual Chrome–Firefox product test disconnected signaling before microphone capture. Firefox emitted an empty ICE candidate as the end-of-candidates marker; the shared schema required every candidate string to begin with `candidate:`. The [WebRTC specification](https://www.w3.org/TR/webrtc/) defines the empty string as a valid completion indication. The shared validator now accepts exactly that marker and forwards it within the existing authenticated epoch, quotas and privacy policy. The relay validator accepts this address-free indication while continuing to reject non-relay addresses and malformed strings. The recorded before/after browser evidence covers the full room and two-way audio path.

A second real relay test connected successfully but mislabeled Firefox’s selected relay as direct: Firefox exposes the selected pair on its candidate-pair report rather than a transport report. One route classifier now supports both report forms and leaves an unknown route unset instead of inventing a direct route. Focused schema/route tests and the actual mixed-browser relay test cover both repairs.

Firefox intentionally excludes loopback TURN addresses by default ([Mozilla's localhost policy change](https://bugzilla.mozilla.org/show_bug.cgi?id=1973521)). The local forced-TURN fixture therefore enables `media.peerconnection.ice.loopback` only for its Firefox relay runs. This is test-environment configuration, not a production browser instruction or public-provider qualification. Direct tests retain the default network setting.

If a browser cannot negotiate an audio transceiver at all, the UI reports the separate voice failure and leaves text/game transport available. Binding retry uses an already negotiated transceiver; it does not recreate the peer or reset emulation. Browser/platform support failures are not hidden as successful voice recovery.

## Verification and reproduction

Prepare the application with `npm ci`, `sh scripts/foundation/prepare.sh` and `npm run build`. Use Python Playwright 1.58 with its browser dependencies and Chrome installed for `--chrome`. The fixture uses browser-provided fake microphone devices, not an actual person's microphone. The tests remove Chrome's global mute flag; game output is muted in the application, and incoming voice volume is set to zero through its own UI. Positive inbound RTP packet counts and decoded audio energy prove transported/decoded audio, not human audibility or intelligibility.

Run `python scripts/voice/browser_smoke.py --chrome --pair Chrome-Firefox --output /tmp/voice.json`; use `Chrome-Chrome` or `Firefox-Firefox` for the other pairs. Add `--relay --turnserver /path/to/turnserver` for a local authenticated coturn relay. The fixture's temporary TURN credentials, candidate addresses and raw TURN log are not published; failure evidence contains bounded event types, numeric error codes and transport counters. No ROM, SDP, microphone samples or chat contents enter the evidence.

CI uses Playwright’s full Chromium `channel="chromium"` headless mode, as described in its [browser guide](https://playwright.dev/python/docs/browsers#chromium-new-headless-mode). The first CI voice cell failed because the separate default headless shell returned `NotSupportedError` for the same fake-device microphone request that succeeds in full Chromium and Chrome. This changes the test browser executable, not the voice workload or application behavior.

Chromium runs use fake microphone hardware with browser permission overrides, without the fake permission UI flag. They explicitly clear the prior grant, verify the browser reports denied, observe the application’s denial message, then grant microphone permission and retry. Firefox uses its fake-device permission configuration; its error cases are injected and are not claimed as a native permission-policy test. Firefox also ignores an untrusted synthetic `ended` event in the tested build, so the removal model invokes the installed production callback and refreshes devices through the UI. No production event handler is replaced.

Focused tests cover canceled and late permission results, blur/mute/push-to-talk, device replacement/end and denial. The real application probe covers two-way decoded audio, no implicit capture, keyboard/button push-to-talk and text isolation, remote mute/volume, explicit permission/device/attachment/playback retry, preserved peer and frame progress, late canceled capture, device replacement starting muted, narrow layout and teardown. Current results and inspected paired screenshots are linked in the PR evidence. Run the complete committed-candidate gate with `timeout 60s sh scripts/preflight.sh`; CI retains its shared 30-minute deadline.

Release validation still needs actual speakers/headphones and game audio, two independent networks, direct and forced-provider relay, supported Windows/macOS browser versions, 30-minute simultaneous gameplay/voice, kick/expiry/reconnect during gameplay and the planned startup samples. The developer/operator owns those #25/#27 gates before public launch. No green local smoke substitutes for them.

## Current author evidence

The [candidate manifest](evidence/d17/candidate.json) pins source/base, proof provenance and retained failures. These are author results, not independent acceptance. All six short voice cells passed, including explicit rejoin and fresh push-to-talk input:

| Browser pair | Direct | Local relay |
|---|---|---|
| Chrome–Chrome | [3.74s](evidence/d17/voice-Chrome-Chrome-direct.json) | [4.07s](evidence/d17/voice-Chrome-Chrome-relay.json) |
| Chrome–Firefox | [10.20s](evidence/d17/voice-Chrome-Firefox-direct.json) | [12.15s](evidence/d17/voice-Chrome-Firefox-relay.json) |
| Firefox–Firefox | [9.30s](evidence/d17/voice-Firefox-Firefox-direct.json) | [8.28s](evidence/d17/voice-Firefox-Firefox-relay.json) |

The complete [foundation/settings/save probe](evidence/d17/foundation.json) passed in 21.34s. The [peer probe with the merged ordered handshake](evidence/d17/peer-ordered.json) passed in 68.17s, including real 15/20-second timeout recovery; [chat](evidence/d17/chat.json) passed in 21.19s. The manifest identifies the precise source of these integration checks; current-head CI runs them again.

Inspected matched [before](evidence/d17/before.desktop.png) / [after](evidence/d17/after.desktop.png), [narrow layout](evidence/d17/after.mobile.png), and [Settings voice controls](evidence/d17/after.settings-voice.png) show the actual application. The dialog remains scrollable, labels and buttons remain readable, and the room uses the existing visual style. The screenshot reproduction script is included beside the images.
