# Retro Coop

The [planned minimal room journey](docs/design/minimal-room-journey.md) for [issue #169](https://github.com/TuringTestee/retro-coop/issues/169) will simplify the controls and require everyone in a room to be ready. Its later [access amendment](docs/design/room-access-and-routing.md) will replace Unlisted with Password protected and choose the connection route automatically. The Play steps below describe the current application until that work is implemented.

Retro Coop plays NES games in your browser, with keyboard/gamepad controls, sound, saves and local rewind. Public and unlisted rooms have five slots. The host assigns the game’s supported player roles or Observer, and can close empty slots. Each member runs a matching local copy; observers and new controller owners synchronize to the current game without restarting it.

## Play

Install Node.js 24.13.1, npm 11.8.0, Python 3, and Rust 1.95.0 with the `wasm32-unknown-unknown` target. From a clean checkout, run:

```sh
sh scripts/demo.sh
```

Open the URL printed by the command, normally **http://127.0.0.1:8765/**. If that port is busy, the launcher chooses the next free local port and prints its URL. Public rooms starts with empty **Super Tilt Bro** and **From Below** rooms; choose **Join as host** to claim one. To host another game, choose **Create game**, select a saved or included game or add one `.nes` file, choose Public or Unlisted and Standard or Relay only, then choose **Create room**. A custom file uploads to the room server before the room opens. Friends can use **Join** on your public room while it has an open slot, or the invitation link for an unlisted room. Each occupied member, including the host and observers, chooses **Ready** after the game and connection are prepared; then the host can choose **Start game**. Opening Public rooms ends the current room or game first. In the NES game, press Enter for its Start button, use the arrow keys to move, X for A, Z for B, and Shift for Select.

This command starts the current client and a local room coordinator, and Ctrl-C stops both. It supports testing up to five member tabs or browser windows on this computer. A friend on another network needs the deployed HTTPS application; local loopback addresses are not reachable from their computer.

The [AWS website operations guide](docs/implementation/d24-aws-eb-operations.md) has the Elastic Beanstalk release, cost guard, rollback and teardown commands. Public deployment remains separate from the local demo and is gated on reviewed source and cloud checks.

### Test a five-member room

1. In tab A, open the URL printed by `sh scripts/demo.sh` and choose **Join as host** on an empty Super Tilt Bro room. Wait for the game to load and note the room code.
2. Open four more tabs at the same URL, find the code, and choose **Join**. Each member gets one of the five stable slot rows. Player 1 and Player 2 are separate from the three observer places; From Below offers only Player 1. The host can change any slot’s role, including their own, or close an empty slot.
3. Assigned players choose **Prepare to play**, then the host chooses **Start game**. Observers choose **Observe game** once play starts. An observer joining later synchronizes to the current frame while the players continue. Focus a player’s game screen to use that player’s controls.
4. Change a player role after making progress. The room pauses at its completed frame, synchronizes the new controller owners, and continues from the same state. If synchronization fails, use **Retry role change** or **Cancel role change**; cancellation keeps the previous roles and progress. A disconnected player can be replaced by an observer.
5. Choose **Enable voice** in each tab and grant microphone permission. The explicit **Mute**/**Unmute** control applies to all listeners and stays unchanged when tabs lose focus. Open-mic conversation continues in the background; optional push-to-talk releases on focus loss. Browser or operating-system suspension can still interrupt a session.

A sixth member cannot join until a slot is free and open. To test your own NES file, choose **Create game**, then **Add NES file**, **Public**, and **Create room**. Joining members download the host-shared file or reuse a verified local cache. **Retry download** recovers a failed acquisition independently of other members. Use an invitation for an Unlisted room. Leaving a member slot preserves the room; the host leaving closes it.

## Application

The application plays included or host-shared NES files with keyboard/gamepad controls, sound, saves and local rewind. The [room coordinator](docs/implementation/d08-rooms.md) creates anonymous public or unlisted rooms; verified matching games can use shared play, text chat and [optional voice](docs/implementation/d17-voice.md). Settings → Local data shows saved game copies and lets you remove one or all. The [five-slot lobby](docs/design/five-slot-lobby.md) defines observer catch-up, reconnect recovery and progress-preserving role changes. Shared save loading and rewind remain separate delivery work. Hardware qualification and public-route release testing are separate from the current representative browser evidence.

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

After a merge, main CI plays the same game for 30 measured seconds in each of three browser pairs: Chrome–Chrome, Firefox–Firefox, and Chrome–Firefox. It checks shared frames, hashes, input, pause/resume, errors, and direct connection, then exercises forced relay. The three pairs run in parallel within a ten-minute CI deadline. The same release gate requires five-member gameplay, voice, observer and preparation-recovery checks before deployment. Add the `release-gate-proof` label to a pull request when its release gate needs proof before merge; that PR runs the same matrix within the same ten-minute deadline. Ordinary PRs keep the five-minute gate. [Post-release qualification](.github/workflows/post-release-qualification.yml) runs the longer core and 600-second network checks daily or on demand, publishes per-pair artifacts, and stays separate from the release gate; see the [verification strategy](docs/implementation/browser-nes-platform.md#verification-strategy).

CI currently needs no submodule checkout. Future jobs that use shared skills must authenticate with read access to Vaseline and initialize the submodule; the default repository token does not grant cross-repository access.

Peer connection privacy and local direct/relay verification are described in the [connection guide](docs/implementation/d10-peer-connectivity.md). Relay only never silently falls back to a direct connection. A custom room's game file is uploaded to the room server while the room is open and downloaded by its members; peer gameplay messages do not carry the file.
