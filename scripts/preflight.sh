#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

# Fast repository and deterministic-codec checks; build dependencies before this bounded gate.
git diff --check
git diff --cached --check
sh -n scripts/preflight.sh
python3 -c 'import ast, pathlib; root=pathlib.Path("spikes/d02"); [ast.parse(p.read_text()) for p in [*root.glob("*.py"), *(root/"demo").glob("*.py")]]'
(cd spikes/d02 && python3 original_fixture.py fixture.local.nes && cargo +1.95.0 fmt --check && cargo +1.95.0 test --locked --offline --release --lib)
echo 'Pre-flight passed (repository hygiene and D02 codec regression tests).'
