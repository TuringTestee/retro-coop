#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

# Fast repository and deterministic-codec checks; build dependencies before this bounded gate.
preflight_base=${PREFLIGHT_BASE_REF:-origin/main}
if ! preflight_merge_base=$(git merge-base HEAD "$preflight_base"); then
  echo "Pre-flight needs history for $preflight_base; fetch the base/history or set PREFLIGHT_BASE_REF to the available PR base." >&2
  exit 1
fi
git diff --check "$preflight_merge_base" HEAD
git diff --check
git diff --cached --check
sh -n scripts/preflight.sh
sh -n scripts/demo.sh
node --check spikes/d02/demo/app.js
sh -n spikes/d02/run_network_probe.sh
bash -n spikes/d02/ci_job.sh
node --check spikes/d02/realtime-worker.js
python3 -c 'import ast, pathlib; root=pathlib.Path("spikes/d02"); [ast.parse(p.read_text()) for p in [*root.glob("*.py"), *(root/"demo").glob("*.py"), *pathlib.Path("scripts/foundation").glob("*.py"), *pathlib.Path("scripts/rooms").glob("*.py"), *pathlib.Path("scripts/peer").glob("*.py"), *pathlib.Path("scripts/featured").glob("*.py"), *pathlib.Path("scripts/staging").glob("*.py")]]'
(cd spikes/d02 && python3 original_fixture.py fixture.local.nes && cargo +1.95.0 fmt --check && cargo +1.95.0 test --locked --offline --release --lib)
node spikes/d02/test_realtime_audio.cjs
node spikes/d02/test_realtime_scheduler.cjs
node spikes/d02/test_realtime_protocol.cjs
python3 -m unittest discover -s spikes/d02 -p 'test_verify_realtime.py'
python3 -m unittest discover -s spikes/d02 -p 'test_ci*.py'
npm run typecheck
npm test
echo 'Pre-flight passed (repository hygiene and D02 codec regression tests).'
