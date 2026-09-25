# Retro Coop

Retro Coop plays NES games in your browser, with keyboard/gamepad controls, sound, saves and local rewind. A host can share one game with a guest in a public or unlisted room; the guest downloads it automatically. Joining an ongoing game and recovering a shared timeline are still being built.

## Play

Install Node.js 24.13.1, npm 11.8.0, Python 3, and Rust 1.95.0 with the `wasm32-unknown-unknown` target. From a clean checkout, run:

```sh
sh scripts/demo.sh
```

Open the URL printed by the command, normally **http://127.0.0.1:8765/**. If that port is busy, the launcher chooses the next free local port and prints its URL. Public rooms starts with empty **Super Tilt Bro** and **From Below** rooms; choose **Join as host** to claim one. To host another game, choose **Create game**, select a saved or included game or add one `.nes` file, choose Public or Unlisted and Standard or Relay only, then choose **Create room**. A custom file uploads to the room server before the room opens. A friend can use **Join** on your public 1/2 row or the invitation link for an unlisted room. The host can **Start game** alone or with a prepared guest. In the NES game, press Enter for its Start button, use the arrow keys to move, X for A, Z for B, and Shift for Select.

This command starts the current client and a local room coordinator, and Ctrl-C stops both. It supports testing two browser windows on this computer. A friend on another network needs the deployed HTTPS application; local loopback addresses are not reachable from their computer.

The [AWS website operations guide](docs/implementation/d24-aws-eb-operations.md) has the Elastic Beanstalk release, cost guard, rollback and teardown commands. Public deployment remains separate from the local demo and is gated on reviewed source and cloud checks.

### Test with two browser tabs

1. In tab A, open the URL printed by `sh scripts/demo.sh` and choose **Join as host** on an empty Super Tilt Bro room. Wait for the game to load. Note the room code beside its name.
2. In a new tab B, open the same URL, search for that code, and choose **Join** on the **1/2 · Waiting for guest** row. Wait for the included game to load, then choose **Prepare to play**. Before this click, tab A should say the guest is still preparing; afterward, it should say the guest is ready.
3. In tab A, choose **Start game**. Both tabs should show **Playing together** and increasing shared-frame counts. Focus each game screen and press Enter to start the NES game; tab A controls Player 1 and tab B controls Player 2.
4. Switch between the tabs while the game runs. The room should stay in **Playing together** and frame counts should keep increasing. Switching tabs releases held buttons, so press a movement or action key again after returning.

To test your own NES file, choose **Create game** in tab A, use **Add NES file**, choose **Public**, then **Create room**. In tab B, search its room code, check the host-shared download size, and choose **Join**. The game downloads or loads from this browser's verified cache. Choose **Prepare to play** once it loads and the peer connects. Use **Cancel preparation** to leave during acquisition or **Retry download** after a failure. For an **Unlisted** room, open the host's invitation link instead of searching. If a room has already started or its guest place is full, leave it and create a new room before repeating the steps.

## Application

The application plays included or host-shared NES files with keyboard/gamepad controls, sound, saves and local rewind. The [room coordinator](docs/implementation/d08-rooms.md) creates anonymous public or unlisted rooms; verified matching games can use shared play, text chat and [optional voice](docs/implementation/d17-voice.md). Settings → Local data shows saved game copies and lets you remove one or all. Progress-preserving late join, reconnect/resynchronization and shared load/rewind remain later deliveries. Hardware qualification and public-route release testing are separate from the current representative browser evidence.

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

Pre-flight checks committed whitespace against the merge-base with `origin/main`, plus staged and working changes. Set `PREFLIGHT_BASE_REF` for another base; shallow checkouts must fetch enough history to find that merge-base. It also checks shell/Python/Rust syntax, TypeScript contracts, coordinator lifecycle and the focused codec tests using an original generated diagnostic. CI also builds the pinned WASM artifact and runs the browser probe on that original fixture. The featured ROM is never committed or fetched by CI. See [D02 reproduction and remaining gates](docs/implementation/d02-feasibility.md). The [verification strategy](docs/implementation/browser-nes-platform.md#verification-strategy) owns the current pre-flight, pull-request, post-submit and release-test budgets.

The pull-request browser gate runs two independent Chromium processes for both Public and Unlisted host-shared games. Only the host process receives the diagnostic ROM path. Both players must advance at least 200 synchronized frames with matching state hashes. The same gate checks failed-download Retry, verified cache reuse, cross-tab Clear, storage-quota fallback, and server blob removal when a room closes.

After a merge, main CI plays the same game for 30 measured seconds in each of three browser pairs: Chrome–Chrome, Firefox–Firefox, and Chrome–Firefox. It checks shared frames, hashes, input, pause/resume, errors, and direct connection, then exercises forced relay. The three pairs run in parallel within a ten-minute CI deadline. The longer core and network qualification is kept for the separate post-release workflow; see the [verification strategy](docs/implementation/browser-nes-platform.md#verification-strategy).

CI currently needs no submodule checkout. Future jobs that use shared skills must authenticate with read access to Vaseline and initialize the submodule; the default repository token does not grant cross-repository access.

Peer connection privacy and local direct/relay verification are described in the [connection guide](docs/implementation/d10-peer-connectivity.md). Relay only never silently falls back to a direct connection. A custom room's game file is uploaded to the room server while the room is open and downloaded by its guest; peer gameplay messages do not carry the file.
