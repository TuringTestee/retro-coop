#!/bin/sh
# Create only the named D24 image repository and address, then build one clean main revision.
set -eu
test "$#" -eq 1 || { echo 'Use: prepare_cloud.sh PROJECT' >&2; exit 2; }
project=$1
test "$project" = bship-164753-06152350 || { echo 'The reviewed staging project does not match.' >&2; exit 2; }
region=us-central1
repository=retro-coop-staging
address=retro-coop-staging-ip
root=$(git rev-parse --show-toplevel)
test "$PWD" = "$root" || { echo 'Run from the repository root.' >&2; exit 2; }
test "$(git branch --show-current)" = main || { echo 'Run from reviewed main.' >&2; exit 2; }
test -z "$(git status --porcelain)" || { echo 'The checkout has uncommitted changes.' >&2; exit 2; }
revision=$(git rev-parse HEAD)
test "$revision" = "$(git rev-parse origin/main)" || { echo 'Main differs from origin/main.' >&2; exit 2; }

query() {
  label=$1
  shift
  if ! query_result=$("$@"); then
    echo "Could not check $label; no resource was created." >&2
    exit 1
  fi
}
query 'target cluster' gcloud container clusters describe cache-guard-test --project="$project" --region="$region" --format='value(status)'
test "$query_result" = RUNNING || { echo 'The reviewed GKE cluster is not running.' >&2; exit 1; }
query 'image repository' gcloud artifacts repositories list --project="$project" --location="$region" --format='value(name)'
if printf '%s\n' "$query_result" | grep -Fxq -e "$repository" -e "projects/$project/locations/$region/repositories/$repository"; then
  echo 'The isolated image repository already exists; inspect it before retrying.' >&2
  exit 1
fi
query 'staging address' gcloud compute addresses list --project="$project" --regions="$region" --filter="name=$address" --format='value(name)'
test -z "$query_result" || { echo 'The staging address already exists; inspect it before retrying.' >&2; exit 1; }

created=0
trap 'status=$?; if [ "$status" -ne 0 ] && [ "$created" -eq 1 ]; then echo "Staging setup stopped after creating resources. Run scripts/staging/teardown.sh $project." >&2; fi' EXIT
echo "Creating the isolated image repository for revision $revision."
created=1
gcloud artifacts repositories create "$repository" --project="$project" --location="$region" --repository-format=docker --immutable-tags --quiet
image_repo="$region-docker.pkg.dev/$project/$repository"
gcloud builds submit . --project="$project" --region="$region" --config=deploy/staging/cloudbuild.yaml \
  --substitutions="_IMAGE_REPO=$image_repo,_SOURCE_REVISION=$revision" --quiet

for image in edge coordinator; do
  query "digest for $image" gcloud artifacts docker images list "$image_repo/$image" --project="$project" --include-tags --format=json
  printf '%s\n' "$query_result" | python3 -c 'import json, re, sys
revision, image = sys.argv[1:]
rows = json.load(sys.stdin)
matches = [row["version"] for row in rows if revision in row.get("tags", []) and re.fullmatch("sha256:[a-f0-9]{64}", row.get("version", ""))]
if len(matches) != 1:
    raise SystemExit("Expected exactly one immutable digest for " + image + " at " + revision)
print(image.upper() + "_IMAGE=" + image + "@" + matches[0])' "$revision" "$image_repo/$image"
done

gcloud compute addresses create "$address" --project="$project" --region="$region" --network-tier=PREMIUM --ip-version=IPV4 --quiet
query 'reserved staging IPv4' gcloud compute addresses describe "$address" --project="$project" --region="$region" --format='value(address)'
python3 - "$query_result" <<'PY'
import ipaddress, sys
address = ipaddress.IPv4Address(sys.argv[1])
if not address.is_global:
    raise SystemExit('The reserved address is not a public IPv4 address')
print('STAGING_IP=' + str(address))
PY
echo 'Run scripts/staging/teardown.sh with this project when the trial ends.'
