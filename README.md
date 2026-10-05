# Retro Coop

Retro Coop plays NES games in your browser, with keyboard/gamepad controls, sound and saves. Public and password-protected lobbies have five slots. Create or join a lobby first, then choose a NES game while friends arrive. The host can assign Player 1 and Player 2 and close empty slots. Other visitors can watch. Only occupied controller players must be Ready before Start.

## Play

Install Node.js 24.13.1, npm 11.8.0, Python 3, and Rust 1.95.0 with the `wasm32-unknown-unknown` target. From a clean checkout, run:

```sh
sh scripts/demo.sh
```

Open the URL printed by the command, normally **http://127.0.0.1:8765/**. If that port is busy, the launcher prints another local URL. The lobby list opens first. Choose **Host a new game** to create a public lobby with a generated name, or click a lobby row to join it. The host can change the lobby name and choose **Password protected** under Settings → Lobby. Choose **Load NES game** in the lobby, then an included game or **Add game file**. Friends can join while the host chooses a game; a protected lobby asks for its password. Occupied controller players choose **Ready** once prepared, then the host chooses **Start →**. Other visitors can watch without blocking Start. **Back to Main Page** asks to close or leave the lobby and stops its game. In the NES game, use the arrow keys to move, Z for A, C for B, Alt for Select, and Space for Start. Hold A or D for rapid A or B; P pauses the emulator, Q saves, and Host Load (E) restores the compatible quick save after the controlling players agree. The in-game guide shows your current bindings if you change them. Your chosen name and automatic host progress stay in this browser. If a hosted lobby expires, host a new lobby and choose Restore game to resume saved progress with a new invitation. Manual Q saves remain separate.

This command starts the current client and a local room coordinator, and Ctrl-C stops both. It supports testing up to five member tabs or browser windows on this computer. A friend on another network needs the deployed HTTPS application; local loopback addresses are not reachable from their computer.

The first preparation also downloads Emscripten 6.0.11 and builds the pinned unmodified FCEUmm core for supported NTSC mapper-225 cartridges. Other supported games and existing saves keep using TetaNES. FCEUmm is GPL software; the build publishes its license and corresponding source instructions under `generated/fceumm-license.txt` and `generated/fceumm-source.txt`. Activate Emscripten 6.0.11 yourself to use an existing SDK installation.

The [AWS website operations guide](docs/implementation/d24-aws-eb-operations.md) has the Elastic Beanstalk release, cost guard, rollback and teardown commands. Public deployment remains separate from the local demo and is gated on reviewed source and cloud checks.

### Test a five-member lobby

1. In tab A, choose **Host a new game** from the first row of the lobby list. Choose **Copy invite** beside the lobby name to share the link. Friends can join before a NES game is selected.
2. Open the invitation in four more tabs, or click the lobby row on the list in each tab. For a protected lobby, enter its password. Five slot rows remain visible while waiting and playing; the host clicks a row to move a visitor to Player 1, Player 2, or another slot, kick a visitor, or close an empty slot.
3. The host chooses **Load NES game** and selects an included game or **Add game file**. Occupied controller players choose **Ready** when prepared. The host chooses **Start →** when they are ready; other visitors can watch and join after play begins. Focus a player's game screen to use that player's controls.
4. To change controller owners during play, the host clicks a slot row. The game pauses while the new owners prepare. If preparation fails, use **Retry player change** or **Cancel player change** in that row's menu. Cancellation preserves the previous owners and progress.

A sixth visitor cannot join until a slot is free and open. Choose a `.nes` file or a ZIP under 2 MB, or drop it onto the game area. The server extracts the first NES game in alphabetic path order; failed replacements keep the previous game. For a custom game, wait for the verified upload before asking players to get ready. A joining visitor downloads the host's game or uses a verified local copy; **Retry game** recovers a failed download. The host leaving closes the lobby; another visitor leaving preserves it. Voice controls live under Settings → Voice; Independent network play and voice checks remain part of the [release gate](https://github.com/TuringTestee/retro-coop/issues/2).
## Application

The application plays included or host-shared NES files with keyboard/gamepad controls, sound and saves. The [lobby coordinator](docs/implementation/d08-rooms.md) creates anonymous public or password-protected lobbies; verified matching games can use shared play, text chat and [optional voice](docs/implementation/d17-voice.md). Settings → Local data shows saved game copies and lets you remove one or all. The [unified lobby design](docs/design/unified-lobbies-direction.md) defines the current journey and layout. Game settings provides Save (Q) and host Load (E); shared loading waits for the controlling players to agree. Shared rewind remains deferred.

## Start working

Open this repository in your agent and ask:

> Use `project-planner` to help me define Retro Coop and its first iteration.

For an existing issue, use `issue-resolver` with its URL. Use `project-orchestrator` for project delivery and follow the repository guidance in [AGENTS.md](AGENTS.md).

## Shared skills

Vaseline is pinned as a submodule at `tooling/vaseline`. Relative links expose its skills without copying their text. After cloning or creating a worktree, run:

```sh
git submodule update --init -- tooling/vaseline
```

You need read access to the private Vaseline repository and an authenticated SSH connection to GitHub. Refresh your agent's skill discovery after initialization. The entry point is `.agents/skills/project-orchestrator/SKILL.md`.

The issue resolver records local ticket activity in SQLite. Run `node tooling/vaseline/cli/vaseline.js effort --help` for the timing commands.

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

Pre-flight checks committed whitespace against the merge-base with `origin/main`, plus staged and working changes. Set `PREFLIGHT_BASE_REF` for another base; shallow checkouts must fetch enough history to find that merge-base. It also checks shell/Python/Rust syntax, TypeScript contracts, coordinator lifecycle and the focused codec tests using an original generated diagnostic. CI also builds the pinned WASM artifact and runs the browser probe on that original fixture. The included game assets are tracked; the deployment check plays Super Tilt Bro for 30 seconds at the public URL. User-supplied games are not used by CI. See [D02 reproduction and remaining gates](docs/implementation/d02-feasibility.md). The [verification strategy](docs/implementation/browser-nes-platform.md#verification-strategy) owns the current pre-flight, pull-request, post-submit and release-test budgets.

The pull-request browser gate runs two independent Chromium processes for both Public and Password-protected host-shared games. Only the host process receives the diagnostic ROM path. Both players must advance at least 200 synchronized frames with matching state hashes. The same gate checks failed-download Retry, verified cache reuse, cross-tab Clear, storage-quota fallback, and server blob removal when a room closes.

Main CI builds the release, runs the current host-and-join journey in Chromium, and verifies the deployment images before deploying. The browser journey covers public and password-protected lobbies, loading a ROM, and synchronized play. Add the `release-gate-proof` label to a pull request to run the same gate before merge. See the [verification strategy](docs/implementation/browser-nes-platform.md#verification-strategy).

CI currently needs no submodule checkout. Future jobs that use shared skills must authenticate with read access to Vaseline and initialize the submodule; the default repository token does not grant cross-repository access.

Peer connection privacy and local direct/relay verification are described in the [connection guide](docs/implementation/d10-peer-connectivity.md). The app chooses a usable peer route automatically; direct peer connections may expose network addresses to other room members. A custom room's game file is uploaded to the room server while the room is open and downloaded by its members; peer gameplay messages do not carry the file.
