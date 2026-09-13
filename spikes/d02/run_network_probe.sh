#!/bin/sh
# Isolated research network only. Host interfaces/routes are never modified.
set -eu
cd "$(dirname "$0")"
D02_RUN_ID=$(python3 -c 'import uuid; print(uuid.uuid4())')
D02_EVIDENCE_DIR="$(pwd)/.network-runs/$D02_RUN_ID"
export D02_RUN_ID D02_EVIDENCE_DIR
mkdir -p "$D02_EVIDENCE_DIR"
python3 -c 'import json,os,pathlib; pathlib.Path(os.environ["D02_EVIDENCE_DIR"],"run-id.local.json").write_text(json.dumps({"run_id":os.environ["D02_RUN_ID"]}))'
exec unshare --user --map-root-user --net sh -c '
set -eu
ip link set lo up
ip link add d02probe type dummy
ip addr add 10.201.0.1/24 dev d02probe
ip link set d02probe up
ip route add default dev d02probe
tc qdisc add dev lo root netem limit 1000 delay 50ms 10ms loss 1%
ip -j route get 10.201.0.1 > "$D02_EVIDENCE_DIR/route.local.json"
tc -j -s qdisc show dev lo > "$D02_EVIDENCE_DIR/netem-before.local.json"
python3 serve_probe.py "$D02_EVIDENCE_DIR/http-ready" >"$D02_EVIDENCE_DIR/http.log" 2>&1 &
D02_HTTP_PID=$!
python3 capture_udp.py "$D02_EVIDENCE_DIR/udp-headers.local.json" "$D02_EVIDENCE_DIR/capture-ready" &
D02_CAPTURE_PID=$!
cleanup() {
  D02_STATUS=$?
  trap - EXIT
  kill "$D02_HTTP_PID" "$D02_CAPTURE_PID" 2>/dev/null || true
  wait "$D02_CAPTURE_PID" || true
  tc -j -s qdisc show dev lo > "$D02_EVIDENCE_DIR/netem-after.local.json"
  python3 finish_network_run.py "$D02_EVIDENCE_DIR" || D02_STATUS=1
  exit "$D02_STATUS"
}
trap cleanup EXIT
trap '\''exit 124'\'' INT TERM
while [ ! -f "$D02_EVIDENCE_DIR/http-ready" ] || [ ! -f "$D02_EVIDENCE_DIR/capture-ready" ]; do
  kill -0 "$D02_HTTP_PID" "$D02_CAPTURE_PID"
  sleep 0.05
done
python3 realtime_probe.py "$@"
' d02-network "$@"
