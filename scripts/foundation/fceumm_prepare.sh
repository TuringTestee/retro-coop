#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
if [ "${RETRO_COOP_PREBUILT_FCEUMM:-0}" != 1 ]; then
  if ! command -v emcc >/dev/null 2>&1; then
    sdk="${XDG_CACHE_HOME:-$HOME/.cache}/retro-coop/emsdk-6.0.11"
    if [ ! -d "$sdk/.git" ]; then
      mkdir -p "$(dirname "$sdk")"
      git init "$sdk"
      git -C "$sdk" fetch --depth 1 https://github.com/emscripten-core/emsdk.git 96c657fc60920d2a6a82318aa50e0abf82749604
      git -C "$sdk" checkout --detach FETCH_HEAD
    fi
    "$sdk/emsdk" install 6.0.11
    "$sdk/emsdk" activate 6.0.11
    . "$sdk/emsdk_env.sh"
  fi
  python3 scripts/foundation/fceumm_build.py
fi
test -s apps/client/src/generated/fceumm.mjs
test -s apps/client/src/generated/fceumm.wasm
test -s apps/client/public/generated/fceumm-license.txt
test -s apps/client/public/generated/fceumm-source.txt
