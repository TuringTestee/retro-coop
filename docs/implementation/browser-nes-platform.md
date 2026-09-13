# Browser NES platform delivery plan

Build and test the browser's ability to run the same game in sync before building the full lobby experience. Then connect local play, public discovery, two-player networking, and chat into one tested journey. This plan is revisable; the companion design defines the intended behavior.

## Governing design and readiness

Use [the design and AC-01 through AC-12](../../docs/design/browser-nes-platform.md) as the scope reference. This is a planning candidate awaiting careful user review. No builders or child issues are dispatched by this PR. Repository setup PR [#1](https://github.com/TuringTestee/retro-coop/pull/1) merged at `57396904d1679b5a87550a0cd89df1fee6ae8ccb`; this planning PR targets main. Checks and local review must identify the actual base/head under review.

Before project breakdown, obtain approval of the exact reviewed planning revision and confirm it has merged. The featured variant's missing specification and rights remain explicit blockers for content-dependent breakdown. If that information is still missing, a reviewed amendment must bound an infrastructure-only iteration before any partial breakdown; do not silently redefine the public release. Later dispatch requires merged breakdown documents and verified live issue ownership/dependencies.

## Effort, roles, and feasibility gate

Assume one developer with coding-agent support and an independent reviewer for each substantive PR. The developer owns frontend, networking, deployment, QA, and support; the user supplies or approves the featured game's identity/rules and rights. This is a capacity bottleneck, not multiple staffed teams. Target 8–12 weeks after approvals for the platform, conditional on a supplied playable game. New game development is unestimated and excluded from this timeline until specified.

Spend at most five developer days on the initial emulator/network feasibility package. Pin a candidate JSNES revision and build an adapter prototype using only authorized test fixtures. Measure canonical save/restore, cross-browser replay, snapshot contents/size, worker/audio integration, rewind memory, replay speed, and two-peer input delay under the design's network profile. Audit immutable ROM copies in CPU/PPU/mapper snapshots; removing a top-level ROM field is insufficient.

Pass only with identical canonical hashes across the browser matrix for ten minutes of identical input, identical replay after restore, a safe dynamic-state encoding, and the 10-second/32 MiB rewind target on the candidate supported game. Capture reference hardware and versions. Without the actual featured title this establishes infrastructure feasibility only; repeat content compatibility before its package can pass. If five days do not produce evidence, record the failure and realign core, scope, or schedule. Do not assume JSNES API availability proves determinism or switch to streaming without alignment.

## Work packages and dependencies

These are delivery packages for later issue breakdown, not assignments or live child issues. Roles denote responsibility held by the developer unless stated otherwise.

| Package | Outcome and dependencies | Responsible role | Completion evidence |
|---|---|---|---|
| P0 Content definition | Resolve variant rules, artifact, two-player interaction, rights and attribution; user input required. | Product/content owner with developer | Reviewed design amendment and reproducible authorized artifact; AC-04 content prerequisites. |
| P1 Feasibility | Prove deterministic adapter, safe checkpoint codec, rewind and basic peer sync after approved breakdown. Uses authorized fixtures; final content proof depends on P0. | Browser/network engineer | Five-day experiment report and repeatable replay/network measurements; technical basis for AC-05–07. |
| P2 Foundation and local play | Create TypeScript client/service workspace, pinned builds, worker/audio/input boundary, local ROM validation, saves, filters, accessible controls, and fast tests. Depends on P1. | Full-stack engineer | Real-browser local play and persistence proof; AC-02, AC-07–08 local portions. |
| P3 Directory and lifecycle | Public/unlisted creation, live listings, guest sessions, atomic slots, ready state, invitation controls, expiry and moderation. Depends on P2 contracts. | Backend/frontend engineer | Multi-client lifecycle and authorization tests; AC-01–03, AC-09–10 coordinator portions. |
| P4 Shared gameplay | Match fingerprints; connect WebRTC; start barriers; delayed inputs; hashes; pause/resync; coordinated restore/rewind; reconnect. Depends on P1–P3. | Network engineer | Browser matrix, fault injection, dynamic-state audit and direct/forced-TURN proof; AC-03, AC-05–07, AC-09, AC-11 networking portions. |
| P5 Social and featured journey | Text, push-to-talk/mute, permanent featured entry and authorized distribution manifest. Depends on P0, P3, P4; text can be implemented after P3. | Frontend/content engineer | Zero-player catalog journey, two-person demo, permissions/abuse tests; AC-04, AC-08, AC-10. |
| P6 Launch validation | Staging, load/cost measurement, admission and relay quotas, telemetry/retention, abuse runbook, rollback/recovery, accessibility and beta rehearsal. Depends on P2–P5. | Developer/operator plus independent reviewer | AC-01–12 coverage report, current prices and measured usage, operational rehearsal and launch checklist evidence. |

The critical path is approval → breakdown → P1 → P2 → P3 → P4 → P5 → P6, with P0 required before committing content-dependent issues and final P1 content compatibility. Approximate allocation: one week feasibility, two weeks local play/foundation, one to two weeks lobbies, two to three weeks networking/recovery, one week social/content integration, and one to two weeks hardening. Overlap only independent work with satisfied prerequisites; agent concurrency does not remove review and merge gates. Reassess at P1 and P4 instead of compressing validation to meet a date.

## Verification strategy

The repository currently has no application code or product tests. For this documentation candidate, inspect links, acceptance coverage, scope consistency, and explicit unknowns. Run the README's `timeout 60s sh scripts/preflight.sh`, defined in `scripts/preflight.sh`, and the existing CI; do not claim runtime evidence for a plan.

As executable code arrives, evolve pre-flight with focused fast type/schema checks and deterministic short fixtures, keeping the entire command below 60 seconds. Presubmit must enforce a shared 30-minute wall-clock deadline across all jobs and retries; preserve the existing single-job deadline until a proven shared deadline exists. Pin CI dependencies. Choose unit/integration/browser tooling during P2 and document exact commands in README.

Presubmit coverage must include canonical serialization and malformed input, matching/mismatching fingerprints, atomic joins and authorization, privacy of outbound traffic, coordinated epoch changes, local save compatibility, and the ten-minute network session matrix. Run browser pairs concurrently only where resource limits permit; record actual full-run time. If the budget is threatened, optimize infrastructure or redundant setup without deleting essential acceptance. Test forced TURN and direct connection in staging with credentials scoped to the run.

For visual changes, capture and inspect matched before/after screenshots or clips from the real application, including empty directory, full/waiting sessions, mismatch, reconnect, settings and gameplay. A new page uses the existing empty state as the before evidence. Check keyboard focus and microphone denial with actual browser interaction.

After merge, run a separately budgeted two-hour network/rewind/reconnect soak in staging, owned by the developer/operator. File failures against the relevant package and record results; pending post-submit tests do not replace essential presubmit proof or hold unrelated PRs. Before public launch, resolve any observed launch-blocking failures.

Each implementation PR records exact commit/build, relevant AC IDs, test settings, actual output and duration, inspected visuals where relevant, pre-flight result, CI URL and elapsed time, and any post-submit plan. Use a fresh local reviewer in a separate detached worktree with only the PR URL and review instructions. Publish its report per [the handoff contract](../../tooling/vaseline/docs/review-handoff.md). A bot/person reviews externally and a separate bot/person merges; confirm integration before dependent work.

## Hosting and operational delivery

At P6 compare available HTTPS/static hosting, one small Node coordinator, and TURN service prices/quotas using current provider documentation. The $50 target/$100 ceiling is not a price quote. Build a cost worksheet from fixed service charges plus measured catalog egress, logs and TURN bytes at 20 concurrent sessions/100 directory connections, including voice and relay-only use. Model monthly session-hours explicitly; concurrent capacity is not a monthly usage estimate. Start beta at a lower admission limit if measured spend demands it and realign any change to the accepted capacity.

Provision only after selecting a plan that can enforce the budget. Configure relay credentials with short expiries, allocation/bandwidth quotas, directory/signaling limits, TLS/origin checks and log redaction. Exercise budget exhaustion: new sessions receive a capacity explanation, relay-only users never silently disclose their address by falling back to direct, and the operator receives a content-free alert.

Deploy immutable versioned client/core assets to staging first and retain previous versions for active lobbies. Rehearse rolling back the client and coordinator and restoring catalog/configuration; a coordinator restart intentionally closes ephemeral lobbies. Document a maintenance message and the accepted interruption. Keep secrets outside source control and test the chosen provider's configuration recovery mechanism. Do not back up chat, user ROMs, or cloud saves because this release does not persist them.

Start a limited beta only after AC-01–12 evidence, featured-title provenance, cost enforcement, and the reviewed operational runbook are complete. The operator reviews redacted health and abuse signals daily during the initial beta and assesses the first two weeks before increasing admission. Deployment authorization and exact provider choice remain separate from this planning PR.

## Risks and reassessment

| Risk | Reduction and decision point |
|---|---|
| Unknown featured game or rights | P0 records actual rules/artifact/permission. No launch, guessed game, or automatic substitution. New game work changes the estimate. |
| Incomplete emulator snapshots or nondeterminism | P1 tests CPU/PPU/mapper state and replay across browsers. Stop at the five-day bound and realign if proof fails. |
| ROM leakage in snapshots | Explicit dynamic schema and cartridge-region audit plus outbound fixtures before enabling any peer transfer. |
| Input delay/background throttling harms play | P1/P4 measure real browser/network behavior; pause clearly, then reassess supported conditions before launch. |
| Relay use exceeds budget | Current-price worksheet, metered session-hours, enforced quota/admission tests before provisioning. |
| Anonymous abuse | Server authority, revocation, rate limits, operator takedown and modest beta capacity; accounts require later alignment. |
| Schedule exceeds one developer's capacity | Reassess after P1/P4; preserve the accepted journey or explicitly renegotiate scope. |

Future iteration plans remain coarse: rollback after deterministic correctness and latency measurements; more titles after per-mapper replay and rights validation; spectators after a topology/cost study; accounts/cloud saves after demand and data-lifecycle review. None are prerequisites silently added to this release.
