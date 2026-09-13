# Playable local demo

Load your local From Below ROM, play with the keyboard or a gamepad, mute/unmute game sound, and save/restore one state in this tab. ROM bytes stay in browser memory. This is the human-playable feasibility prototype, not the completed online lobby platform.

Install Python 3 and the pinned Rust toolchain once:

```sh
rustup toolchain install 1.95.0 --profile minimal --target wasm32-unknown-unknown
```

From the repository root, build and serve with one command (Ctrl-C stops it):

```sh
sh scripts/demo.sh
```

Open **http://127.0.0.1:8765/demo/**. Choose or drop the supplied `.nes` file. The game retains its own title/menu screens; press Enter to start. Arrow keys move, X is A, Z is B, Shift is Select. Sound starts enabled. Mute/Unmute controls only this game and retains your choice when changing ROMs in this tab. If browser autoplay blocks sound, press Enter or click Unmute. Leaving the window pauses gameplay and clears held keyboard input. A standard gamepad controls player 1.

The prototype admits iNES mapper-0/NROM files with 16/32 KiB PRG and at most 8 KiB CHR; it does not claim all NES support. Invalid files show an error before replacing the loaded game. No included ROM, external asset download, account, lobby, voice, persistence, or multiplayer capability is implied by this demo. From Below is single-player; the platform's planned shared-P1 handoff remains separate work.

Save state is a single in-memory slot and is cleared when a new ROM loads or the tab closes. Restore resets the audio presentation queue. This demo uses the experimental codec and is not the release save format. The server binds to loopback and is for local development only.

With the server running and the README's pinned Playwright environment installed, run the original-fixture browser check from `spikes/d02`:

```sh
python3 original_fixture.py fixture.local.nes
python3 demo/demo_smoke.py fixture.local.nes
```

The test opens `?muted=1`, the game’s muted-start setting. It verifies mute/unmute through a silent game-audio test output without changing computer or Chrome audio settings. Normal URLs start unmuted.

Use `--chrome` for installed Google Chrome instead of bundled Chromium. The check exercises real keyboard-to-pixel input, scheduled nonzero audio, pause, save/restore, invalid-file recovery and narrow-window layout. It writes ignored `demo-*.local.png` screenshots and `demo-smoke.local.json`. Automated audio scheduling evidence does not establish speaker quality or the final voice/game-audio experience.
