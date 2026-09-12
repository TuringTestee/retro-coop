#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

# Bootstrap hygiene only. Add fast product checks when executable features exist.
git diff --check
git diff --cached --check
sh -n scripts/preflight.sh
echo 'Pre-flight passed (repository hygiene; no product tests yet).'
