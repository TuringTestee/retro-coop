#!/bin/sh
# Create only the isolated, timed TURN VM and its narrow network rules.
set -eu
cd "$(dirname "$0")/../.."

test "$#" -eq 5 || { echo 'Use: provision_turn.sh PROJECT ZONE TESTER_IP/32 TESTER_IP/32 OPERATOR_IP/32' >&2; exit 2; }
project=$1
zone=$2
tester_one=$3
tester_two=$4
operator=$5
test "$project" = bship-164753-06152350 || { echo 'The reviewed staging project does not match.' >&2; exit 2; }
python3 -B - "$tester_one" "$tester_two" "$operator" <<'PY'
import sys
import argparse
sys.path.insert(0, 'scripts/staging')
from render_k8s import source_range
for value in sys.argv[1:]:
    if not value.endswith('/32'):
        raise SystemExit('Tester and operator sources must be individual public IPv4 addresses')
    try:
        source_range(value)
    except argparse.ArgumentTypeError as error:
        raise SystemExit(str(error)) from error
PY
test "$zone" = us-central1-a || { echo 'The reviewed VM zone is us-central1-a.' >&2; exit 2; }
require_absent() {
  label=$1
  shift
  if ! found=$("$@"); then
    echo "Could not check $label; no staging resource was created." >&2
    exit 1
  fi
  test -z "$found" || { echo "$label already exists; inspect it before retrying." >&2; exit 1; }
}
require_absent 'the dedicated staging network' gcloud compute networks list --project="$project" --filter='name=retro-coop-staging' --format='value(name)'
require_absent 'the staging subnet' gcloud compute networks subnets list --project="$project" --filter='name=retro-coop-staging' --format='value(name)'
require_absent 'the staging TURN VM' gcloud compute instances list --project="$project" --filter='name=retro-coop-staging-turn' --format='value(name)'
for name in retro-coop-staging-ssh retro-coop-staging-turn; do
  require_absent "firewall rule $name" gcloud compute firewall-rules list --project="$project" --filter="name=$name" --format='value(name)'
done

gcloud compute networks create retro-coop-staging --project="$project" --subnet-mode=custom --quiet
gcloud compute networks subnets create retro-coop-staging --project="$project" --network=retro-coop-staging \
  --region=us-central1 --range=10.76.0.0/28 --quiet
gcloud compute firewall-rules create retro-coop-staging-ssh --project="$project" --network=retro-coop-staging \
  --direction=INGRESS --allow=tcp:22 --source-ranges="$operator" --target-tags=retro-coop-staging-turn --quiet
gcloud compute firewall-rules create retro-coop-staging-turn --project="$project" --network=retro-coop-staging \
  --direction=INGRESS --allow=udp:3478,tcp:3478,udp:49160-49175 \
  --source-ranges="$tester_one,$tester_two" --target-tags=retro-coop-staging-turn --quiet
gcloud compute instances create retro-coop-staging-turn --project="$project" --zone="$zone" \
  --machine-type=e2-micro --image-project=debian-cloud --image=debian-12-bookworm-v20260921 \
  --boot-disk-size=10GB --boot-disk-type=pd-balanced --network=retro-coop-staging --subnet=retro-coop-staging \
  --tags=retro-coop-staging-turn --no-service-account --no-scopes --no-restart-on-failure \
  --max-run-duration=6h --instance-termination-action=DELETE --quiet
termination=$(gcloud compute instances describe retro-coop-staging-turn --project="$project" --zone="$zone" \
  --format='value(scheduling.terminationTimestamp)')
test -n "$termination" || { echo 'The VM has no termination timestamp; tear down the trial immediately.' >&2; exit 1; }
private_ip=$(gcloud compute instances describe retro-coop-staging-turn --project="$project" --zone="$zone" \
  --format='value(networkInterfaces[0].networkIP)')
public_ip=$(gcloud compute instances describe retro-coop-staging-turn --project="$project" --zone="$zone" \
  --format='value(networkInterfaces[0].accessConfigs[0].natIP)')
test -n "$private_ip" && test -n "$public_ip" || {
  echo 'The VM has no public and private IPv4 pair; tear down the trial immediately.' >&2; exit 1;
}
gcloud compute instances describe retro-coop-staging-turn --project="$project" --zone="$zone" \
  --format='table(name,networkInterfaces[0].networkIP,networkInterfaces[0].accessConfigs[0].natIP,scheduling.terminationTimestamp)'
echo 'The VM must be configured and checked before adding its TURN URL to the coordinator Secret.'
echo 'If setup fails, run scripts/staging/teardown.sh immediately; a timed VM does not remove the VPC or firewall rules.'
