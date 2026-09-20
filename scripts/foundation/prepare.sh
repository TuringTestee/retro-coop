#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
(cd spikes/d02 && cargo +1.95.0 build --locked --release --lib --target wasm32-unknown-unknown)
mkdir -p apps/client/public/generated
cp spikes/d02/target/wasm32-unknown-unknown/release/retro_coop_d02.wasm apps/client/public/generated/
cp spikes/d02/THIRD_PARTY_NOTICES.txt apps/client/public/generated/emulator-notices.txt
python3 spikes/d02/original_fixture.py apps/client/public/generated/diagnostic.nes
