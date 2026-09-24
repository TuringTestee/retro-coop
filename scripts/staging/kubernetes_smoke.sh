#!/bin/sh
# Exercise the rendered staging workload in an isolated, local Kubernetes node.
set -eu
cd "$(dirname "$0")/../.."

edge_image=${1:-retro-coop-staging-edge:candidate}
coordinator_image=${2:-retro-coop-staging-coordinator:candidate}
cluster_name="retro-coop-k3s-$$"
temporary=$(mktemp -d)
cleanup() {
  docker rm -f "$cluster_name" >/dev/null 2>&1 || true
  python3 - "$temporary" <<'PY'
import shutil, sys
shutil.rmtree(sys.argv[1])
PY
}
trap cleanup EXIT HUP INT TERM

# Pin the small K3s test runtime; the production cluster remains GKE.
k3s_image='rancher/k3s:v1.35.8-k3s1@sha256:59fe491fd3b73204e499e40b325240d85c42c7189c3ae50150d37b78243f3b32'
docker run -d --privileged --name "$cluster_name" -p 127.0.0.1::6443 "$k3s_image" server \
  --disable traefik --disable servicelb --disable metrics-server >/dev/null

ready=0
attempt=0
while [ "$attempt" -lt 80 ]; do
  if docker cp "$cluster_name:/etc/rancher/k3s/k3s.yaml" "$temporary/kubeconfig" >/dev/null 2>&1; then
    ready=1
    break
  fi
  attempt=$((attempt + 1))
  sleep .5
done
if [ "$ready" -ne 1 ]; then
  docker logs --tail 80 "$cluster_name" >&2
  echo 'Local Kubernetes config was not created.' >&2
  exit 1
fi
port=$(docker port "$cluster_name" 6443/tcp | sed 's/.*://')
python3 - "$temporary/kubeconfig" "$port" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
source = path.read_text()
if source.count('server: https://127.0.0.1:6443') != 1:
    raise SystemExit('Unexpected local Kubernetes endpoint')
path.write_text(source.replace('server: https://127.0.0.1:6443', 'server: https://127.0.0.1:' + sys.argv[2]))
PY
kube() { KUBECONFIG="$temporary/kubeconfig" kubectl "$@"; }
attempt=0
until kube get nodes >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 40 ]; then
    kube get nodes >&2
    exit 1
  fi
  sleep .5
done
kube wait --for=condition=Ready node --all --timeout=60s

docker tag "$edge_image" localhost/retro-coop-staging-edge:ci
docker tag "$coordinator_image" localhost/retro-coop-staging-coordinator:ci
docker save localhost/retro-coop-staging-edge:ci localhost/retro-coop-staging-coordinator:ci |
  docker exec -i "$cluster_name" k3s ctr --namespace k8s.io images import - >/dev/null

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$temporary/tls.key" -out "$temporary/tls.crt" \
  -subj '/CN=127.0.0.1' -addext 'subjectAltName=IP:127.0.0.1' -days 1 >/dev/null 2>&1
kube create namespace retro-coop-staging >/dev/null
kube -n retro-coop-staging create secret tls retro-coop-staging-tls \
  --cert="$temporary/tls.crt" --key="$temporary/tls.key" >/dev/null
kube -n retro-coop-staging create secret generic retro-coop-staging-turn \
  --from-literal=TURN_URLS=turn:127.0.0.1:3478?transport=udp \
  --from-literal=TURN_SECRET=0123456789abcdef0123456789abcdef >/dev/null

python3 scripts/staging/render_k8s.py \
  --public-ip 34.100.1.2 \
  --edge-image us-central1-docker.pkg.dev/sample/retro-coop-staging/edge@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --coordinator-image us-central1-docker.pkg.dev/sample/retro-coop-staging/coordinator@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
  --allow 8.8.8.8/32 > "$temporary/staging.yaml"
python3 - "$temporary/staging.yaml" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
source = path.read_text()
replacements = {
    'us-central1-docker.pkg.dev/sample/retro-coop-staging/edge@sha256:' + 'a'*64: 'localhost/retro-coop-staging-edge:ci',
    'us-central1-docker.pkg.dev/sample/retro-coop-staging/coordinator@sha256:' + 'b'*64: 'localhost/retro-coop-staging-coordinator:ci',
}
for old, new in replacements.items():
    if source.count(old) != 1:
        raise SystemExit('Expected exactly one rendered image placeholder')
    source = source.replace(old, new)
path.write_text(source)
PY
kube apply -f "$temporary/staging.yaml"
kube -n retro-coop-staging rollout status \
  deployment/retro-coop-staging --timeout=60s
kube -n retro-coop-staging get configmap \
  retro-coop-staging-config -o jsonpath='{.data.COORDINATOR_ORIGINS}' |
  grep -qx 'https://34.100.1.2'
kube -n retro-coop-staging exec \
  deployment/retro-coop-staging -c coordinator -- node -e \
  "if(process.env.COORDINATOR_ORIGINS!=='https://34.100.1.2')process.exit(1)"
kube -n retro-coop-staging get pods \
  -l app=retro-coop-staging -o json > "$temporary/pods.json"
python3 - "$temporary/pods.json" <<'PY'
import json, sys
pods = json.load(open(sys.argv[1]))['items']
if len(pods) != 1:
    raise AssertionError('Expected one staging Pod')
statuses = {item['name']: item['ready'] for item in pods[0]['status']['containerStatuses']}
if statuses != {'edge': True, 'coordinator': True}:
    raise AssertionError(f'Staging containers not ready: {statuses}')
print('Kubernetes staging passed: one Pod, both containers Ready, Origin ConfigMap resolved in staging namespace.')
PY
