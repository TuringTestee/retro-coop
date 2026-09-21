Audience: Agent

# Local controls and presentation

Players can now choose and remap a keyboard or gamepad, test the controls, and change the picture, volume and fullscreen display. These settings affect only this tab and preserve the active game. Unplugging the selected controller pauses play and offers keyboard fallback.

## Player behavior

Open **Settings** from the player. Keyboard is the initial input device; press a gamepad button if the browser has not exposed it yet, then select that controller. Each of the eight NES buttons has a mapping. Gamepads accept buttons and signed axis directions. The reserved push-to-talk mapping participates in conflicts, but no microphone/voice behavior is implemented by D07.

**Change** captures one input and presents an explicit **Apply mapping** or **Cancel mapping** action. A binding already assigned to another button or the reserved talk action cannot apply. Release it and press a different input to replace a conflict in the same capture dialog. Keyboard shortcuts with Ctrl/Alt/Meta are excluded from capture; Tab and Escape remain navigation/cancel keys. Restoring defaults asks for confirmation and replaces only the currently edited keyboard or gamepad mapping set. The input-test area reports mapped NES buttons without injecting them into the game.

Only the selected input device controls the focused game screen. Moving focus to settings or another control releases input. Window blur/background pauses the existing game. A selected controller's disappearance pauses and explains the problem; reconnection never resumes automatically. Loading a first or replacement cartridge while that device remains absent initializes it paused at zero frames. Resume checks the current device, not a previously displayed error. **Use keyboard** changes device, then **Resume** continues existing progress. No mapping or presentation operation reloads a cartridge, recreates a worker, or resets its timeline.

The picture is nearest-neighbor by default. Scanlines add an overlay only on the game screen. Volume uses the game's existing gain node and respects mute; the settings show the audio activation state and existing retry action. Fullscreen includes an exit control and Esc guidance; denial keeps ordinary play usable. Settings use a native modal dialog with keyboard navigation, Escape cancellation, restored trigger focus and visible focus outlines. The frame counter is passive rather than an implicit live status announcing every frame. Preferences currently last for the tab; cross-tab persistence is not part of D07.

## Ownership and integration

`spikes/d02/demo/runtime/input.js` owns the original keyboard and gamepad default mapping consumed by the current application. `apps/client/src/controls.ts` owns action names, reserved talk binding, conflict checks and input interpretation. `Settings.tsx` owns capture/confirmation/presentation UI. `LocalPlayer` still owns the single active emulator and its resources, now exposing `configureControls`, `useKeyboard` and `setVolume`. The existing load/pause/resume interface is unchanged for later room integration.

The display filter is CSS; it does not alter emulator output or local fingerprints. The future voice implementation must consume the reserved talk mapping rather than maintain a competing key. Current tests emulate browser gamepad readings to exercise actual UI/player behavior; this is not a physical-controller qualification matrix.

## Verification

Run the README preparation and `timeout 60s sh scripts/preflight.sh`. Focused Node tests cover every NES mask, reserved conflicts, default isolation and shared demo gamepad defaults. Then build with `npm run build` and run:

```sh
python3 scripts/foundation/browser_smoke.py --chrome --output /tmp/foundation.local.json
```

Omit `--chrome` for the existing pinned Playwright Chromium installation used in CI. The smoke retains D05's full file-to-play workload and invokes `settings_smoke.py`: real keyboard/pad remaps change emulator pixels, axis capture works, conflicts block apply, cancellation/defaults restore focus, unplug/reconnect/fallback preserve pause, settings retain exactly one worker, and fullscreen success/denial/exit work. It verifies volume at zero while unmuted without changing system/browser audio settings; the game remains muted for all other checks. Existing audio-denial/retry verification remains included.

Screenshots use `foundation.local.settings-before.png`, `foundation.local.settings-after.png` and `foundation.local.settings-mobile.png`, covered by the existing core artifact's `foundation.local.*.png` upload. Current test scheduling and budgets follow the governing [verification strategy](browser-nes-platform.md#verification-strategy); this delivery introduced no separate long suite.

Source authority: D07 / issue #11, approved planning PR #3 at `ecf6bd4c7443526f0a163b721a351c854ee90fd4`, governing UI U4/U7 and S18/S19/S30/S31. D05 prerequisite integrated at `f248296aca30c4a2f60475e4c3e062c73577dd76`. D07 does not implement voice, online room/controller ownership, saved-game management, or a release-wide accessibility/hardware certification.
