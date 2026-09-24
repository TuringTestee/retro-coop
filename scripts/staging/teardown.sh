#!/bin/sh
# Remove only the isolated D24 trial resources and verify that they are absent.
set -eu
test "$#" -eq 1 || { echo 'Use: teardown.sh PROJECT' >&2; exit 2; }
project=$1
test "$project" = bship-164753-06152350 || { echo 'The reviewed staging project does not match.' >&2; exit 2; }
region=us-central1
zone=us-central1-a
temporary=$(mktemp -d)
trap 'python3 - "$temporary" <<"PY"
import shutil, sys
shutil.rmtree(sys.argv[1])
PY' EXIT HUP INT TERM
export KUBECONFIG="$temporary/kubeconfig"
query() {
  label=$1
  shift
  if ! query_result=$("$@"); then
    echo "Could not check $label; teardown incomplete." >&2
    exit 1
  fi
}
repository_present() {
  printf '%s\n' "$query_result" | grep -Fxq -e 'retro-coop-staging' -e "projects/$project/locations/$region/repositories/retro-coop-staging"
}

query 'relay VM' gcloud compute instances list --project="$project" --filter='name=retro-coop-staging-turn' --format='value(name)'
if [ -n "$query_result" ]; then
  gcloud compute instances delete retro-coop-staging-turn --project="$project" --zone="$zone" --quiet
fi
gcloud container clusters get-credentials cache-guard-test --project="$project" --region="$region" --quiet >/dev/null
kubectl delete namespace retro-coop-staging --ignore-not-found=true --wait=true --timeout=10m
query 'staging namespace' kubectl get namespace retro-coop-staging -o name --ignore-not-found
test -z "$query_result" || {
  echo 'Staging namespace still exists; stop before releasing its load-balancer IP.' >&2; exit 1;
}

for name in retro-coop-staging-turn retro-coop-staging-ssh; do
  query "firewall rule $name" gcloud compute firewall-rules list --project="$project" --filter="name=$name" --format='value(name)'
  if [ -n "$query_result" ]; then
    gcloud compute firewall-rules delete "$name" --project="$project" --quiet
  fi
done
query 'staging subnet' gcloud compute networks subnets list --project="$project" --filter='name=retro-coop-staging' --format='value(name)'
if [ -n "$query_result" ]; then
  gcloud compute networks subnets delete retro-coop-staging --project="$project" --region="$region" --quiet
fi
query 'staging network' gcloud compute networks list --project="$project" --filter='name=retro-coop-staging' --format='value(name)'
if [ -n "$query_result" ]; then
  gcloud compute networks delete retro-coop-staging --project="$project" --quiet
fi
query 'staging address' gcloud compute addresses list --project="$project" --filter='name=retro-coop-staging-ip' --format='value(name)'
if [ -n "$query_result" ]; then
  gcloud compute addresses delete retro-coop-staging-ip --project="$project" --region="$region" --quiet
fi
query 'image repository' gcloud artifacts repositories list --project="$project" --location="$region" --format='value(name)'
if repository_present; then
  gcloud artifacts repositories delete retro-coop-staging --project="$project" --location="$region" --quiet
fi

verify_absent() {
  label=$1
  shift
  query "$label" "$@"
  test -z "$query_result" || { echo "$label still exists; teardown incomplete." >&2; exit 1; }
}
verify_absent 'relay VM' gcloud compute instances list --project="$project" --filter='name=retro-coop-staging-turn' --format='value(name)'
verify_absent 'staging address' gcloud compute addresses list --project="$project" --filter='name=retro-coop-staging-ip' --format='value(name)'
verify_absent 'staging network' gcloud compute networks list --project="$project" --filter='name=retro-coop-staging' --format='value(name)'
verify_absent 'staging subnet' gcloud compute networks subnets list --project="$project" --filter='name=retro-coop-staging' --format='value(name)'
for name in retro-coop-staging-turn retro-coop-staging-ssh; do
  verify_absent "firewall rule $name" gcloud compute firewall-rules list --project="$project" --filter="name=$name" --format='value(name)'
done
query 'image repository' gcloud artifacts repositories list --project="$project" --location="$region" --format='value(name)'
if repository_present; then
  echo 'The staging image repository still exists.' >&2
  exit 1
fi
echo 'D24 namespace, relay VM/network, reserved IP and isolated image repository removed.'
