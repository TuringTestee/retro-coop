# Journey audit and proposed issue map

The revised plan covers anonymous hosting, friend discovery, automatic joining and voice, with explicit exceptions for missing ROMs, permissions and ongoing game progress. It is not ready to dispatch builders: only epic #2 exists, the planning PR remains open, and the featured game plus measured compatibility scope remain unresolved. The requested workflow now places architecture and task planning in the epic and issue/Projects organization in the orchestrator. The draft tickets below make the missing implementation breakdown reviewable without pretending tickets have been published.

## Source and status

Source: [design](../design/browser-nes-platform.md), [UI](../design/browser-nes-ui.md), [delivery](browser-nes-platform.md), and the user’s request to update the audited journey and check issue coverage. This document travels with [planning PR #3](https://github.com/TuringTestee/retro-coop/pull/3); its current commit is the candidate source. At publication, record the actual approved merged source SHA in each child issue. The [root epic #2](https://github.com/TuringTestee/retro-coop/issues/2) remains open. As checked on 2026-09-13, there are zero implementation child issues; PRs #3 and #4 are not implementation tickets.

The user directed the revision; that does not establish approval of a not-yet-reviewed document revision. The revised workflow requires actual approval and merged planning before the orchestrator publishes executable child issues, organizes GitHub Projects and dispatches eligible agents. There is no separate mandatory breakdown PR. No draft below is assigned or claimed executable. This is a coverage audit, not a replacement for those gates.

## Iterative gap audit

| Pass | Missing behavior and user consequence | Revision and remaining evidence |
|---|---|---|
| 1: straight-through journey | Required name/visibility form, connection dialog, catalog Load, Ready and Start add setup to every visit. | Visible defaults, generated names, automatic preparation/start; AC-13 measures actions and elapsed time. Browser permissions and missing local file remain explicit exceptions. |
| 1: friend discovery | Duplicate names and no search make a friend’s room ambiguous. | Public search and unique public code, invite preview and full/stale feedback; AC-14 proves isolation of unlisted rooms. |
| 1: voice | Push-to-talk alone does not deliver ordinary conversation. | Open mic after consent, optional push-to-talk, device and separate mute controls; AC-16 tests actual duplex voice during play. |
| 2: late join | Automatically starting the host alone conflicts with resetting when a guest appears. | Reservation does not pause host; prepared guest triggers Continue current game/Restart/Keep playing alone with validated checkpoint transfer. AC-09/13 cover failure/cancel and progress preservation. |
| 2: anonymous lifecycle | A guest without a file can monopolize the second slot indefinitely. | Separate 120-second initial reservation and established reconnect grace, with rate limits and clear retry; AC-09/10. |
| 2: game semantics | Two networked controllers cannot make a single-player ROM co-op. | Native two-player/alternating behavior plus optional atomic P1 handoff; AC-15. Special peripherals remain qualified or unsupported. |
| 2: privacy and cancellation | Removing dialogs can accidentally connect on invite view, leak peer addresses or leave cancelled rooms published. | Inline policy before action, metadata-only preview, strict relay precedence and stale-action cleanup; AC-10/11/13. |
| 3: compatibility | A single featured-game test does not substantiate “all NES.” | Core/format/hardware inventory, separate local/netplay statuses, representative authorized fixtures, runtime errors and unsupported explanations; AC-15. Actual coverage is unresolved until measured. |
| 3: returning visitor | “Already loaded” can be confused with silently storing ROMs. | Tab-memory reuse only; saves persist but ROMs do not. Reload may require reselection; AC-02/03/13. |
| 3: measurable release | No startup, connection-success or sustained simultaneous voice evidence. | Proposed budgets and sample conditions, real internet/forced-relay trials, separate release validation versus bounded PR CI; AC-13/16. |
| 3: retained features | Simplifying start could erase pause, saves, rewind, accessibility, moderation or recovery. | Retained S01–S32, added S33–S37; explicit acceptance and issue mapping below. |

These are author walkthrough findings and document revisions. No prototype, user study, internet session or compatibility run has occurred. Independent document review is recorded in the PR and does not establish runtime feasibility.

## Draft ticket boundaries

Every draft is a Feature or Enhancement under epic #2. Priority P0 means decision/feasibility or release safety is critical; P1 delivers the main journey; P2 completes retained release features. All are committed release work, not optional because their priority is lower. Priority orders eligible work only; the user is CEO and the architect owns technical/dependency decisions. The source section and acceptance references below form its requirements, not prescribed implementation steps. Default exclusion for every draft: no new accounts, ROM sharing/storage, server gameplay, streaming fallback, recording or unapproved product scope. Named dependencies are blockers, not implied merely by membership in the epic. The P0 content answer is D03’s deliverable and blocks D19 and content-specific qualification; it does not fabricate a substitute game.

| Draft | Priority / reason | Bounded outcome / source section | Observable completion and acceptance | Blocks on |
|---|---|---|---|---|
| D01 | P0: architecture risk | Core recommendation and hardware/fixture inventory — delivery P1; design compatibility | Compare candidates, enumerate mapper/region/format/peripheral gaps and authorized fixtures, recommend pinned core and revised effort. No universal-support claim. AC-15 inventory. | Approved merged plan |
| D02 | P0: feasibility risk | Deterministic core/state feasibility — delivery P1; design local emulation | Five-day spike report, cross-browser replay/restore and ROM-free dynamic state proof, measured rewind envelope; record fail/realign if unmet. AC-05–07 initial evidence. | D01 |
| D03 | P0: content decision | Featured-game specification and provenance — design content policy; P0 | Reviewed identity/rules, reproducible artifact, two-player behavior, distribution/browser-play evidence and credits. No guessed variant. AC-04 prerequisites. | Approved merged plan; user owns content answer |
| D04 | P1: build foundation | Executable client/service foundation — design architecture; P2 | Reproducible pinned build, local/staging config boundaries, worker/input/audio contract, evolving fast preflight and bounded CI. No product-completion claim. AC-12 foundation. | D02 |
| D05 | P1: first play | Local file-to-play and anonymous defaults — design discovery/fast-start | Drop/picker validation, generated names, default controls, responsive feedback/cancel and no ROM upload; unknown titles on supported hardware accepted. AC-02/08/13 local portions; S02/S36. | D04 |
| D06 | P2: retained progress | Local saves, export/import and rewind — design saves | Persistence/error/export evidence, compatible restore and 10-second/32 MiB rewind; no cloud/ROM persistence. AC-07; S12/S14–17. | D05 |
| D07 | P1: usable input | Controls, presentation and local accessibility — design controls; UI U4/U7 | Keyboard/gamepad remap, conflict/defaults/focus/unplug, filters/audio/fullscreen and keyboard-accessible controls. AC-08; S18/S19/S30/S31. | D05 |
| D08 | P1: guest hosting | Guest rooms and immediate hosting — design discovery/lifecycle | Public/unlisted room creation from valid file, generated identities, atomic two-slot reservations/expiry/cancel, role authority, ephemeral lifecycle; no required form. AC-02/03/09/13; S02/S04/S07. | D05 |
| D09 | P1: find friends | Public friend discovery and invitations — design discovery/fast-start | Live all-status directory, search/unique codes with collision handling, duplicate names, invite preview/copy, unlisted omission, stale/full/no-match paths. AC-01/14; S01/S06/S33. | D08 |
| D10 | P0: internet viability | Peer connectivity and privacy — design social/architecture | Authenticated signaling, inline policy, stricter relay wins before candidates, direct/forced-TURN proof, retry/capacity denial. AC-10/11 connectivity; S09/S28. | D08 |
| D11 | P1: shared gameplay | Automatic shared start and delayed inputs — design synchronization/lifecycle | Exact fingerprints, automatic prerequisites/start, frame/epoch input discipline, stall/focus handling and representative deterministic browser matrix. AC-03/05/13; S05/S07/S10/S11. | D02, D07, D10 |
| D12 | P1: join without reset | Progress-preserving late join — design lifecycle; UI U3 | Only prepared guest prompts host; checkpoint continue, agreed reset or resume solo; cancel/failure preserves original progress. AC-09/13; S08. | D11 |
| D13 | P1: recovery/exit | Desync and reconnect recovery — design synchronization/lifecycle | Correct hash pairs, one bounded validated resync, disconnect grace/expiry/host loss, explicit leave/close and viable continue-solo with stopped peer/voice, no stale resume or unauthorized reservation claim. AC-06/09; S22–25/S28. | D11 |
| D14 | P2: shared progress | Shared timeline controls — design saves; UI U5/U6 | Local committed save plus both-party rewind/load/reset barrier, decline/timeout, epoch invalidation and no concurrent requests. AC-07; S13–16. | D06, D11 |
| D15 | P1: honest game modes | Game modes and P1 handoff — design compatibility; UI U7/U9 | Native P1/P2 and alternating-turn explanation, optional shared P1 transfer with one owner/acceptance/clear held inputs; no invented co-op. AC-15 gameplay; S35. | D11 |
| D16 | P1: pre-game contact | Room text chat — design social; UI U3/U4/U7 | Pre-ROM text, plain text/rate/length limits, no pre-join history, bounded retention, focus isolation and unsent retry. AC-08/10; S20. | D08 |
| D17 | P1: conversation | Conversational voice and devices — design social; UI U7 | Two-way open mic, optional push-to-talk, permission/device failures, local/remote mute, blur/leave stop and retry without gameplay reset. AC-08/16 functional; S21/S34. | D10, D07 |
| D18 | P0: admission/privacy | Moderation and protocol hardening — design social/data ownership | Role/token/origin/schema/rate enforcement, kick revocation/peer closure, operator removal, no private content in listings/telemetry; adversarial evidence. AC-09/10; S26/S27/S29. | D09, D10, D16, D17 |
| D19 | P1: included fast path | Included-game fast path — design featured/content; UI U1/U3/U9 | Permanent honest entry, pinned verified download on Join, credits/instructions, zero-player/start/browse and failure paths. AC-04/13; S03/S29. | D03, D09, D11 |
| D20 | P0: compatibility proof | Hardware qualification suite and release matrix — design compatibility | Local/netplay statuses and per-advertised-combination boot/audio/input/save/rewind/replay/network proof, negative fixtures, unsupported/experimental runtime handling; reviewed exceptions. AC-05/15. | D01, D06, D13, D14, D15; D03 for featured fixture |
| D21 | P0: journey proof | Combined fast-start, voice and accessible journey validation — design AC-13/16; UI interaction acceptance | Recorded action counts, startup samples, success rates, 30-minute voice/gameplay per route, both-role browser demo and keyboard/recovery paths; fix failures before acceptance. AC-08/12/13/16; S30–32/S37. | D07, D09, D12, D13, D14, D15, D16, D17, D19, D24 |
| D22 | P0: enforce budget | Capacity and enforceable cost envelope — delivery hosting; design operations | Scoped relay credentials/quotas, measured load/session-hours/cost, admission behavior and operational telemetry; no spend beyond authorization. AC-01 load, AC-10/11. | D18, D19, D24 |
| D23 | P0: release evidence | Release readiness and beta handoff — delivery launch/operations | All AC evidence linked, compatibility and content accepted, rollback/restart/config restore and abuse runbook rehearsed, accessible complete journey, owned separate soak/post-launch review. AC-01–16 release gate. | D20, D21, D22 |
| D24 | P1: real internet testbed | Internet staging environment — delivery hosting | HTTPS, versioned client/coordinator and relay access on independent networks, deployment/config smoke, secrets isolated; staging only, not public launch. AC-11/12 infrastructure. | D10 |

D05 covers local playback; D08 integrates publication without duplicating the local loader. D09 is discovery, D10 connectivity, and D11 is synchronized gameplay. D17 provides voice behavior; D21 measures it alongside actual gameplay. D18 audits and hardens controls whose owning feature must already enforce its own authorization; security is not postponed to a final patch. D20 is a qualification harness/report across the reviewed inventory, not a single giant “support all NES” implementation issue: any missing mapper/core feature discovered by D01 becomes a separately bounded scoped proposal before committing it. D23 owns release integration, not duplicate feature implementation.

## Acceptance ownership and coverage check

| Acceptance | Primary draft ownership | Integration evidence |
|---|---|---|
| AC-01 | D09 | D22, D23 |
| AC-02 | D05, D08 | D18, D21 |
| AC-03 | D08, D11 | D12, D21 |
| AC-04 | D03, D19 | D23 |
| AC-05 | D02, D11 | D20, D21 |
| AC-06 | D02, D13 | D20 |
| AC-07 | D06, D14 | D20, D21 |
| AC-08 | D07, D16, D17 | D21 |
| AC-09 | D08, D12, D13, D18 | D21 |
| AC-10 | D10, D16, D18 | D22 |
| AC-11 | D10, D22 | D21 |
| AC-12 | D04, D23 | D21 |
| AC-13 | D05, D08, D11, D12, D19 | D21 |
| AC-14 | D09 | D18, D21 |
| AC-15 | D01, D15, D20 | D23 |
| AC-16 | D17 | D21 |

Every AC has an owner and end-to-end evidence destination. The UI’s S01–S37 trace visible states; D13 owns S25 leave/continue-solo and D23 collects cross-feature release evidence. D24 stages the real internet environment before D21’s measurements and D22’s cost/admission proof, avoiding a partial or cyclic dependency. D03 is a parallel content decision. The dependency graph must be machine-checked before handoff and revalidated against real issue relationships at publication.

## Remaining readiness gaps

- Actual approved merged planning revision and orchestrator-created issue/Project organization are absent. Next deliverable is review of this concrete planning amendment, not dispatch.
- Featured variant identity, playable artifact, rights and native two-player rules remain unknown. D03 is a draft outcome; it is not evidence those requirements are resolved.
- “All NES” remains an aspiration pending D01/D20 evidence. No emulator or hardware matrix has been qualified; absent hardware support needs its own estimate and approved scope, not an unsupported success promise.
- Fast-start, success-rate and voice budgets are proposed targets. D02 provides early feasibility; D21 supplies release evidence. Device/browser expansion beyond the stated desktop matrix requires separate scope.
- The original 8–12 week estimate is not sufficient evidence for the expanded work; revise it after the inventory. Provider choice and spend authorization remain launch prerequisites.

The orchestrator should read the epic plan, verify all live issues before creation, preserve parent/child and blocking relationships separately, and replace D-identifiers with issue links tied to the approved source SHA. Reuse a repository-linked GitHub Project when available and verify real issue cards, priorities and status by readback. Current credentials lack `read:project`; use epic and issue tickets for priorities, dependencies, ownership and status instead. This fallback does not block otherwise eligible dispatch or require extra approval; no board setup is claimed. Merged [Vaseline workflow refactor PR #6](https://github.com/TuringTestee/vaseline/pull/6) defines the ownership split. This PR updates the pin to `72655f749c0df2fa35f9631dd1fbf32bff7cac79`, reconciles skill links and consuming guidance, and supersedes closed tooling PR #4. Keep this audit as rationale, not a second live progress tracker.
