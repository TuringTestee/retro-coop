# Retro Coop

Retro Coop plays local NES games in your browser, with keyboard/gamepad controls, sound, saves and local rewind. Two players with matching fresh games can play together in public or unlisted rooms, with text chat and optional voice. Joining an ongoing game and recovering a shared timeline are still being built.

## Play the local demo

With Python 3 and Rust 1.95.0 (including the `wasm32-unknown-unknown` target) installed, run this from the repository root:

```sh
sh scripts/demo.sh
```

Then open **http://127.0.0.1:8765/demo/**. Choose your local NES `.nes` file, press Enter to start, and use the arrow keys with X/Z. Sound starts enabled for normal play; the Mute button controls only the game. No ROM is bundled or uploaded. See [setup and controls](spikes/d02/demo/README.md) for prerequisites and testing.

## Application

The React application now plays local NES files through a picker or drop target, with default keyboard/gamepad controls and no upload. See the [local-player guide](docs/implementation/d05-local-play.md) for setup, supported formats and verification. The [room coordinator](docs/implementation/d08-rooms.md) now creates anonymous public/unlisted rooms and reserves guest places. The public directory lists available rooms. Members can use text chat and [optional voice](docs/implementation/d17-voice.md). [Shared gameplay](docs/implementation/d11.md) starts matching fresh games automatically and supports a common pause and deliberate resume. [Manual saves](docs/implementation/d06-slots.md) provide three local slots and validated import/export; battery progress persists locally, and solo play has up to ten seconds of bounded rewind. Progress-preserving late join, reconnect/resynchronization and shared load/rewind remain later deliveries. Hardware qualification and public-route release testing are separate from the current representative browser evidence.

## Start working

Open this repository in your agent and ask:

> Use `project-planner` to help me define Retro Coop and its first iteration.

For an existing issue, ask for `issue-resolver` with its URL. Vaseline’s planner turns CEO direction into architecture decisions and a prioritized dependency plan in the epic. After approval and planning merge, its orchestrator organizes linked issues and coordinates agents, using GitHub Projects when accessible or issue-only tracking otherwise. There is no separate breakdown stage. Implementation PRs include local review and test evidence. Follow the merge policy recorded in the epic: this project authorizes agent merges after local review and passing required checks. Without scoped authorization, use external review and a separate merge owner.

## Shared skills

Vaseline is pinned as a submodule at `tooling/vaseline`. Relative links expose its skills without copying their text. After cloning or creating a worktree, run:

```sh
git submodule update --init --recursive
```

You need read access to the private Vaseline repository and an authenticated SSH connection to GitHub. Refresh your agent's skill discovery after initialization. If needed, ask it to read `.agents/skills/project-planner/SKILL.md` directly.

To update deliberately, fetch Vaseline, check out a reviewed commit inside `tooling/vaseline`, and submit the changed submodule pointer in a PR. Reconcile skill links if the bundled names changed. Project instructions stay in `AGENTS.md`.

## Verification

The research probe needs Git, a POSIX shell, `timeout`, Python 3, Node.js (tested with 24.13.1), and Rust 1.95.0. Prepare the pinned tools and compile once before the fast gate:

```sh
rustup toolchain install 1.95.0 --profile minimal --component rustfmt --target wasm32-unknown-unknown
cd spikes/d02
cargo +1.95.0 fetch --locked
python3 original_fixture.py fixture.local.nes
cargo +1.95.0 test --locked --release --lib --no-run
cd ../..
```

Install the pinned Node dependencies with `npm ci` at the repository root. Then run:

```sh
timeout 60s sh scripts/preflight.sh
```

Pre-flight checks committed whitespace against the merge-base with `origin/main`, plus staged and working changes. Set `PREFLIGHT_BASE_REF` for another base; shallow checkouts must fetch enough history to find that merge-base. It also checks shell/Python/Rust syntax, TypeScript contracts, coordinator lifecycle and the focused codec tests using an original generated diagnostic. CI also builds the pinned WASM artifact and runs the browser probe on that original fixture. The featured ROM is never committed or fetched by CI. See [D02 reproduction and remaining gates](docs/implementation/d02-feasibility.md). Pre-flight must finish in under one minute; presubmit CI has a 30-minute hard limit. Separate post-submit tests may run for hours.

CI currently needs no submodule checkout. Future jobs that use shared skills must authenticate with read access to Vaseline and initialize the submodule; the default repository token does not grant cross-repository access.

Peer connection privacy and local direct/relay verification are described in the [connection guide](docs/implementation/d10-peer-connectivity.md). Relay only never silently falls back to a direct connection. Shared play uses the same privacy policy and never transfers either player’s ROM file.
