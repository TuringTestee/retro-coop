# Retro Coop

Retro Coop is a browser-local NES multiplayer project in feasibility testing. A playable local demo now runs your ROM with keyboard/gamepad input, sound and a save slot. Online rooms remain in development.

## Play the local demo

With Python 3 and Rust 1.95.0 (including the `wasm32-unknown-unknown` target) installed, run this from the repository root:

```sh
sh scripts/demo.sh
```

Then open **http://127.0.0.1:8765/demo/**. Choose your local NES `.nes` file, press Enter to start, and use the arrow keys with X/Z. Sound starts enabled for normal play; the Mute button controls only the game. No ROM is bundled or uploaded. See [setup and controls](spikes/d02/demo/README.md) for prerequisites and testing.

## Application

The React application now plays local NES files through a picker or drop target, with default keyboard/gamepad controls and no upload. See the [local-player guide](docs/implementation/d05-local-play.md) for setup, supported formats and verification. The Node coordinator currently provides only a health endpoint; online rooms remain in development.

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

Pre-flight checks whitespace, shell/Python/Rust syntax, TypeScript contracts, coordinator lifecycle and the focused codec tests using an original generated diagnostic. CI also builds the pinned WASM artifact and runs the browser probe on that original fixture. The featured ROM is never committed or fetched by CI. See [D02 reproduction and remaining gates](docs/implementation/d02-feasibility.md). Pre-flight must finish in under one minute; presubmit CI has a 30-minute hard limit. Separate post-submit tests may run for hours.

CI currently needs no submodule checkout. Future jobs that use shared skills must authenticate with read access to Vaseline and initialize the submodule; the default repository token does not grant cross-repository access.
