#!/bin/sh
# Prepare and run the current lobby application on this computer. Ctrl-C stops both services.
set -eu
cd "$(dirname "$0")/.."

if [ "${RETRO_COOP_SKIP_INSTALL:-0}" != 1 ]; then
  npm ci
fi
if [ "${RETRO_COOP_SKIP_PREPARE:-0}" != 1 ]; then
  sh scripts/foundation/prepare.sh
fi

coordinator_pid=
client_pid=
cleanup() {
  trap - EXIT HUP INT TERM
  for pid in "$client_pid" "$coordinator_pid"; do
    if [ -n "$pid" ]; then kill "$pid" 2>/dev/null || true; fi
  done
  attempts=0
  while [ "$attempts" -lt 40 ]; do
    alive=0
    for pid in "$client_pid" "$coordinator_pid"; do
      if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then alive=1; fi
    done
    if [ "$alive" -eq 0 ]; then break; fi
    attempts=$((attempts + 1))
    sleep .05
  done
  for pid in "$client_pid" "$coordinator_pid"; do
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then kill -KILL "$pid" 2>/dev/null || true; fi
  done
  for pid in "$client_pid" "$coordinator_pid"; do
    if [ -n "$pid" ]; then wait "$pid" 2>/dev/null || true; fi
  done
}
on_signal() { status=$1; cleanup; exit "$status"; }
trap cleanup EXIT
trap 'on_signal 129' HUP
trap 'on_signal 130' INT
trap 'on_signal 143' TERM

COORDINATOR_ORIGINS=http://127.0.0.1:8765 node apps/coordinator/src/main.ts > /tmp/retro-coop-coordinator.log 2>&1 &
coordinator_pid=$!
python3 - <<'PY'
import time
from urllib.request import urlopen
for _ in range(100):
    try:
        with urlopen('http://127.0.0.1:8787/health', timeout=.2) as response:
            if response.status == 200:
                break
    except OSError:
        time.sleep(.05)
else:
    raise SystemExit('The room coordinator did not start; see /tmp/retro-coop-coordinator.log')
PY
if ! kill -0 "$coordinator_pid" 2>/dev/null; then
  echo 'The room coordinator exited; port 8787 may already be in use. See /tmp/retro-coop-coordinator.log.' >&2
  exit 1
fi

printf '\nOpen http://127.0.0.1:8765/ to play or host a lobby. Ctrl-C stops Retro Coop.\n'
(
  cd apps/client
  exec env PUBLIC_COORDINATOR_URL=http://127.0.0.1:8787 \
    PUBLIC_CATALOG_GAMES=super-tilt-bro-pal,from-below-1.0 \
    node ../../node_modules/vite/bin/vite.js --host 127.0.0.1 --port 8765 --strictPort
) &
client_pid=$!
set +e
wait "$client_pid"
status=$?
set -e
client_pid=
exit "$status"
