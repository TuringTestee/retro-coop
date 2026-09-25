#!/bin/sh
# Run all four EB Compose services on one Linux ARM64 host with local HTTP Caddy.
set -eu
cd "$(dirname "$0")/../.."
edge_image=${1:-retro-coop-eb-edge:candidate}
coordinator_image=${2:-retro-coop-eb-coordinator:candidate}
caddy_image=${3:-retro-coop-eb-caddy:candidate}
turn_image=${4:-retro-coop-eb-turn:candidate}
temporary=$(mktemp -d)
project="retroeb$$"
cleanup() {
  docker compose -p "$project" -f "$temporary/docker-compose.yml" -f "$temporary/local.yml" down --remove-orphans --volumes >/dev/null 2>&1 || true
  rm -rf -- "$temporary"
}
trap cleanup EXIT HUP INT TERM

python3 - "$edge_image" "$coordinator_image" "$caddy_image" "$turn_image" "$temporary/docker-compose.yml" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'scripts/aws_eb'))
from package import render
Path(sys.argv[5]).write_text(render(*sys.argv[1:5], local=True))
PY
cat > "$temporary/Caddyfile" <<'EOF_CADDY'
{
    admin off
}
:18080 {
    reverse_proxy 127.0.0.1:8080 {
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto https
    }
}
EOF_CADDY
cat > "$temporary/local.yml" <<'EOF_LOCAL'
services:
  caddy:
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
EOF_LOCAL
export COORDINATOR_ORIGINS=https://retro-coop.1001.page
export TURN_URLS=turn:127.0.0.1:3478?transport=udp
export TURN_SECRET=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
export TURN_PUBLIC_IP=54.1.2.3
export TURN_PRIVATE_IP=127.0.0.1
docker compose -p "$project" -f "$temporary/docker-compose.yml" -f "$temporary/local.yml" config --quiet
docker compose -p "$project" -f "$temporary/docker-compose.yml" -f "$temporary/local.yml" up -d
attempt=0
until curl --silent --fail http://127.0.0.1:18080/healthz >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 80 ]; then
    docker compose -p "$project" -f "$temporary/docker-compose.yml" -f "$temporary/local.yml" logs --tail 100 >&2
    echo 'The one-machine EB Compose stack did not become healthy.' >&2
    exit 1
  fi
  sleep .2
done
node scripts/aws_eb/edge_probe.mjs http://127.0.0.1:8080
node scripts/aws_eb/caddy_probe.mjs http://127.0.0.1:18080
python3 scripts/aws_eb/source_smoke.py --compose "$temporary/docker-compose.yml"
docker compose -p "$project" -f "$temporary/docker-compose.yml" -f "$temporary/local.yml" exec -T turn \
  turnutils_uclient -v -c -n 0 -e 8.8.8.8 -p 3478 -W "$TURN_SECRET" 127.0.0.1 > "$temporary/turn-valid.log"
if ! grep -q 'Received relay addr: 54.1.2.3:' "$temporary/turn-valid.log"; then
  echo 'Coturn did not allocate through the cohosted container.' >&2
  exit 1
fi
