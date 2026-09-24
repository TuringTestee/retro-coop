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
preferred_client_port=${RETRO_COOP_CLIENT_PORT:-8765}
preferred_coordinator_port=${RETRO_COOP_COORDINATOR_PORT:-8787}
ports=$(python3 - "$preferred_client_port" "$preferred_coordinator_port" <<'PY'
import socket
import sys

def available(preferred, reserved):
    try:
        start = int(preferred)
    except ValueError:
        raise SystemExit(f'Invalid demo port: {preferred}')
    if not 1 <= start <= 65535:
        raise SystemExit(f'Invalid demo port: {preferred}')
    for port in range(start, 65536):
        if port in reserved:
            continue
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(('127.0.0.1', port))
            except OSError:
                continue
        return port
    raise SystemExit(f'No free local port from {start} through 65535')

client = available(sys.argv[1], set())
coordinator = available(sys.argv[2], {client})
print(client, coordinator)
PY
)
set -- $ports
client_port=$1
coordinator_port=$2
if [ "$client_port" != "$preferred_client_port" ] || [ "$coordinator_port" != "$preferred_coordinator_port" ]; then
  printf 'Preferred demo ports are busy; using client %s and coordinator %s.\n' "$client_port" "$coordinator_port"
fi

coordinator_pid=
client_pid=
demo_rom_dir=
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
  if [ -n "$demo_rom_dir" ]; then rm -rf -- "$demo_rom_dir"; fi
}
on_signal() { status=$1; cleanup; exit "$status"; }
trap cleanup EXIT
trap 'on_signal 129' HUP
trap 'on_signal 130' INT
trap 'on_signal 143' TERM

if [ -n "${COORDINATOR_ROM_DIR:-}" ]; then
  coordinator_rom_dir=$COORDINATOR_ROM_DIR
else
  demo_rom_dir=$(mktemp -d "${TMPDIR:-/tmp}/retro-coop-demo-roms.XXXXXX")
  coordinator_rom_dir=$demo_rom_dir
fi
coordinator_log="/tmp/retro-coop-coordinator-$coordinator_port.log"
COORDINATOR_PORT="$coordinator_port" COORDINATOR_ORIGINS="http://127.0.0.1:$client_port" COORDINATOR_EMPTY_OFFERS=super-tilt-bro-pal,from-below-1.0 COORDINATOR_REQUIRE_CUSTOM_UPLOAD=1 COORDINATOR_ROM_DIR="$coordinator_rom_dir" node apps/coordinator/src/main.ts > "$coordinator_log" 2>&1 &
coordinator_pid=$!
python3 - "$coordinator_port" "$coordinator_log" <<'PY'
import sys
import time
from urllib.request import urlopen
for _ in range(100):
    try:
        with urlopen(f'http://127.0.0.1:{sys.argv[1]}/health', timeout=.2) as response:
            if response.status == 200:
                break
    except OSError:
        time.sleep(.05)
else:
    raise SystemExit(f'The room coordinator did not start; see {sys.argv[2]}')
PY
if ! kill -0 "$coordinator_pid" 2>/dev/null; then
  echo "The room coordinator exited; port $coordinator_port may already be in use. See $coordinator_log." >&2
  exit 1
fi

(
  cd apps/client
  exec env PUBLIC_COORDINATOR_URL="http://127.0.0.1:$coordinator_port" \
    PUBLIC_CATALOG_GAMES=super-tilt-bro-pal,from-below-1.0 \
    node ../../node_modules/vite/bin/vite.js --host 127.0.0.1 --port "$client_port" --strictPort
) &
client_pid=$!
python3 - "$client_port" <<'PY'
import sys
import time
from urllib.request import urlopen
for _ in range(100):
    try:
        with urlopen(f'http://127.0.0.1:{sys.argv[1]}/', timeout=.2) as response:
            if response.status == 200:
                break
    except OSError:
        time.sleep(.05)
else:
    raise SystemExit('The demo client did not start on the selected port.')
PY
printf '\nOpen http://127.0.0.1:%s/ to play or host a lobby. Ctrl-C stops Retro Coop.\n' "$client_port"
set +e
wait "$client_pid"
status=$?
set -e
client_pid=
exit "$status"
