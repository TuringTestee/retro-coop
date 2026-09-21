# The documented play command now opens the lobby-first app

Running `sh scripts/demo.sh` opens the same current application at `/` and the former `/demo/` URL. The screen puts Super Tilt Bro first, From Below second, arbitrary NES hosting beside them, and the public lobby directory below them.

## Visual evidence

- [`main-menu.png`](main-menu.png) shows the root URL at 1280×800 after the coordinator connected. Both included games have direct Play and Show lobbies actions, arbitrary-file hosting is visible, and the lobby directory is already open.
- [`legacy-url-current-app.png`](legacy-url-current-app.png) shows that `/demo/` resolves to the same current application instead of the deleted standalone player.
- [`catalog-recovery.png`](catalog-recovery.png) shows a failed included-game download with a specific retry/local-file action while every launch choice remains available.
- [`catalog-local-file-recovery.png`](catalog-local-file-recovery.png) shows the same tab playing a locally selected NES file after the failed catalog download.
- [`super-tilt-bro-playing.png`](super-tilt-bro-playing.png) shows the successful retry running Super Tilt Bro in the enlarged play view.
- [`from-below-playing.png`](from-below-playing.png) shows From Below rendering its title sequence in the enlarged play view.

The screenshots were captured from the real Vite application started by `sh scripts/demo.sh`. They verify the initial desktop journey, recovery action, and both included-game success states. They do not prove internet reachability.

## Automated evidence

At the candidate containing these files:

- `python3 scripts/public_entrypoint_smoke.py --browser --screenshot-dir review-evidence/issue-69` passed in 9 seconds. It started the documented command, retrieved `/` and `/demo/`, completed a WebSocket connection, and used Chromium to verify action order, lobby filtering, an unobstructed real file-picker recovery in the failed-download tab, a separate successful Super Tilt Bro retry, successful From Below rendering, directory reconnect, viewport fit, and arbitrary-file room hosting. It forced client startup failure, sent SIGTERM and Ctrl-C to the launcher alone, verified both service ports were released, and relaunched immediately after each case.
- `timeout --foreground 60s sh scripts/preflight.sh` passes in under one minute. It runs 29 Rust tests, 33 Python tests, TypeScript type checking, 96 Node tests, repository hygiene checks, and the source-level public-entrypoint ownership gate.

The runtime result is recorded in [`public-entrypoint.json`](public-entrypoint.json). CI repeats the runtime journey after a clean install and build.
