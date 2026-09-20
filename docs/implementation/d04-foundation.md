Audience: Agent

# Application foundation

Retro Coop now has a React browser client and a small Node coordinator. The client runs the existing emulator in a worker using an original diagnostic cartridge; the coordinator reports health and shuts down cleanly. This is the D04 foundation, not completed local-play or room functionality.

## Setup and commands

Use Node **24.13.1**, npm **11.8.0**, and the Rust **1.95.0** toolchain with `wasm32-unknown-unknown` from the README. Each worktree owns its build outputs. From the repository root:

```sh
npm ci
sh scripts/foundation/prepare.sh
npm run dev
```

Open the URL printed by Vite (normally `http://127.0.0.1:5173`). Click **Run diagnostic**, then focus the screen and press an arrow key. The original diagnostic changes its backdrop when it receives controller input. It produces PCM audio, muted through the game's own gain setting by default; **Unmute** enables audible output. Pause stops frame requests and flushes queued audio. Restarting replaces the worker and audio context. Background tabs pause automatically.

In another terminal, `npm run coordinator` starts the health-only service on loopback port 8787. `curl http://127.0.0.1:8787/health` returns a content-free JSON response. Other routes, including rooms, return 404. SIGINT/SIGTERM stop accepting connections and close outstanding connections within two seconds.

`npm run build` creates a static bundle in `apps/client/dist`; `npm run build:staging` uses staging settings. `npm run preview -w @retro-coop/client` serves that built bundle locally. Builds fail clearly if the prepared WASM/diagnostic assets are absent. The preparation command reuses the pinned Cargo lock and general local-player ABI accepted in PR #40. It does not fetch a third-party game.

## Boundaries and reuse

- `apps/client`: React/Vite shell, dedicated worker adapter and browser lifecycle. No production ROM picker, save UI or room controls (D05/D06/D08 remain separate).
- `apps/coordinator`: Node's maintained built-in HTTP server, validated process configuration, health and bounded shutdown. No emulator, user-ROM endpoint or persistent state.
- `packages/contracts`: explicit local worker request/response and health types. Requests validate controller bytes and nonempty buffers at runtime. ROM buffers transfer only to the browser worker. Future room/signaling contracts belong to D08.
- `spikes/d02/demo/runtime`: extracted existing keyboard/gamepad mapping and bounded 48 kHz PCM scheduler. Both the accepted demo and new client import these modules; the existing demo remains runnable without npm tooling. This retains one owner for those proven rules.
- Worker calls only `local_*` exports of the existing Rust/TetaNES core. It never sends general cartridges through the narrow peer-checkpoint codec. Worker memory and core instances are discarded on restart; D05 owns production loading policies.

Only `PUBLIC_` variables are visible to Vite. The public coordinator endpoint is `http://127.0.0.1:8787` in development, and `/coordinator` in staging/default builds. Staging expects a same-origin reverse proxy; no provider is selected or provisioned. Server-only `COORDINATOR_STAGE` (`local`/`staging`), `COORDINATOR_HOST`, and `COORDINATOR_PORT` are read only by the Node entry point. No secrets or server configuration are imported by the browser. `.env.local` and mode-specific local overrides are ignored. Never place secrets in `PUBLIC_` variables.

The client currently displays no service health badge and makes no coordinator request. This keeps the foundation useful offline while the public endpoint contract is ready for D08. Node's native HTTP implementation avoids an unused HTTP framework; WebSocket lifecycle and its maintained library will arrive with that feature.

## Pins and verification

Direct dependencies use exact versions and the committed npm lockfile: React/React DOM 19.3.0, Vite 8.3.0, React Vite plugin 6.1.1, TypeScript 7.0.2, and matching React types. Versions were checked against the npm registry and official [React release](https://react.dev/blog/2026/09/09/react-19-3) and [Vite documentation](https://vite.dev/guide/). Node is fixed by `.node-version`, package engines and strict npm engine checking; CI installs that same version. The existing emulator pin is unchanged.

Fast checks: `npm run typecheck`, `npm test`, and the complete README `timeout 60s sh scripts/preflight.sh` after preparing native Rust tests as documented there. Node tests exercise actual HTTP requests and SIGTERM in a child process, plus malformed worker requests.

Real browser check, after preparing assets/building and installing the repository's pinned Playwright 1.58.0 and Chromium:

```sh
python3 scripts/foundation/browser_smoke.py --output /tmp/foundation.local.json
```

Use `--chrome` to check installed Chrome instead of bundled Chromium. This check observes changed canvas pixels from controller input, real nonzero PCM buffers scheduled through a muted game gain, stable pause output, mobile overflow, browser errors and network requests. It captures matched empty/running screenshots and a mobile view. It never changes system/browser-global audio settings. The demo's existing browser smoke separately verifies extraction compatibility.

CI builds the application alongside the emulator, transfers the immutable client artifact to the core job, runs the browser smoke there, and retains its raw JSON/screenshots. All jobs remain under the existing shared 30-minute deadline/watchdog. The root preflight includes TypeScript and service/contract checks and retains its 60-second hard timeout. No long new post-submit workload is introduced by D04.
