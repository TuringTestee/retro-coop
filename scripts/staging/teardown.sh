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

gcloud container clusters get-credentials cache-guard-test --project="$project" --region="$region" --quiet >/dev/null
kubectl delete namespace retro-coop-staging --ignore-not-found=true --wait=true --timeout=10m
test -z "$(kubectl get namespace retro-coop-staging -o name --ignore-not-found)" || {
  echo 'Staging namespace still exists; stop before releasing its load-balancer IP.' >&2; exit 1;
}

if [ -n "$(gcloud compute instances list --project="$project" --filter='name=retro-coop-staging-turn' --format='value(name)')" ]; then
  gcloud compute instances delete retro-coop-staging-turn --project="$project" --zone="$zone" --quiet
fi
for name in retro-coop-staging-turn retro-coop-staging-ssh; do
  if [ -n "$(gcloud compute firewall-rules list --project="$project" --filter="name=$name" --format='value(name)')" ]; then
    gcloud compute firewall-rules delete "$name" --project="$project" --quiet
  fi
done
if [ -n "$(gcloud compute networks subnets list --project="$project" --filter='name=retro-coop-staging' --format='value(name)')" ]; then
  gcloud compute networks subnets delete retro-coop-staging --project="$project" --region="$region" --quiet
fi
if [ -n "$(gcloud compute networks list --project="$project" --filter='name=retro-coop-staging' --format='value(name)')" ]; then
  gcloud compute networks delete retro-coop-staging --project="$project" --quiet
fi
if [ -n "$(gcloud compute addresses list --project="$project" --filter='name=retro-coop-staging-ip' --format='value(name)')" ]; then
  gcloud compute addresses delete retro-coop-staging-ip --project="$project" --region="$region" --quiet
fi
repositories=$(gcloud artifacts repositories list --project="$project" --location="$region" --format='value(name)')
if printf '%s\n' "$repositories" | rg -qx 'retro-coop-staging'; then
  gcloud artifacts repositories delete retro-coop-staging --project="$project" --location="$region" --quiet
fi

test -z "$(gcloud compute instances list --project="$project" --filter='name=retro-coop-staging-turn' --format='value(name)')"
test -z "$(gcloud compute addresses list --project="$project" --filter='name=retro-coop-staging-ip' --format='value(name)')"
test -z "$(gcloud compute networks list --project="$project" --filter='name=retro-coop-staging' --format='value(name)')"
test -z "$(gcloud compute networks subnets list --project="$project" --filter='name=retro-coop-staging' --format='value(name)')"
for name in retro-coop-staging-turn retro-coop-staging-ssh; do
  test -z "$(gcloud compute firewall-rules list --project="$project" --filter="name=$name" --format='value(name)')"
done
repositories=$(gcloud artifacts repositories list --project="$project" --location="$region" --format='value(name)')
if printf '%s\n' "$repositories" | rg -qx 'retro-coop-staging'; then
  echo 'The staging image repository still exists.' >&2
  exit 1
fi
echo 'D24 namespace, relay VM/network, reserved IP and isolated image repository removed.'
