# Background voice delivery

Remove focus-driven open-microphone muting while retaining explicit mute, safe push-to-talk release, and existing microphone consent and teardown behavior.

## Governing source

[Human direction and journeys](../design/background-voice.md) govern feature [#156](https://github.com/TuringTestee/retro-coop/issues/156). This document supersedes only the conflicting blur/hidden behavior and its tests in [D17](d17-voice.md); that document continues to own device, permission, media transport and release qualification details. Review and merge this plan before implementation. Repository policy B authorizes the builder to merge only after independent acceptance and passing checks.

## Current cause and replacement

At `f125ed5`, `Microphone.blur()` calls `mute(true)` and `VoiceSession` calls it on blur and hidden state. The gamepad polling path also invokes that method when a selected gamepad disappears. These are application behavior, not evidence that the browser itself stopped capture.

`Microphone` remains the single owner of desired mute and effective track enablement. Replace focus-driven muting with a release operation that clears held push-to-talk state without altering `muted`. `VoiceSession` must clear keyboard, gamepad arming and pointer state immediately on blur/hidden. Input polling must not change open-microphone mute when controls become unavailable. Teardown still resets the microphone endpoint and cancels pending capture generations. Keep desired mute stable during pending permission, including explicit mute/cancel races.

`VoiceControls` exposes an explicit Mute/Unmute action whenever capture is ready in both modes. Compact push-to-talk must not replace the only mute action with Hold to talk. Keep the lobby control discoverable and gameplay/Settings controls consistent. Replace the obsolete “Switching windows mutes” explanation. No cross-tab shared mute storage or focus-return auto-unmute.

Search all code, tests, browser fixtures and docs for blur, hidden, focus-mute and the old voice copy. Update assertions and current instructions; retain clearly historical evidence as historical. No new transport or recording service is needed for this slice. Five-member sender fanout remains owned by #157 and must preserve this microphone rule.

## Proof and acceptance

Use `pr-create-and-review` for the implementation draft, then independent review in a separate detached checkout through `sh scripts/review-bot.sh`. Post exact candidate/base, commands, durations, observed results and inspected visuals on the PR.

- Focused microphone tests: open mic remains transmitting after blur; explicit mute stays silent; blur during pending consent honors latest mute; push-to-talk releases immediately and requires fresh input; device replacement, unavailable device, canceled/late permission and teardown retain their safety behavior.
- Real public-entrypoint browser journey: join two tabs in one browser and two independent browser processes, enable fake-device audio by actual controls, change real tab/window focus, and observe increasing received RTP audio energy while backgrounded. Do not substitute synthetic blur events for the primary focus journey. Verify explicit mute stops energy after buffered media drains and unmute restores it. Fake microphones establish transport/decoding, not acoustic quality.
- Exercise permission denial/retry, typing isolation, push-to-talk release, lobby/gameplay mute discovery, and leave stopping capture. Inspect screenshots of lobby, gameplay and denied-permission recovery; assert continued shared game progress where applicable.
- Run the README `timeout 60s sh scripts/preflight.sh`, required PR CI within its five-minute budget, and relevant existing voice/browser checks. Follow [verification strategy](browser-nes-platform.md#verification-strategy), including existing direct/relay regressions and separately owned release qualification. Physical devices on separate machines/networks remain a separately reported qualification obligation; do not describe independent processes as independent machines.

Browser limits: the [media capture specification](https://www.w3.org/TR/mediacapture-streams/) distinguishes application-controlled track enablement from source muting outside application control. [Chrome page lifecycle documentation](https://developer.chrome.com/docs/web-platform/page-lifecycle-api) distinguishes hidden from frozen/discarded pages. The implementation removes app-induced focus muting; it cannot override OS sleep or browser termination.

## Delivery and integration

One feature PR completes the background-voice journey independently of #157/#158. Merge this governing plan first; then implement, prove, independently review and merge the feature. Confirm the merged revision and required main integration results before closing #156. The five-slot work must rerun the voice journey across all members when its transport changes. The deterministic-layout work must preserve this visible mute control across loading and errors.
