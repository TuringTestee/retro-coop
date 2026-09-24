#!/bin/sh
set -eu

repo_root=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
preferences="$repo_root/.agents/preferences.local.json"

if [ -f "$preferences" ]; then
  exec node "$repo_root/tooling/vaseline/cli/vaseline.js" review TuringTestee/retro-coop --preferences "$preferences" "$@"
fi

exec node "$repo_root/tooling/vaseline/cli/vaseline.js" review TuringTestee/retro-coop "$@"
