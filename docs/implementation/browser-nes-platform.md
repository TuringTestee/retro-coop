Audience: Agent

# Browser NES platform delivery plan

Build and test the browser's ability to run the same game in sync before building the full lobby experience. Then connect local play, public discovery, two-player networking, and chat into one tested journey. This plan is revisable; the companion design defines the intended behavior.

## Governing design and readiness

Use [the design and AC-01 through AC-16](../../docs/design/browser-nes-platform.md) as the scope reference. The original delivery plan was approved and merged; live status, ownership and dependencies now reside in [epic #2](https://github.com/TuringTestee/retro-coop/issues/2), its child issues and GitHub Project. The [two-game catalog amendment](included-games.md) is the current owner for changed content and discovery behavior and still requires its own reviewed-version approval and merge. Checks and local review must identify the actual base/head under review.

Use [the UI design](../design/browser-nes-ui.md), screens U1–U9 and stories S01–S37, to guide frontend breakdown and acceptance evidence across P2–P6. Its text sketches and author critiques are planning evidence; implementation must still demonstrate both roles, alternate states, keyboard access, and actual browser visuals. The catalog amendment owns the two supplied identities, text-only Game help, license placeholders and remaining runtime qualification.

Before executing changed scope, obtain actual approval of the exact reviewed amendment and confirm its governing documents have merged. The user acts as CEO; the planner acts as architect and owns the actionable epic plan. The orchestrator reads that plan, reconciles child issues, and maintains GitHub Project priorities, dependencies, ownership and status. The two supplied catalog identities and placeholders are resolved; D03, D09 and D11 are integrated, so D19 is eligible after this amendment gate. D19 still must package and boot the exact artifacts, and D20/D21 retain final qualification.

## Effort, roles, and feasibility gate

Assume one developer with coding-agent support and an independent reviewer for each substantive PR. The developer owns frontend, networking, deployment, QA, and support; the user supplied and authorized the two catalog artifacts recorded by the amendment. This is a capacity bottleneck, not multiple staffed teams. The earlier 8–12 week platform estimate is provisional: broad hardware qualification, conversational voice and the fast-start targets expand the work. Use measured issue progress and remaining qualification rather than presenting the earlier date as a renewed commitment. New game development is unestimated and excluded from this timeline until specified.

The initial emulator/network feasibility package had a five-developer-day bound. Its accepted work selected and pinned the current core adapter using authorized fixtures and measured canonical save/restore, cross-browser replay, snapshot contents/size, worker/audio integration, rewind memory, replay speed and two-peer input delay. Immutable ROM-copy auditing remains part of state evidence; removing a top-level ROM field alone is insufficient.

The five-day spike produced the core recommendation and initial deterministic foundation; live evidence is recorded in its issue and accepted implementation documents. It did not qualify all hardware. The exact catalog games still require the D19 initial boot/state check and D20 browser/hardware matrix; infrastructure evidence alone does not advertise either game as playable. Do not assume API availability proves determinism or switch to streaming without alignment.

## Work packages and dependencies

These are high-level delivery packages; the epic and 24-outcome snapshot below provide actionable task boundaries for orchestrator publication, not live assignments. Roles denote responsibility held by the developer unless stated otherwise.

| Package | Outcome and dependencies | Responsible role | Completion evidence |
|---|---|---|---|
| P0 Content definition | Record both supplied artifacts, ordering, presentation, mode honesty and placeholders. Complete as an input to the catalog amendment; runtime qualification remains D19/D20. | Product/content owner with developer | [Two-game catalog amendment](included-games.md), exact artifact evidence and AC-04 content prerequisites. |
| P1 Feasibility and compatibility | Select a core, inventory hardware/fixture gaps, and prove deterministic adapter, safe checkpoint codec, rewind and basic peer sync after approved planning handoff. Uses authorized fixtures; final content proof depends on P0. | Browser/network engineer | Five-day experiment report and repeatable replay/network measurements; technical basis for AC-05–07. |
| P2 Foundation and local play | Create TypeScript client/service workspace, pinned builds, worker/audio/input boundary, local ROM validation, saves, filters, accessible controls, and fast tests. Depends on P1. | Full-stack engineer | Real-browser local play and persistence proof; AC-02, AC-07–08 local portions. |
| P3 Directory and lifecycle | Immediate public/unlisted creation, live search/codes, anonymous defaults, atomic reservations, automatic readiness, invitation controls, expiry and moderation. Depends on P2 contracts. | Backend/frontend engineer | Multi-client lifecycle and authorization tests; AC-01–03, AC-09–10, AC-13–14 coordinator portions. |
| P4 Shared gameplay | Match fingerprints; connect WebRTC; automatic start and progress-preserving late-join barriers; delayed inputs; hashes; pause/resync; coordinated restore/rewind and controller handoff; reconnect; qualification across advertised hardware. Depends on P1–P3. | Network engineer | Browser matrix, fault injection, dynamic-state audit and direct/forced-TURN proof; AC-03, AC-05–07, AC-09, AC-11, AC-13, AC-15 networking portions. |
| P5 Social and catalog journey | Text, conversational voice with devices/mute/optional push-to-talk, two ordered included entries and verified distribution manifests. Depends on P0, P3, P4; text can be implemented after P3. | Frontend/content engineer | Zero-player catalog journey for both games, two-person demo, concurrent voice/gameplay and permissions/abuse tests; AC-04, AC-08, AC-10, AC-16. |
| P6 Launch validation | Staging, load/cost measurement, admission and relay quotas, telemetry/retention, abuse runbook, rollback/recovery, accessibility and beta rehearsal. Depends on P2–P5. | Developer/operator plus independent reviewer | AC-01–16 coverage report, current prices and measured usage, operational rehearsal and launch checklist evidence. |

The original critical path was approval/merged plan → issue/Project organization → P1 → P2 → P3 → P4 → P5 → P6. The live epic and Project now govern completed and remaining dependencies. P0 content identity is complete; D19 waits only for the reviewed catalog amendment to merge, while D20/D21 retain qualification and integrated acceptance. Overlap only independent work with satisfied prerequisites; agent concurrency does not remove review and merge gates.

## Verification strategy

The repository now contains the browser application, coordinator, native core adapter and product tests delivered by the linked issues. For a documentation amendment, inspect links, acceptance coverage, scope consistency and explicit unknowns. Run the README's `timeout 60s sh scripts/preflight.sh` and existing CI; do not claim new runtime evidence from a plan-only change.

Continue evolving pre-flight with focused fast type/schema checks and deterministic short fixtures, keeping the entire command below 60 seconds. Presubmit enforces a shared 30-minute wall-clock deadline across all jobs and retries. Keep CI dependencies pinned and document commands in the README.

Presubmit coverage must include canonical serialization and malformed input, matching/mismatching fingerprints, atomic joins and authorization, privacy of outbound traffic, coordinated epoch changes, local save compatibility, and the ten-minute network session matrix. Run browser pairs concurrently only where resource limits permit; record actual full-run time. If the budget is threatened, optimize infrastructure or redundant setup without deleting essential acceptance. Test forced TURN and direct connection in staging with credentials scoped to the run.

For visual changes, capture and inspect matched before/after screenshots or clips from the real application, including empty directory, full/waiting sessions, mismatch, reconnect, settings and gameplay. A new page uses the existing empty state as the before evidence. Check keyboard focus and microphone denial with actual browser interaction.

Essential presubmit voice evidence includes a short two-way audio/input/permission/mute regression smoke. The 30-minute-per-route AC-16 sessions, full per-hardware qualification and repeated startup samples run as separately timed staging release-validation jobs with named developer/operator ownership; they must pass before public launch but do not fit inside or replace the 30-minute presubmit suite. Keep a representative deterministic browser matrix and known regression fixtures in presubmit. Report release-validation results separately from PR CI and the post-submit soak.

After merge, run a separately budgeted two-hour network/rewind/reconnect soak in staging, owned by the developer/operator. File failures against the relevant package and record results; pending post-submit tests do not replace essential presubmit proof or hold unrelated PRs. Before public launch, resolve any observed launch-blocking failures.

Each implementation PR records exact commit/build, relevant AC IDs, test settings, actual output and duration, inspected visuals where relevant, pre-flight result, CI URL and elapsed time, and any post-submit plan. Use a fresh local reviewer in a separate detached worktree with only the PR URL and review instructions. Publish its report per [the handoff contract](../../tooling/vaseline/docs/review-handoff.md). Follow the scoped merge authorization recorded in the epic. The user now authorizes agent merges after local review and passing required checks, superseding the original external-review/separate-merger default for this project. Preserve branch protections and planning/scope approval; confirm integration before dependent work. The original approved snapshot remains available at its recorded commit.

## Hosting and operational delivery

At P6 compare available HTTPS/static hosting, one small Node coordinator, and TURN service prices/quotas using current provider documentation. The $50 target/$100 ceiling is not a price quote. Build a cost worksheet from fixed service charges plus measured catalog egress, logs and TURN bytes at 20 concurrent sessions/100 directory connections, including voice and relay-only use. Model monthly session-hours explicitly; concurrent capacity is not a monthly usage estimate. Start beta at a lower admission limit if measured spend demands it and realign any change to the accepted capacity.

Provision only after selecting a plan that can enforce the budget. Configure relay credentials with short expiries, allocation/bandwidth quotas, directory/signaling limits, TLS/origin checks and log redaction. Exercise budget exhaustion: new sessions receive a capacity explanation, relay-only users never silently disclose their address by falling back to direct, and the operator receives a content-free alert.

Deploy immutable versioned client/core assets to staging first and retain previous versions for active lobbies. Rehearse rolling back the client and coordinator and restoring catalog/configuration; a coordinator restart intentionally closes ephemeral lobbies. Document a maintenance message and the accepted interruption. Keep secrets outside source control and test the chosen provider's configuration recovery mechanism. Do not back up chat, user ROMs, or cloud saves because this release does not persist them.

Start a limited beta only after AC-01–16 evidence, both catalog artifacts' provenance and qualification, cost enforcement, and the reviewed operational runbook are complete. The operator reviews redacted health and abuse signals daily during the initial beta and assesses the first two weeks before increasing admission. Deployment authorization remains separate from this planning PR; the user selected GKE for staging, subject to the existing cost gate.

## Risks and reassessment

| Risk | Reduction and decision point |
|---|---|
| Catalog artifact incompatibility or packaging error | D19 verifies exact hashes, boot/menu/controllers and canonical state before advertising play; D20 performs full qualification. Do not substitute a different binary silently. |
| Incomplete emulator snapshots or nondeterminism | P1 tests CPU/PPU/mapper state and replay across browsers. Stop at the five-day bound and realign if proof fails. |
| ROM leakage in snapshots | Explicit dynamic schema and cartridge-region audit plus outbound fixtures before enabling any peer transfer. |
| Input delay/background throttling harms play | P1/P4 measure real browser/network behavior; pause clearly, then reassess supported conditions before launch. |
| Relay use exceeds budget | Current-price worksheet, metered session-hours, enforced quota/admission tests before provisioning. |
| Anonymous abuse | Server authority, revocation, rate limits, operator takedown and modest beta capacity; accounts require later alignment. |
| Schedule exceeds one developer's capacity | Reassess after P1/P4; preserve the accepted journey or explicitly renegotiate scope. |

Future iteration plans remain coarse: rollback after deterministic correctness and latency measurements; further compatibility expansion after the first reviewed hardware matrix; spectators after a topology/cost study; accounts/cloud saves after demand and data-lifecycle review. None are prerequisites silently added to this release.

## Gap audit and proposed issue coverage

The [journey audit and ticket map](browser-nes-audit.md) records three refinement passes and the original issue boundaries for AC-01–AC-16 and S01–S37. The epic, linked child issues and GitHub Project now own live status and assignments; D-identifiers in the audit are historical architecture references.

`project-orchestrator` keeps the stable plan IDs reconciled with live issues and the repository-linked GitHub Project. Priorities order eligible work; blockers govern readiness. D19's original dependencies are integrated, and its changed two-game/UI scope waits for the catalog amendment's reviewed approval and merge. Keep this document as technical detail and review snapshot; the epic owns the actionable delivery plan and issues own live status.

## Architecture decisions and delegated implementation choices

| Area | Architect decision / reuse direction | Deferred choice and owner / decision point |
|---|---|---|
| Browser app | Reuse React/Vite with TypeScript and browser canvas, worker, Web Audio, Gamepad and IndexedDB APIs; build the lobby/play integration. | D04 agent pins maintained versions; D07 frontend agent chooses components/style implementation within approved UX/accessibility constraints before its PR. |
| Emulator | Reuse a NES core behind an adapter; compare JSNES and credible alternatives against D01’s hardware inventory. Build only the deterministic adapter and ROM-free state codec needed by the product. | D01 architect selects core after inventory; D02 proves it. Failed evidence returns architecture/scope for review, not silent fallback. |
| Multiplayer | Browser-local emulation, WebRTC inputs, fixed delayed-input synchronization and validated dynamic checkpoints. Reuse browser transport/crypto; no custom encryption or server emulation. | D02/D10 network agents choose maintained transport helpers if useful; protocol fingerprints and state schema must be fixed before D11 consumers. |
| Coordinator | TypeScript Node service, WebSocket lobby/signaling, in-memory ephemeral state; reuse maintained HTTP/WebSocket libraries. No account database. | D04 backend agent pins libraries and protocol schemas before D08; D08 owns role/session contracts. |
| Voice | Reuse WebRTC media and browser permission/device APIs; conversational voice plus optional push-to-talk. | D17 media agent chooses helper libraries and tested processing settings within mute/privacy rules before integration. |
| Storage/content | Local IndexedDB saves; authorized catalog assets with manifests/credits; user ROMs remain in tab memory. | D03 content identity is integrated; [the catalog amendment](included-games.md) governs D19 packaging and presentation. |
| Hosting | Static HTTPS assets, one coordinator, STUN/TURN; reuse managed services where they meet enforceable quotas. | D24/D22 operator selects provider after current-price/access checks before spend; the $100 ceiling is a hard constraint, excess needs CEO alignment. |
| Tests/operations | Reuse project tooling and browser/network test libraries; retain hard preflight/CI budgets and separate release validation. | D04/D21 agents choose tools; D22 sets content-free telemetry and runbooks before launch. |

D01/D02 are the critical early feasibility decisions; D03 can progress independently. The prior effort envelope must be re-estimated once broad qualification is inventoried. The [24-outcome plan](browser-nes-audit.md) provides priorities, real blockers and acceptance; it is copied into the epic as the architect’s handoff, not delegated to the orchestrator to invent.
