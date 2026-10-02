# Fast main delivery

A passing main build should deploy the exact checked code to the Retro Coop website automatically. The release gate now uses the current Chromium host-and-join journey and deployment image checks.

## Direction and ownership

The owner requested automatic delivery to the public site and a short release gate in September 2026. The original plan required three browser pairs and a scheduled long qualification. On 2026-10-02, after the lobby redesign made those old scripts fail, the owner directed us to remove the obsolete tests, retain only essential checks, and use one browser. This newer direction supersedes the test matrix and post-release workflow in the original plan. The [verification strategy](browser-nes-platform.md#verification-strategy) owns the current test policy.

## Delivery path

1. Build the client and native core, run preflight, and verify the public entrypoint in Chromium. The browser journey hosts and joins both public and password-protected lobbies, loads a diagnostic ROM, and checks synchronized play. UI, layout, controls, and recovery checks for the current interface run alongside it.
2. Build and validate the native ARM64 deployment images from the same revision. Record their checksums and publish them as artifacts of the main run.
3. Start deployment only after build, browser journey, and image checks pass. The deployment job checks that its source is still the head of main, assumes the main-scoped AWS role with temporary credentials, and publishes only the checked images and source bundle.
4. Deploy through `einaregilsson/beanstalk-deploy@v21`, then verify Elastic Beanstalk health, HTTPS, and the served revision. A failed gate leaves the current site running. A failed deployment must report the prior and attempted versions and restore the prior healthy version when needed.

A pull request labeled `release-gate-proof` runs the same release checks before merge, without deploying. Main deployments are serialized and cannot publish a superseded head. A merge is complete only after the live site serves that main revision. Deferred voice and host recovery remain tracked separately.
