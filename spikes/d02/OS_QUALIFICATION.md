# Manual OS replay qualification

This workflow runs the original diagnostic through Chrome and Firefox on one Windows or macOS runner. It supplies OS replay, restore and rewind evidence without uploading a private game ROM. Passing runs are initial core evidence, not featured-game, network, voice or release qualification.

After this workflow is merged to the default branch, dispatch `d02-os-qualification.yml` once with `runner=windows-2025` and once with `runner=macos-15`. Each run has one standard runner, a 30-minute total deadline, a 1,200-second browser deadline and no retry extension. Record both actual run IDs and final durations. Neither pending jobs nor a same-OS browser match prove a cross-OS match.

Download `d02-os-windows-2025` and `d02-os-macos-15` artifacts. Run `python verify_results.py browser-os.local.json` on each, then compare the complete `runs[*].hashes` lists across OS artifacts and the Linux reference. Compare ROM hashes, source commits, exact browser versions and WASM hashes first. Different build artifacts must be recorded; do not silently treat them as the same deployment fingerprint. The artifacts expire after seven days, so preserve the non-ROM JSON evidence in the reviewed report when accepting results.

The core/toolchain/dependencies and Playwright are pinned. The workflow installs branded Chrome and the Playwright Firefox build, and records the actual versions rather than claiming they are the same across runners. Build metadata records the OS, architecture and source revision. Generated fixture bytes never leave the runner through uploaded artifacts; only measurements are uploaded.

Manual qualification is separate from PR CI, which retains its existing 30-minute gate. With the official standard-runner rates checked on 2026-09-13, two full 30-minute runs cost at most $2.16 in compute before included minutes: Windows $0.30 and macOS $1.86. This excludes artifact storage and is not a claim of available free quota. Do not schedule repeated runs or use larger runners without reviewing the project budget. See [GitHub runner pricing](https://docs.github.com/en/billing/reference/actions-runner-pricing).
