#!/bin/bash
# Every invocation is enclosed by ci_budget.py's shared absolute deadline.
set -euo pipefail
# Never configure system audio or privileged CI namespaces on a local workstation.
test "${GITHUB_ACTIONS:-}" = true
D02_JOB=$1
if [ "$D02_JOB" = build ]; then
  python3 spikes/d02/ci_namespace_probe.py --ci
  git diff --check "$BASE_SHA" HEAD
  sh scripts/foundation/fceumm_prepare.sh & fceumm_pid=$!
  trap 'kill "$fceumm_pid" 2>/dev/null || true' EXIT
  rustup toolchain install 1.95.0 --profile minimal --component rustfmt --target wasm32-unknown-unknown
  (cd spikes/d02
   cargo +1.95.0 fetch --locked
   python3 original_fixture.py fixture.local.nes
   cargo +1.95.0 test --locked --release --lib --no-run
   cargo +1.95.0 build --locked --release --lib --target wasm32-unknown-unknown)
  npm ci
  wait "$fceumm_pid"
  trap - EXIT
  RETRO_COOP_PREBUILT_FCEUMM=1 sh scripts/foundation/prepare.sh
  npm run build:staging
  test ! -e apps/client/dist/generated/diagnostic.nes
  timeout --foreground 60s python3 scripts/public_entrypoint_smoke.py
  timeout --foreground 60s sh scripts/preflight.sh
  exit
fi
if [[ "$D02_JOB" == entrypoint-* ]]; then
  python3 -m venv /tmp/d02-entrypoint-venv
  /tmp/d02-entrypoint-venv/bin/pip install playwright==1.58.0
  # The pinned Ubuntu runner already has Chromium's libraries. Installing apt
  # fonts/upgrades here has variable latency and can exhaust the PR deadline.
  /tmp/d02-entrypoint-venv/bin/playwright install chromium
  export PATH="/tmp/d02-entrypoint-venv/bin:$PATH"
  npm ci
  RETRO_COOP_PREBUILT_CORE=1 RETRO_COOP_PREBUILT_FCEUMM=1 sh scripts/foundation/prepare.sh
  if [ "$D02_JOB" = entrypoint-journey ]; then
    # Run browser cohorts separately to avoid competition within the 90s limits.
    RETRO_COOP_RT2_OUTPUT=spikes/d02/public-entrypoint.local/host-upload timeout --foreground 90s python3 scripts/rooms/host_upload_browser.py
    timeout --foreground 90s python3 scripts/public_entrypoint_smoke.py --browser --screenshot-dir spikes/d02/public-entrypoint.local
    timeout --foreground 60s python3 scripts/foundation/fceumm_browser.py --output spikes/d02/fceumm-boundary.local.json
  fi
  npm run build:staging
  case "$D02_JOB" in
    entrypoint-journey)
      timeout --foreground 30s python3 scripts/featured/observer_isolation_browser.py --output spikes/d02/public-entrypoint.local/solo-release
      timeout --foreground 90s python3 scripts/rooms/two_agent_game.py --role run --expect-controller-ram 128,64 --rom spikes/d02/fixture.local.nes --session-dir spikes/d02/public-entrypoint.local/two-agent-game
      timeout --foreground 90s python3 scripts/rooms/two_agent_game.py --role run --visibility protected --expect-controller-ram 128,64 --rom spikes/d02/fixture.local.nes --session-dir spikes/d02/public-entrypoint.local/two-agent-protected
      ;;
    entrypoint-controls)
      timeout --foreground 60s python3 scripts/rooms/integrated_transfer_browser.py --output spikes/d02/public-entrypoint.local/transfer-recovery & transfer_pid=$!
      # Native edges and the real preparation deadline take 65.58s locally; the shared workflow deadline remains unchanged.
      timeout --foreground 90s python3 scripts/rooms/unified_shell_browser.py --browser chromium --serve --controls-only --output spikes/d02/public-entrypoint.local/controller-ui & controller_pid=$!
      mkdir -p spikes/d02/public-entrypoint.local/exit
      RETRO_EXIT_SCREENSHOT_DIR=spikes/d02/public-entrypoint.local/exit timeout --foreground 60s python3 scripts/rooms/exit_browser.py > spikes/d02/public-entrypoint.local/exit/result.json & exit_pid=$!
      wait "$transfer_pid"
      timeout --foreground 45s python3 scripts/rooms/guest_place_browser.py --output spikes/d02/public-entrypoint.local/guest-place.json
      RETRO_COOP_ACCESS_OUTPUT=spikes/d02/public-entrypoint.local/access timeout --foreground 45s python3 scripts/rooms/access_browser.py > spikes/d02/public-entrypoint.local/access.json
      wait "$exit_pid"
      wait "$controller_pid"
      timeout --foreground 30s python3 scripts/rooms/unified_shell_browser.py --browser chromium --serve --drag-only --output spikes/d02/public-entrypoint.local/controller-drag
      timeout --foreground 30s python3 scripts/rooms/unified_shell_browser.py --browser chromium --serve --picker-only --output spikes/d02/public-entrypoint.local/expanded-picker
      ;;
    entrypoint-ui)
      timeout --foreground 120s python3 scripts/rooms/unified_shell_browser.py --browser chromium --serve --layout-only
      for voice_mode in tabs processes; do
        timeout --foreground 45s python3 scripts/voice/journey_browser.py --serve --mode "$voice_mode" --output "spikes/d02/public-entrypoint.local/voice-$voice_mode"
      done
      ;;
    entrypoint-save-load)
      timeout --foreground 60s python3 scripts/rooms/two_agent_game.py --role host-input --rom spikes/d02/fixture.local.nes --session-dir spikes/d02/public-entrypoint.local/host-input
      timeout --foreground 120s python3 scripts/rooms/two_agent_game.py --role shared-load --expect-controller-ram 0,64 --rom spikes/d02/fixture.local.nes --session-dir spikes/d02/public-entrypoint.local/shared-load
      ;;
    entrypoint-recovery)
      timeout --foreground 210s python3 scripts/rooms/two_agent_game.py --role recovery --rom spikes/d02/fixture.local.nes --session-dir spikes/d02/public-entrypoint.local/recovery
      ;;
    entrypoint-layout)
      timeout --foreground 80s python3 scripts/rooms/unified_shell_browser.py --browser chromium --serve --zoom
      ;;
    *) echo "Unknown entrypoint suite" >&2; exit 2;;
  esac
  exit
fi
echo "Unknown CI job: $D02_JOB" >&2
exit 1
