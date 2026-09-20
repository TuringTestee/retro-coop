#!/bin/sh
# The common profile is applied only to an isolated research namespace.
set -eu
cd "$(dirname "$0")/../.."
: "${GAMEPLAY_EVIDENCE:?Set an absolute evidence directory}"
case "$GAMEPLAY_EVIDENCE" in /*) ;; *) echo "Evidence directory must be absolute" >&2; exit 2;; esac
GAMEPLAY_RUN_ID=$(python3 -c 'import uuid; print(uuid.uuid4().hex)')
GAMEPLAY_EVIDENCE="$GAMEPLAY_EVIDENCE/$GAMEPLAY_RUN_ID"
export GAMEPLAY_RUN_ID GAMEPLAY_EVIDENCE
mkdir -p "$GAMEPLAY_EVIDENCE"
python3 -c 'import json,os,pathlib; pathlib.Path(os.environ["GAMEPLAY_EVIDENCE"],"run-id.local.json").write_text(json.dumps({"run_id":os.environ["GAMEPLAY_RUN_ID"]}))'
export GAMEPLAY_EVIDENCE
exec unshare --user --map-root-user --net sh -c '
set -eu
. spikes/d02/network_profile.sh
setup_network_profile
ip -j route get 10.201.0.1 > "$GAMEPLAY_EVIDENCE/route.local.json"
tc -j -s qdisc show dev lo > "$GAMEPLAY_EVIDENCE/netem-before.local.json"
python3 spikes/d02/capture_udp.py "$GAMEPLAY_EVIDENCE/udp-headers.local.json" "$GAMEPLAY_EVIDENCE/capture-ready" &
capture=$!
cleanup() {
 status=$?
 trap - EXIT
 kill "$capture" 2>/dev/null || true
 wait "$capture" || true
 tc -j -s qdisc show dev lo > "$GAMEPLAY_EVIDENCE/netem-after.local.json"
 python3 spikes/d02/finish_network_run.py "$GAMEPLAY_EVIDENCE"
 if [ "$status" -eq 0 ]; then python3 scripts/gameplay/verify.py "$GAMEPLAY_EVIDENCE/gameplay.json"; fi
 exit "$status"
}
trap cleanup EXIT
trap '\''exit 124'\'' INT TERM
while [ ! -f "$GAMEPLAY_EVIDENCE/capture-ready" ]; do kill -0 "$capture"; sleep .05; done
python3 scripts/gameplay/browser_smoke.py "$@" --output "$GAMEPLAY_EVIDENCE/gameplay.json"
' gameplay-network "$@"
