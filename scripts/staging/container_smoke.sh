#!/bin/sh
# Run the exact candidate images on one Linux host, matching one Pod's shared loopback.
set -eu
cd "$(dirname "$0")/../.."

edge_image=${1:-retro-coop-staging-edge:candidate}
coordinator_image=${2:-retro-coop-staging-coordinator:candidate}
certificate_dir=$(mktemp -d)
suffix=$(basename "$certificate_dir")
edge_name="retro-coop-edge-$suffix"
coordinator_name="retro-coop-coordinator-$suffix"
cleanup() {
  docker rm -f "$edge_name" "$coordinator_name" >/dev/null 2>&1 || true
  rm -rf -- "$certificate_dir"
}
trap cleanup EXIT HUP INT TERM

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$certificate_dir/tls.key" -out "$certificate_dir/tls.crt" \
  -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost' -days 1 >/dev/null 2>&1
chmod 755 "$certificate_dir"
chmod 644 "$certificate_dir/tls.key"

docker run -d --network host --name "$coordinator_name" \
  --env COORDINATOR_ORIGINS=https://localhost:8443 "$coordinator_image" >/dev/null
docker run -d --network host --name "$edge_name" \
  --mount "type=bind,source=$certificate_dir,target=/run/tls,readonly" "$edge_image" >/dev/null

ready=0
attempt=0
while [ "$attempt" -lt 50 ]; do
  if curl --silent --fail http://127.0.0.1:8787/health >/dev/null && \
     curl --silent --fail --cacert "$certificate_dir/tls.crt" https://localhost:8443/healthz >/dev/null; then
    ready=1
    break
  fi
  attempt=$((attempt + 1))
  sleep .1
done
if [ "$ready" -ne 1 ]; then
  docker logs "$coordinator_name" >&2 || true
  docker logs "$edge_name" >&2 || true
  echo 'Staging images did not start.' >&2
  exit 1
fi

NODE_EXTRA_CA_CERTS="$certificate_dir/tls.crt" node scripts/staging/edge_probe.mjs https://localhost:8443
