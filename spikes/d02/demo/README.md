# Playable local demo

Load your local NES ROM, play with the keyboard or a gamepad, mute/unmute game sound, and save/restore one state in this tab. ROM bytes stay in browser memory. This is the human-playable feasibility prototype, not the completed online lobby platform.

Install Python 3 and the pinned Rust toolchain once:

```sh
rustup toolchain install 1.95.0 --profile minimal --target wasm32-unknown-unknown
```

From the repository root, build and serve with one command (Ctrl-C stops it):

```sh
sh scripts/demo.sh
```

Open **http://127.0.0.1:8765/demo/**. Choose or drop the supplied `.nes` file. The game retains its own title/menu screens; press Enter to start. Arrow keys move, X is A, Z is B, Shift is Select. Sound starts enabled. Mute/Unmute controls only this game and retains your choice when changing ROMs in this tab. If browser autoplay blocks sound, press Enter or click Unmute. Leaving the window pauses gameplay and clears held keyboard input. A standard gamepad controls player 1.

The player delegates cartridge/header validation to the pinned emulator: there is no title allowlist, NROM-only gate, NES 2.0 gate, or application file-size cutoff. Region is detected by the core. Actual hardware support is bounded by that core; an unimplemented mapper or malformed file reports its error and preserves the current game. This is not proof that every NES title or peripheral works. The file picker and drop target use the same loading path.

No ROM is bundled or uploaded. Online lobbies and voice remain separate work. From Below is single-player; the platform's planned shared-P1 handoff remains separate work.

Save state is a single in-memory slot and is cleared when a new ROM loads or the tab closes. Restore resets the audio presentation queue. Local saves use the core’s full state format entirely within WASM memory; they may include cartridge bytes and are never exposed to JavaScript, exported, or sent to peers. The NROM-only ROM-free networking codec remains separate and is not used by this player. The server binds to loopback and is for local development only.

With the server running and the README's pinned Playwright environment installed, run the original-fixture browser check from `spikes/d02`:

```sh
python3 original_fixture.py fixture.local.nes
python3 demo/demo_smoke.py fixture.local.nes
```

The test opens `?muted=1`, the game’s muted-start setting. It verifies mute/unmute through a silent game-audio test output without changing computer or Chrome audio settings. Normal URLs start unmuted.

Use `--chrome` for installed Google Chrome instead of bundled Chromium. The check exercises real keyboard-to-pixel input, scheduled nonzero audio, pause, save/restore, invalid-file recovery and narrow-window layout. It writes ignored `demo-*.local.png` screenshots and `demo-smoke.local.json`. Automated audio scheduling evidence does not establish speaker quality or the final voice/game-audio experience.
