# Fast main delivery

A successful main build should reach the existing Retro Coop website automatically. The main workflow will use `einaregilsson/beanstalk-deploy@v21` for the release. Shared play keeps its 30-second release test; longer soak tests run separately.

## Source and delivery ownership

The user requested on 2026-09-25: “the release gate should be just 30s long, 10 min is too long”; “setup CICD”; “CI should be short, and CD should be also under 5min”; “add post release testing” with rollback when needed; and “keep main CD synced with https://retro-coop.atobot.cloud/”. After the custom CD workflow failed, the user directed us to remove it and use `einaregilsson/beanstalk-deploy@v21`, following their existing GitHub workflow examples. Environment-specific account IDs and ARNs must come from GitHub configuration or AWS at runtime, not tracked workflow or release code. The [verification strategy](browser-nes-platform.md#verification-strategy) owns the test policy.

The selected [Retro Coop delivery Project](https://github.com/orgs/TuringTestee/projects/1) has these committed draft cards. Root is dispatcher and single delivery owner; each card's builder uses `issue-resolver` in an isolated worktree, then an independent reviewer accepts its PR. A card is ready only when its named dependency is merged and checked.

| Card | Dependency | Acceptance owner |
|---|---|---|
| Fast 30-second main release gate (`PVTI_lADOE0HVec4BkDjlzg8znF4`) | This reviewed, merged plan | Root: measured browser-pair evidence and CI timing |
| Automatic main deployment to existing AWS site (`PVTI_lADOE0HVec4BkDjlzg8znG4`) | Fast gate integrated, dedicated OIDC role | Root: exact-source deploy and elapsed time |
| Integrated live host-and-guest release check (`PVTI_lADOE0HVec4BkDjlzg8znHk`) | Automatic CD integrated | Root: public two-browser proof and rollback rehearsal |
| Post-release ten-minute qualification (`PVTI_lADOE0HVec4BkDjlzg8znIQ`) | Fast gate integrated | Root: scheduled/manual evidence and failure report |

The integrated release gate is the live host-and-guest card: it may close only after all four cards are integrated and the public site proves the requested player journey. Project fields hold status, priority, next action and blockers; this table records only dependency and acceptance ownership.

## Current evidence and target

- Main CI currently runs 600-second gameplay and network workloads for Chrome–Chrome, Firefox–Firefox, and Chrome–Firefox. The `main` push at `4466a05` was still running more than 12 minutes after it started. PR build, entrypoint and native ARM64 image checks had passed.
- The same commit's ARM64 image job passed, an exact-source bundle was produced, and the existing single-instance Elastic Beanstalk environment deployed `main-4466a05f1f63`. Two live browser tabs joined one public room, prepared, played more than 120 shared frames, and showed numeric FPS and ping without page errors.
- Target: the gameplay release workload itself is 30 seconds per browser pair, with a short CI pipeline and a CD workflow that normally finishes within five minutes after eligible artifacts are available. Record actual timings; do not mark a longer run as meeting the target.

## Delivery sequence

1. Keep `scripts/preflight.sh` and the relevant real-browser journey on pull requests. On main, run 30 seconds of synchronized gameplay for all three browser pairs. Check both players' frame progress, state hashes, controller input, pause, and fatal page errors. Keep direct and forced-relay smoke coverage. Reduce setup and tests around the workload so main's release gate does not inherit the full core qualification. Preserve the separate full suite as a scheduled and manually runnable post-release workflow with its existing evidence artifacts. Update `docs/implementation/browser-nes-platform.md`, `README.md`, and the CI budget tests to name the new owner of each test.
2. Publish exact native ARM64 images as a main CI artifact. Keep checksum, source-commit, architecture, image-digest and client/core asset checks. The fast main gate must pass before CD starts. A failed gate must leave the existing website version running and report the unpublished main commit.
3. Delete the separate custom `.github/workflows/deploy.yml`. Add one final deployment job to the existing main CI workflow, after its build and browser checks pass. Give that job the same run's checked native ARM64 image artifact. Keep pull-request checks, but never run the deployment job on a pull request. Serialize main deployments without cancelling an update in progress.
4. In the final job, assume the existing main-only AWS role through OIDC, with its ARN stored as a GitHub secret. Derive the AWS account and release bucket from AWS at runtime; obtain the existing application, environment and public URL from GitHub configuration. Publish the exact checked images and source bundle, then call `einaregilsson/beanstalk-deploy@v21` with the bundle, a source-derived version label, and the temporary AWS access key, secret key and session token. Reuse an existing version on retry. Do not call the broad `website.py deploy --update` provisioning path during routine CD. Record prior and new EB versions, Ready/Green health, HTTPS result and elapsed time. Aim for under five minutes after the build gate passes.
5. After EB reports Ready/Green, exercise the public HTTPS URL in two fresh browser contexts: claim an empty included room, join from the second context, prepare, start, run synchronized frames for 30 seconds, see numeric FPS/ping and no direct-path relay notice, then leave. Verify the served source/version and health. If deploy or live check fails, restore the previous EB version, verify its health and HTTPS endpoint, and fail CD with both versions and the failure reason. Publish deployment status and a readable run summary. A rollback creates a visible main/live mismatch to repair, rather than a false green sync claim.
6. Run the existing 600-second multi-browser and broader core qualification after release on a schedule and on demand. Preserve evidence and report failures. A confirmed live regression triggers rollback and a repair PR; a flaky infrastructure failure does not silently roll back healthy players.

## Main-only credential bootstrap

The AWS role accepts only this repository's main branch; `deploy/aws-eb/github-cd-role.yaml` owns the exact OIDC subject. A pull-request run cannot assume it. The action-based deployment therefore has two acceptance stages:

1. Before merging the enabling workflow, independently review the action inputs, same-run source and image selection, OIDC credential handoff, failure handling and absence of tracked account IDs or ARNs. Require green PR checks and a real bundle made from a successful main build. Record the current healthy EB version. This establishes readiness; it does not claim a live CD result.
2. Merge the reviewed workflow. Its first successful main run must deploy that same commit through the action. Keep the automatic-deployment card **In Review** until the run records the exact source SHA, previous and new EB versions, Ready/Green health, public HTTPS response and elapsed time from build-gate completion. Compare the live version with main before closing the card. On failure, inspect and restore the previous healthy EB version when needed, then repair the workflow in a reviewed PR.

This sequence supplies live evidence at the first point where main-only OIDC access exists. It introduces no static AWS key. The action does not roll back by itself; the integrated live-check card owns automated browser acceptance and rollback. Until then, a failed release needs operator recovery and remains red.

## Acceptance

- A reviewed main commit with passing fast CI automatically reaches the website without a local operator command. The public site's version matches that commit after CD succeeds.
- The three release browser pairs each execute a measured 30-second gameplay interval, with the same critical sync and recovery assertions. The old ten-minute runs are absent from required CI/CD checks and remain runnable separately.
- CD assumes AWS access through the main-scoped OIDC role, deploys only an exact checked artifact, never overlaps updates, and records elapsed time. A healthy run completes in under five minutes under normal service conditions.
- A deliberately failing live check restores the prior working EB version and makes the deployment red. A failing fast CI check does not start CD. A newer main head prevents deployment of a stale run.
- The post-release full suite can run without blocking a new main deployment and retains its browser/core evidence for debugging.

## Recovery and limits

Elastic Beanstalk may take longer than five minutes during AWS service or instance recovery. CD must report that elapsed time honestly and finish or roll back safely, not cancel an in-progress EB update at an arbitrary deadline. A failed main commit or rolled-back release means main and live differ until a repair is merged and deployed; the workflow must make that drift visible. Existing rooms close when the single EC2 instance restarts for a new version or rollback.
