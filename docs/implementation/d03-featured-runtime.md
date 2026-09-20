Audience: Agent

# From Below: selected-game runtime evidence

The exact selected From Below release starts in all three modes in the current local worker. These short checks support its single-player presentation: P1 moves the piece, while the tested P2 inputs leave the video unchanged. They complement the earlier browser and network experiments; they do not complete release qualification.

## Identity and reproduction

The creator's NES 1.0 Final download from [the game page](https://mhughson.itch.io/from-below) matches the original selected file: 40,976 bytes, SHA-256 `1a3ac4faf4b35640505344059ae5d91dae07cd47e1fb4d9d2a33c76391f1c555`. No header patch or alternate release was used. The binary stays outside Git. The [content handoff](featured-from-below.md) owns credits, presentation and included-game requirements.

Build the pinned local WASM with the [application guide](d05-local-play.md). With Python Playwright and Google Chrome installed, run from the repository root:

```sh
python3 scripts/featured/qualify.py \
  --rom /path/to/from_below_2020_09_16_v_1_0_0.nes \
  --wasm apps/client/dist/generated/retro_coop_d02.wasm \
  --output /tmp/from-below-qualification
```

The command rejects a different file before launching the browser. It serves only a small canvas harness, the existing worker and supplied WASM over loopback; ROM bytes enter the worker locally. It creates no audio output device and inspects generated PCM instead. This is not a test of the application picker, controls dialog or network room UI.

## Observed results

[Raw results](d03/result.json) record Linux Chrome 145.0.7632.75, 28.98 seconds, exact WASM identity, per-frame video timeline hashes, PCM peaks and all browser requests. No page errors or non-GET requests occurred. The runtime and worker came from merged application commit `f248296aca30c4a2f60475e4c3e062c73577dd76`; documentation-only integration `813bc898b9e376a27d4fdb2acae1fa062ca452ad` does not change them.

| Check | Observation |
|---|---|
| Boot | Title appears after 600 accelerated frames; PCM is nonzero. |
| Modes | Inspected options display TIMED, CLASSIC and FIXED, corresponding to the creator's timed Kraken, classic and turn-based Kraken descriptions. Each enters gameplay. |
| P1 | Holding Right changes the 120-frame gameplay video timeline in each mode. |
| P2 | Holding all P2 buttons produces the same tested video timeline as idle at title, each options menu and each mode's gameplay checkpoint. This is scoped evidence, not exhaustive controller proof. |
| Restore | Replaying the same 120 P1-input frames after restoring the saved checkpoint produces the same video timeline in each mode. |
| Audio | Boot and gameplay produce nonzero PCM; audible quality and bit-identical PCM after restore are not asserted. |

The author inspected all seven screenshots: [title](d03/title.png), [timed options](d03/timed-options.png), [classic options](d03/classic-options.png), [fixed options](d03/fixed-options.png), and gameplay in [timed](d03/timed-playing.png), [classic](d03/classic-playing.png) and [fixed](d03/fixed-playing.png). These are captures of the exact game rendered by the worker, not product mockups. The script records expected menu labels; visual inspection establishes that those labels actually appeared.

## Limits and remaining owners

An initial comparison combined video with PCM and failed after restore even when displayed frames matched. The pinned core deliberately preserves the running session's synthesizer and filter history (`cpu.rs::keep_session_settings` at TetaNES revision `a0a6b17`). The final probe therefore compares complete video timelines, while recording PCM separately. This does not establish complete emulator-state equivalence or deterministic presentation audio.

These accelerated checks do not verify every wall kick, T-spin, drop, lock delay or tentacle rule, real-time performance, all operating systems, rewind, network synchronization or human voice quality. Earlier selected-title Chrome/Firefox and real-time results remain linked in issue #7. D20 owns final core/browser qualification; D19 owns included download, automatic joining and recovery; D15 owns shared-P1 transfer; D21 owns the combined internet journey. Keep the selected game labelled single-player with optional shared-P1 handoff, not native two-player co-op.
