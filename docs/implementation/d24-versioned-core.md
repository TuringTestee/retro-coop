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

The standalone local-page asset probe is retired because its old entrypoint is absent from the current UI. Its [historical source](https://github.com/TuringTestee/retro-coop/blob/fe5cf26dc52b258826a0491be5d099bf21a97074/scripts/aws_eb/versioned_core_smoke.py) remains available with the recorded results below. Current build, release and live checks follow the [verification strategy](browser-nes-platform.md#verification-strategy) and [deployment operations](d24-aws-eb-operations.md). Those checks do not claim to repeat every old loaded-tab publication/rollback scenario.

The [actual browser regression](https://github.com/TuringTestee/retro-coop/blob/a8eed786407c16b16dcbac2d8f4ad2679c91661a/docs/implementation/d24-versioned-core/browser.json) passed in4.28s; the [existing foundation/settings/storage workload](https://github.com/TuringTestee/retro-coop/blob/a8eed786407c16b16dcbac2d8f4ad2679c91661a/docs/implementation/d24-versioned-core/foundation.json) passed in49.45s. The [baseline failure](https://github.com/TuringTestee/retro-coop/blob/a8eed786407c16b16dcbac2d8f4ad2679c91661a/docs/implementation/d24-versioned-core/before-failure.txt) records the wrong core hash. Its reproduction is archived with that historical result; the retired probe is preserved only through the historical source above. The [candidate manifest](https://github.com/TuringTestee/retro-coop/blob/a8eed786407c16b16dcbac2d8f4ad2679c91661a/docs/implementation/d24-versioned-core/candidate.json) pins source and approval. These are author checks; CI and independent acceptance remain pending.

After integrating voice PR56, [update/rollback](https://github.com/TuringTestee/retro-coop/blob/a8eed786407c16b16dcbac2d8f4ad2679c91661a/docs/implementation/d24-versioned-core/integrated-assets.json) passed in4.64s and [full Chromium voice recovery](https://github.com/TuringTestee/retro-coop/blob/a8eed786407c16b16dcbac2d8f4ad2679c91661a/docs/implementation/d24-versioned-core/integrated-voice.json) passed in3.82s. This verifies voice still uses the versioned worker/core without reloading or importing its timeline. The merged base and exact source are in the manifest.
