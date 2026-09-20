#!/bin/sh
# Build the local player and serve it on this computer. Ctrl-C stops the demo.
set -eu
cd "$(dirname "$0")/../spikes/d02"
cargo +1.95.0 build --locked --release --lib --target wasm32-unknown-unknown
printf '\nOpen http://127.0.0.1:8765/demo/ and choose your ROM. Ctrl-C stops the demo.\n'
exec python3 -m http.server 8765 --bind 127.0.0.1
