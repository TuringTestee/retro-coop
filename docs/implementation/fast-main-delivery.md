Audience: Agent

# Fast main delivery

A passing main build should deploy the exact checked code to the Retro Coop website automatically. The release gate now uses the current Chromium host-and-join journey and deployment image checks.

## Direction and ownership

The owner requested automatic delivery to the public site, a short release gate, and live testing with rollback in September 2026. On 2026-10-02, after the lobby redesign made old scripts fail, the owner directed us to remove obsolete tests, retain essential checks, and use one browser engine. This replaces the original three-browser matrix and long qualification workflow. The short live game check reuses the maintained Chromium journey. The [verification strategy](browser-nes-platform.md#verification-strategy) owns the current test policy.

## Delivery path

1. Build the client and native core, run preflight, and verify the public entrypoint in Chromium. The browser journey hosts and joins both public and password-protected lobbies, loads a diagnostic ROM, and checks synchronized play. UI, layout, controls, and recovery checks for the current interface run alongside it.
2. Build and validate the native ARM64 deployment images from the same revision. Record their checksums and publish them as artifacts of the main run.
3. Start deployment only after build, browser journey, and image checks pass. The deployment job checks that its source is still the head of main, assumes the main-scoped AWS role with temporary credentials, and publishes only the checked images and source bundle.
4. Deploy through `einaregilsson/beanstalk-deploy@v21`, then verify Elastic Beanstalk health, HTTPS, and the served revision. Two fresh Chromium processes use the public website to host, join, and play for 30 seconds, record frame rate and round-trip latency, then verify matching paused state and resume. A failed build gate leaves the current site running. A failed deployment or live game check reports the prior and attempted versions and restores the prior healthy version when needed; the workflow remains failed and reports any main/live mismatch.

A pull request labeled `release-gate-proof` runs the same release checks before merge, without deploying. Main deployments are serialized and cannot publish a superseded head. A merge is complete only after the live site serves that main revision. Deferred voice and host recovery remain tracked separately.
