Audience: Agent

# Stable emulator assets during updates

An already loaded client must keep using its original emulator after a deployment. The worker now imports the emulator as a Vite asset, so each distinct binary gets a content-specific URL. Staging must retain previous hashed assets when publishing a new index or rolling back.

This is a bounded preparation slice of D24/#28 under approved epic #2 and planning PR #3, approved head `2e8adfcd3259f5bdffdc9a13ef9b983f78cfb965`, governing merge `ecf6bd4c7443526f0a163b721a351c854ee90fd4`. The approved architecture requires immutable versioned client/core assets and retention for existing sessions. No hosting is provisioned by this slice. HTTPS, coordinator/proxy configuration, TURN access on independent networks, enforceable costs and deployment rollback remain D24 acceptance work.

## Cause and shared ownership

Previously the worker fetched `/generated/retro_coop_d02.wasm`. Updating that file changed the core underneath a loaded page whenever it next created a worker. The reproduction retained the old page, replaced the static release, then selected the same local cartridge: the page reported the new core SHA-256 instead of the original one.

`scripts/foundation/prepare.sh` now places generated WASM beside worker source, outside the public copy directory; it removes only its previous unversioned generated output. The worker's `?url` import lets Vite own content naming and dependencies. There is no second hashing algorithm, manifest resolver or runtime version selector. Runtime fingerprinting still hashes the downloaded bytes and save compatibility remains tied to that actual core identity. The existing foundation probe discovers the single built WASM asset and continues testing cancellation against its request.

## Static publication contract

Publish new hashed assets before changing the current HTML. If an asset URL already exists, its bytes must be identical; retain old assets for active clients. Roll back by restoring the previous HTML while retaining both generations of assets. Do not deploy by deleting the old assets directory or overwriting content at an existing URL. The staging provider/configuration must implement and verify this contract before D24 is complete; this PR supplies the immutable build output and an actual browser regression, not a production deployment command.

## Verification

Prepare and build using `sh scripts/foundation/prepare.sh` and `npm run build`. Run `python scripts/aws_eb/versioned_core_smoke.py --chrome --output /tmp/versioned-core.json` with Python Playwright1.58 and Chrome installed; omit `--chrome` for bundled Chromium. The probe copies application sources into an owned temporary directory, builds two valid WASM variants (an inert custom section changes only binary identity), and publishes them through a local static server. Original cartridges are local test fixtures; no ROM, save or microphone content leaves the machine.

The actual browser loads a cartridge in an old tab after publication, a new tab, a rollback tab, and the still-loaded new tab after rollback. Each must report its correct core SHA-256 and render frames. The game stays muted through its own UI setting. This is client/asset consistency proof, not public-network or multiplayer acceptance. There is no visible product change requiring a screenshot comparison.

The focused regression remains separate from the README preflight; current scheduling and budgets follow the governing [verification strategy](browser-nes-platform.md#verification-strategy). Existing foundation/storage tests must pass with the new asset path; their scope is unchanged. Exact candidate/proof revisions and measured results are recorded with the PR. Root remains the sole merge owner after fresh independent acceptance and required CI.

The [actual browser regression](d24-versioned-core/browser.json) passed in4.28s; the [existing foundation/settings/storage workload](d24-versioned-core/foundation.json) passed in49.45s. The [baseline failure](d24-versioned-core/before-failure.txt) records the wrong core hash; run its adjacent reproduction from the repository root to repeat the old-source case. The [candidate manifest](d24-versioned-core/candidate.json) pins source and approval. These are author checks; CI and independent acceptance remain pending.

After integrating voice PR56, [update/rollback](d24-versioned-core/integrated-assets.json) passed in4.64s and [full Chromium voice recovery](d24-versioned-core/integrated-voice.json) passed in3.82s. This verifies voice still uses the versioned worker/core without reloading or importing its timeline. The merged base and exact source are in the manifest.
