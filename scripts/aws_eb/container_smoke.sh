#!/bin/sh
# Run the EB Compose shape on one Linux host with the candidate images.
set -eu
cd "$(dirname "$0")/../.."
edge_image=${1:-retro-coop-eb-edge:candidate}
coordinator_image=${2:-retro-coop-eb-coordinator:candidate}
temporary=$(mktemp -d)
project="retroeb$$"
cleanup() {
  docker compose -p "$project" -f "$temporary/docker-compose.yml" down --remove-orphans >/dev/null 2>&1 || true
  rm -rf -- "$temporary"
}
trap cleanup EXIT HUP INT TERM

python3 - "$edge_image" "$coordinator_image" "$temporary/docker-compose.yml" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'scripts/aws_eb'))
from package import render
Path(sys.argv[3]).write_text(render(sys.argv[1], sys.argv[2], local=True))
PY
export COORDINATOR_ORIGINS=https://retro-coop.1001.page
export TURN_URLS=turn:127.0.0.1:3478?transport=udp
export TURN_SECRET=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
docker compose -p "$project" -f "$temporary/docker-compose.yml" config --quiet
docker compose -p "$project" -f "$temporary/docker-compose.yml" up -d

attempt=0
until curl --silent --fail http://127.0.0.1:8080/healthz >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 60 ]; then
    docker compose -p "$project" -f "$temporary/docker-compose.yml" logs --tail 100 >&2
    echo 'The EB-shaped edge and coordinator did not become healthy.' >&2
    exit 1
  fi
  sleep .2
done
node scripts/aws_eb/edge_probe.mjs http://127.0.0.1:8080
python3 scripts/aws_eb/source_smoke.py --compose "$temporary/docker-compose.yml"
