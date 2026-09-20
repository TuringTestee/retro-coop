Audience: Agent

# Measured local rewind

Solo players can rewind up to ten seconds of available game time, confirm replacing progress, and resume from the selected frame. The history reuses validated local saves and stays in memory; no ROM or rewind history is persisted or sent to another player. This bounded D06 slice qualifies representative local cases, not every cartridge or shared-game restore.

## Time and restoration

`rewind.rs::History` owns recorded history. After each successfully emulated local frame, the worker calls `local_rewind_record` with the controller bytes that produced that frame. The native owner subtracts the prior `cpu.cycle` with u32 wrapping arithmetic and accumulates elapsed cycles. It divides by the loaded deck's actual regional `clock_rate`, never by `local_fps()` or a fixed 600-frame count. The first committed frame is history's origin; partial startup time is not fabricated as retained history.

Approximately once per emulated second, History stores a checkpoint through the existing `local_state::Codec`. It keeps an anchor at or before the ten-second horizon and packed controller inputs for the intervening frames. A request chooses the latest recorded frame no later than the requested time. Thus a ten-second rewind moves back at least ten actual emulated seconds, with at most one frame of extra movement. The reply reports that exact history-relative frame and cycle total.

Restoration uses the same validated codec and the same `local_player::clock_inputs` frame/input routine as normal local play. It restores the nearest earlier checkpoint and replays recorded inputs to the exact target. Checkpoint pixels cover the endpoint case where no replay frame is needed; otherwise the target's actual rendered pixels are returned. Later checkpoints and inputs are dropped after success, so a new timeline cannot silently reuse its discarded future. A validated current-state backup protects against restore/replay failure. Invalid or unavailable durations fail as correlated nonfatal operations before changing the timeline.

Successful state or battery import clears history in the native owner, including direct ABI callers. ROM replacement starts with a new player and no history. Validation-only, save/export, local controls, volume and display changes do not reset history. The existing audio limitation remains: restore starts a new filter/synthesis epoch, so arbitrary bit-exact PCM continuity is not promised. Replay discards intermediate audio; the player flushes queued presentation audio and waits for explicit Resume. Browser evidence separately observes finite, nonzero PCM after resuming.

## Allocation accounting and bounds

The Rust format still owns the state-file cap. History holds at most twelve sparse checkpoints and a pre-reserved queue for 4,096 packed input records. The queue capacity is a safety bound, not the duration calculation. Supported regional traces need roughly 500–602 intervals for ten seconds; the actual recorded cycles decide availability.

`retained_bytes` measures the actual Vec capacities for checkpoint bytes and pixels, deque backing capacities for checkpoint/input records, and the History structure. `peakBytes` also accounts for the current validated backup and returned target pixels during rewind. This is implemented allocation accounting, not a multiplication of one wire-size sample by 602. A native test allocates the maximum checkpoint count at the shared file cap and includes restore scratch; changing a shared limit cannot silently invalidate the budget. Recording budget/timing failures clear this history and report a local rewind error without excluding the ROM from play.

The 32 MiB bound describes the retained history and accounted restore buffers. The emulator, immutable cartridge memory, shared validated-codec template, JavaScript runtime and allocator bookkeeping are separate baseline costs; this is not a claim that the whole worker RSS is below 32 MiB. The current shared codec's temporary serialization work is also not represented as retained history. Representative observed history and peak figures are published with native/WASM evidence. The earlier 96,616-byte full-snapshot ×602 result (58,162,832 bytes /55.47 MiB) remains the reason for sparse checkpoints and replay.

## Worker and UI ownership

`state-history` and `state-rewind` use the existing correlated local-file request path, including request/worker ownership, cancellation and nonfatal errors. No second scheduler or state decoder is added. `RewindInfo` is the shared typed response; native values own duration and memory limits. The worker's local-frame response carries current availability. Unsupported save profiles report their existing limitation while ordinary local ROM admission remains unchanged.

The local panel pauses play before reading history, shows the available duration, disables impossible choices, and confirms replacement of progress. Cancel leaves the timeline unchanged and paused. Success immediately presents the restored frame and discards future history; Close and explicit Resume return to play. Escape cancels confirmation before closing the dialog, with focus restored to the initiating control. Technical allocation details stay in developer evidence, not the player's decision flow.

D11's shared frame owner remains separate from local history recording: tagged shared frames must clear/skip local history, and shared-mode guards must reject local rewind just as they reject local load. A successful rewind must keep the worker non-pristine. These integration hooks are coordinated with the D11 owner; this slice does not implement the later two-player consent/epoch barrier.

## Qualification and remaining scope

Native checks measure mapper 0/1/4 in NTSC, PAL and Dendy with changed bank mappings, partial MMC1 serial state, enabled MMC3 IRQ state and RAM mutation. They run beyond twelve actual emulated seconds, rewind ten seconds to an independently traced target, compare canonical state and pixels, and replay the original inputs to the original state. A separate test crosses CPU u32 wrap and checks short/invalid targets and the zero-replay pixel endpoint. The original mapper-validation regressions remain; their fixture register helpers are shared through `test_support` rather than duplicated.

Actual-worker checks execute CPU stores that switch MMC1 PRG banks, leave a partial mirrored CHR-register write, and mutate battery RAM in NES 2.0 NTSC/PAL/Dendy fixtures. Exported CPU counters independently confirm elapsed time. These are original diagnostic fixtures, not a claim of commercial-game qualification. Remaining mapper/region combinations, peripherals, title-specific behavior and broad launch qualification remain explicit unfinished D06/D20 work. No new ROM allowlist or scope reduction is introduced.

This implements the local part of U5/S12 and AC-07 in [issue #10](https://github.com/TuringTestee/retro-coop/issues/10), following [the approved UI](../design/browser-nes-ui.md#u5--shared-rewind-load-and-restart) and [architecture](browser-nes-platform.md). The governing plan was approved at `2e8adfcd3259f5bdffdc9a13ef9b983f78cfb965` and merged through PR #3 (`ecf6bd4c7443526f0a163b721a351c854ee90fd4`). Prerequisites #47/#49/#52/#55 are integrated; this work starts from `2f58a1e915d3849c5732677bc77e9b52a8f41f7b` and integrates voice main `aea276ffe52ec10599aa79934658949ed657f01d` before handoff. Root owns merge after fresh independent acceptance and current checks. D06 is not automatically closed by this bounded PR.

## Reproduction

Use the README preparation, then `timeout 60s sh scripts/preflight.sh`. Run `sh scripts/foundation/prepare.sh`, `npm run build` and `python3 scripts/foundation/browser_smoke.py --chrome --output /tmp/foundation.local.json` for actual WASM/browser proof. Existing CI's `foundation.local.*.png` pattern retains the rewind screenshots. No job/deadline increase is introduced. Native qualification lives in the normal library suite; browser proof remains outside the one-minute local preflight. Audio tests use only application gain mute.
