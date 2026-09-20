Audience: Agent

# D02 playable local demo

The feasibility core now has a local player: choose a ROM, use the keyboard or a gamepad, hear audio, and save or restore one state in the current tab. This gives the user a playable demonstration while D02's browser/network qualification continues. It does not complete the online platform or release D04's prerequisite.

## Scope and provenance

The demo extends the experiment integrated in [PR #33](https://github.com/TuringTestee/retro-coop/pull/33), within [issue #6](https://github.com/TuringTestee/retro-coop/issues/6) and [epic #2](https://github.com/TuringTestee/retro-coop/issues/2). The user requested a playable game and demo during the feasibility work. The governing [design](../design/browser-nes-platform.md), [implementation plan](browser-nes-platform.md), and [From Below specification](featured-from-below.md) remain in effect. The unfinished network experiments are not included in this change.

The adapter adds explicit per-frame P1/P2 button masks and RGBA output. The page runs the pinned core in a worker, copies the frame and PCM to the main thread, and schedules a bounded amount of Web Audio output. Pause, blur, mute and restore clear pending output. The page uses the existing bounded checkpoint codec for its single in-memory save slot. This is not a persistent or exportable release save format.

The demo accepts the experimental iNES NROM hardware subset, validates the header and exact size before replacing the loaded game, and retains ROM bytes only in browser memory. The selected From Below ROM is supplied locally; it is not checked into the repository, served by the development server, or sent to CI. Credits match the merged game specification. No public deployment or game redistribution is part of this PR.

The original CI diagnostic's generator was corrected to return PPUADDR to palette entry `$3F00` after writing its backdrop. With rendering disabled, the previous `$3F01` address hid the input-driven color change. A browser keyboard-to-pixel test exposed that defect. The revised original fixture is 24,592 bytes, SHA-256 `29b69405c375e2f349be89c08fef4654db99381c871ad05c16650c9da17bcb03`. Earlier PR #33 evidence continues to identify the historical fixture `d4a21ae4…`; those measurements are not relabeled as runs of this revision. Neither fixture replaces From Below.

## Verification and remaining limits

The focused native test verifies P1 A and P2 B through the original diagnostic's actual serial reads into RAM, clears both inputs, checks nonzero PCM and RGBA size/alpha, and confirms a right-arrow input changes the rendered frame. The existing six codec and memory regressions remain. Local preflight passed in 0.57 seconds with all seven tests. The demo browser smoke tests the actual file picker, keyboard-to-pixel change, sound scheduling, pause, save/restore, invalid file handling and viewport layout using the original fixture; CI publishes its measurements and screenshots. The local Chrome 145.0.7632.75 smoke passed in 2.91 seconds including process startup; [its recorded checks](d02/demo-smoke.json) include the latest-selection-wins race regression. Matched screenshots show the [empty page](d02/demo-before.png) and [loaded original diagnostic](d02/demo-after.png), not the selected game.

The selected-game local smoke exercises the real From Below title/menu, movement, sound enable and save/restore. Visual inspection shows the game rendered within the playable page. These checks do not establish audible speaker quality, physical gamepad coverage, persistence, cross-machine timing, public-network startup, voice, multiplayer input epochs or the full Windows/macOS release matrix. The browser/audio queue experiment remains an initial demonstration, not the later product audio acceptance.

See [demo setup and controls](../../spikes/d02/demo/README.md). The existing 60-second preflight and 30-minute CI deadlines remain; the short browser smoke is added to the existing CI job. Exact current-head check durations, local reviewer report and CI evidence links are published on the PR. The original combined D01/D02 five-developer-day bound and its historical accounting gap remain as recorded in [the feasibility report](d02-feasibility.md#time-budget-and-next-decision).
