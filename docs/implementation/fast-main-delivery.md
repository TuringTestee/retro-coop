# Fast main delivery

A successful main build should reach the existing Retro Coop website automatically. Shared play gets a 30-second release test, and the live site gets a host-and-guest check with automatic rollback if that check fails. Longer soak tests run after release and report regressions without delaying every deployment.

## Source and delivery ownership

The user requested on 2026-09-25: “the release gate should be just 30s long, 10 min is too long”; “setup CICD”; “CI should be short, and CD should be also under 5min”; “add post release testing” with rollback when needed; and “keep main CD synced with https://retro-coop.atobot.cloud/”. This plan is a direct response to that request and adds no new player-facing design. The [verification strategy](browser-nes-platform.md#verification-strategy) owns the current and accepted test policy during migration.

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
3. Add a GitHub Actions CD workflow triggered by successful main CI. Use GitHub OIDC to assume a dedicated AWS role whose trust is limited to this repository's main branch. Give it the permissions required for the existing ECR repository, EB application/environment, release bucket, deployment checks and rollback; keep credentials out of GitHub secrets and source. Before deploying, verify the CI source SHA is still the current main head. Serialize deployments without cancelling an update in progress.
4. Reuse `scripts/aws_eb/build_release.py` and `scripts/aws_eb/website.py deploy --update` so CD deploys the exact CI images to `retro-coop.atobot.cloud` on the existing one-machine environment. Record prior and new EB versions. Aim for under five minutes from eligible artifact to completed live check; measure packaging, EB update and verification separately. Optimize observed bottlenecks rather than removing source or live integrity checks.
5. After EB reports Ready/Green, exercise the public HTTPS URL in two fresh browser contexts: claim an empty included room, join from the second context, prepare, start, run synchronized frames for 30 seconds, see numeric FPS/ping and no direct-path relay notice, then leave. Verify the served source/version and health. If deploy or live check fails, restore the previous EB version, verify its health and HTTPS endpoint, and fail CD with both versions and the failure reason. Publish deployment status and a readable run summary. A rollback creates a visible main/live mismatch to repair, rather than a false green sync claim.
6. Run the existing 600-second multi-browser and broader core qualification after release on a schedule and on demand. Preserve evidence and report failures. A confirmed live regression triggers rollback and a repair PR; a flaky infrastructure failure does not silently roll back healthy players.

## Main-only credential bootstrap

The AWS role accepts only this repository's main branch; `deploy/aws-eb/github-cd-role.yaml` owns the exact OIDC subject. A pull-request run cannot assume it, and granting PR branches production access just to make a premerge test possible would break that boundary. The automatic CD workflow therefore has two acceptance stages:

1. Before merging the enabling workflow, independently review its exact-source selection, role policy, recovery path and workflow wiring. Require green PR checks, a deployed-role trust and permission readback, a timed package of an existing successful main CI artifact, and focused failure-path tests. Record the current healthy EB version. This establishes readiness to run on main; it does not claim a live CD result.
2. Merge the reviewed workflow. Its first successful main CI run must assume the role and deploy that same main commit. Keep the automatic-deployment card **In Review** until the workflow records the triggering CI run, exact source SHA, previous and new EB versions, Ready/Green health, public HTTPS response and actual time from CI completion to verification. Compare the live version with the main commit before closing the card. If the run fails or times out, inspect the EB version and health, restore the recorded previous version when needed, publish the failure and repair the workflow in a reviewed PR. Do not report main and live as synchronized while they differ.

This sequence supplies the live integration evidence at the first point where main-only OIDC access exists. It does not weaken the trust rule, introduce a static AWS key or mark the delivery complete based on a PR simulation. The following integrated live-check card adds the automatic two-browser acceptance and rollback; the first bootstrap run retains the existing EB and HTTPS checks and an operator recovery path.

## Acceptance

- A reviewed main commit with passing fast CI automatically reaches the website without a local operator command. The public site's version matches that commit after CD succeeds.
- The three release browser pairs each execute a measured 30-second gameplay interval, with the same critical sync and recovery assertions. The old ten-minute runs are absent from required CI/CD checks and remain runnable separately.
- CD assumes AWS access through the main-scoped OIDC role, deploys only an exact checked artifact, never overlaps updates, and records elapsed time. A healthy run completes in under five minutes under normal service conditions.
- A deliberately failing live check restores the prior working EB version and makes the deployment red. A failing fast CI check does not start CD. A newer main head prevents deployment of a stale run.
- The post-release full suite can run without blocking a new main deployment and retains its browser/core evidence for debugging.

## Recovery and limits

Elastic Beanstalk may take longer than five minutes during AWS service or instance recovery. CD must report that elapsed time honestly and finish or roll back safely, not cancel an in-progress EB update at an arbitrary deadline. A failed main commit or rolled-back release means main and live differ until a repair is merged and deployed; the workflow must make that drift visible. Existing rooms close when the single EC2 instance restarts for a new version or rollback.
