# Fast main delivery

A successful main build should reach the existing Retro Coop website automatically. Shared play gets a 30-second release test, and the live site gets a host-and-guest check with automatic rollback if that check fails. Longer soak tests run after release and report regressions without delaying every deployment.

## Current evidence and target

- Main CI currently runs 600-second gameplay and network workloads for Chrome–Chrome, Firefox–Firefox, and Chrome–Firefox. The `main` push at `4466a05` was still running more than 12 minutes after it started. PR build, entrypoint and native ARM64 image checks had passed.
- The same commit's ARM64 image job passed, an exact-source bundle was produced, and the existing single-instance Elastic Beanstalk environment deployed `main-4466a05f1f63`. Two live browser tabs joined one public room, prepared, played more than 120 shared frames, and showed numeric FPS and ping without page errors.
- Target: the gameplay release workload itself is 30 seconds per browser pair, with a short CI pipeline and a CD workflow that normally finishes within five minutes after eligible artifacts are available. Record actual timings; do not mark a longer run as meeting the target.

## Delivery sequence

1. Keep `scripts/preflight.sh` and the relevant real-browser journey on pull requests. On main, run 30 seconds of synchronized gameplay for all three browser pairs. Check both players' frame progress, state hashes, controller input, pause, and fatal page errors. Keep direct and forced-relay smoke coverage. Reduce setup and tests around the workload so main's release gate does not inherit the full core qualification. Preserve the separate full suite as a scheduled and manually runnable post-release workflow with its existing evidence artifacts. Update `docs/implementation/browser-nes-platform.md`, `README.md`, and the CI budget tests to name the new owner of each test.
2. Publish exact native ARM64 images as a main CI artifact. Keep checksum, source-commit, architecture, image-digest and client/core asset checks. The fast main gate must pass before CD starts. A failed gate must leave the existing website version running and report the unpublished main commit.
3. Add a GitHub Actions CD workflow triggered by successful main CI. Use GitHub OIDC to assume a dedicated AWS role whose trust is limited to this repository's main branch. Give it the permissions required for the existing ECR repository, EB application/environment, release bucket, deployment checks and rollback; keep credentials out of GitHub secrets and source. Before deploying, verify the CI source SHA is still the current main head. Serialize deployments without cancelling an update in progress.
4. Reuse `scripts/aws_eb/build_release.py` and `scripts/aws_eb/website.py deploy --update` so CD deploys the exact CI images to `retro-coop.atobot.cloud` on the existing one-machine environment. Record prior and new EB versions. Aim for under five minutes from eligible artifact to completed live check; measure packaging, EB update and verification separately. Optimize observed bottlenecks rather than removing source or live integrity checks.
5. After EB reports Ready/Green, exercise the public HTTPS URL in two fresh browser contexts: claim an empty included room, join from the second context, prepare, start, run synchronized frames for 30 seconds, see numeric FPS/ping and no direct-path relay notice, then leave. Verify the served source/version and health. If deploy or live check fails, restore the previous EB version, verify its health and HTTPS endpoint, and fail CD with both versions and the failure reason. Publish deployment status and a readable run summary. A rollback creates a visible main/live mismatch to repair, rather than a false green sync claim.
6. Run the existing 600-second multi-browser and broader core qualification after release on a schedule and on demand. Preserve evidence and report failures. A confirmed live regression triggers rollback and a repair PR; a flaky infrastructure failure does not silently roll back healthy players.

## Acceptance

- A reviewed main commit with passing fast CI automatically reaches the website without a local operator command. The public site's version matches that commit after CD succeeds.
- The three release browser pairs each execute a measured 30-second gameplay interval, with the same critical sync and recovery assertions. The old ten-minute runs are absent from required CI/CD checks and remain runnable separately.
- CD assumes AWS access through the main-scoped OIDC role, deploys only an exact checked artifact, never overlaps updates, and records elapsed time. A healthy run completes in under five minutes under normal service conditions.
- A deliberately failing live check restores the prior working EB version and makes the deployment red. A failing fast CI check does not start CD. A newer main head prevents deployment of a stale run.
- The post-release full suite can run without blocking a new main deployment and retains its browser/core evidence for debugging.

## Recovery and limits

Elastic Beanstalk may take longer than five minutes during AWS service or instance recovery. CD must report that elapsed time honestly and finish or roll back safely, not cancel an in-progress EB update at an arbitrary deadline. A failed main commit or rolled-back release means main and live differ until a repair is merged and deployed; the workflow must make that drift visible. Existing rooms close when the single EC2 instance restarts for a new version or rollback.
