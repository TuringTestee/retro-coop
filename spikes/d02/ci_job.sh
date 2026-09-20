#!/bin/bash
# Every invocation is enclosed by ci_budget.py's shared absolute deadline.
set -euo pipefail
# Never configure system audio or privileged CI namespaces on a local workstation.
test "${GITHUB_ACTIONS:-}" = true
D02_JOB=$1
if [ "$D02_JOB" = build ]; then
  python3 spikes/d02/ci_namespace_probe.py --ci
  git diff --check "$BASE_SHA" HEAD
  rustup toolchain install 1.95.0 --profile minimal --component rustfmt --target wasm32-unknown-unknown
  (cd spikes/d02
   cargo +1.95.0 fetch --locked
   python3 original_fixture.py fixture.local.nes
   cargo +1.95.0 test --locked --release --lib --no-run
   cargo +1.95.0 build --locked --release --lib --target wasm32-unknown-unknown)
  npm ci
  sh scripts/foundation/prepare.sh
  npm run build:staging
  timeout --foreground 60s sh scripts/preflight.sh
  exit
fi
python3 -m venv /tmp/d02-browser-venv
/tmp/d02-browser-venv/bin/pip install playwright==1.58.0
/tmp/d02-browser-venv/bin/playwright install --with-deps chromium firefox
export PATH="/tmp/d02-browser-venv/bin:$PATH"
cd spikes/d02
python3 ci_resources.py resources-before.local.json
trap 'python3 ci_resources.py resources-after.local.json' EXIT
if [ "$D02_JOB" = core ]; then
  (cd ../.. && npm ci)
  sudo apt-get update
  sudo apt-get install -y coturn
  turnserver --version > turn-version.local.txt
  python3 -m http.server 8765 --bind 127.0.0.1 >/tmp/d02-http.log 2>&1 &
  D02_HTTP_PID=$!
  trap 'kill "$D02_HTTP_PID"; python3 ci_resources.py resources-after.local.json' EXIT
  timeout --foreground 1200s python3 browser_probe.py fixture.local.nes --bundled-chromium --output browser-ci.local.json
  python3 verify_results.py browser-ci.local.json
  timeout --foreground 60s python3 demo/demo_smoke.py fixture.local.nes --output demo-smoke.local.json
  (cd ../.. && timeout --foreground 90s python3 scripts/foundation/browser_smoke.py --output spikes/d02/foundation.local.json)
  (cd ../.. && timeout --foreground 60s python3 scripts/staging/versioned_core_smoke.py --output spikes/d02/versioned-core.local.json)
  (cd ../.. && timeout --foreground 90s python3 scripts/rooms/browser_smoke.py --output spikes/d02/rooms.local.json)
  (cd ../.. && timeout --foreground 60s python3 scripts/rooms/moderation_smoke.py --output spikes/d02/moderation.local.json)
  (cd ../.. && timeout --foreground 60s python3 scripts/rooms/operator_smoke.py --output spikes/d02/operator.local.json)
  (cd ../.. && timeout --foreground 90s python3 scripts/rooms/chat_smoke.py --output spikes/d02/chat.local.json)
  (cd ../.. && timeout --foreground 120s python3 scripts/peer/browser_smoke.py --output spikes/d02/peer.local.json)
  for D17_PAIR in Chrome-Chrome Chrome-Firefox Firefox-Firefox; do
    (cd ../.. && timeout --foreground 90s python3 scripts/voice/browser_smoke.py --pair "$D17_PAIR" --output "spikes/d02/voice-$D17_PAIR-direct.local.json")
    (cd ../.. && timeout --foreground 90s python3 scripts/voice/browser_smoke.py --pair "$D17_PAIR" --relay --output "spikes/d02/voice-$D17_PAIR-relay.local.json")
  done
  (cd ../.. && timeout --foreground 90s python3 scripts/rooms/directory_smoke.py --output spikes/d02/directory.local.json)
elif [ "$D02_JOB" = network ]; then
  timeout --foreground 180s python3 prepare_stock_firefox.py /tmp/d02-stock-firefox
  cp /tmp/d02-stock-firefox/browser-build.json stock-firefox-build.local.json
  # This sink exists only on the ephemeral CI runner, never the user's machine.
  sudo apt-get update
  sudo apt-get install -y pulseaudio pulseaudio-utils
  pulseaudio --start --exit-idle-time=-1
  pactl load-module module-null-sink sink_name=d02 rate=48000 channels=2
  pactl set-default-sink d02
  test "$(pactl get-default-sink)" = d02
  pulseaudio --version > audio-backend.local.txt
  pactl list short sinks >> audio-backend.local.txt
  sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0
  python3 ci_resources.py resources-before.local.json
  timeout --foreground 900s sh run_network_probe.sh fixture.local.nes --seconds 600 --pair "$D02_PAIR" --bundled-chromium --firefox-executable /tmp/d02-stock-firefox/firefox/firefox --output pair.local.json
  python3 verify_realtime.py pair.local.json --require-muted
else
  echo 'Unknown CI job' >&2
  exit 1
fi
