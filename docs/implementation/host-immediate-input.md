Replace shared input waiting with a host-owned frame timeline. Keep local emulators and existing transactions; isolate guest lag and recovery from ordinary host advancement.

Audience: Agent

# Host input without network waiting

Governing journey: [immediate host input](../design/host-immediate-input.md). Baseline inspected: [`40b195164cce249edfb09621abee4603e9e89170`](https://github.com/TuringTestee/retro-coop/tree/40b195164cce249edfb09621abee4603e9e89170). This amends the platform's delayed-input gameplay design when implemented; it does not change the released runtime yet.

## Current causes and owners

| Current responsibility | Required change |
|---|---|
| `game-scheduler.ts`: `proposeInputDelay`, future-frame input queues, `next` waits for both owners | One host scheduler chooses the next frame from current local input and available authorized remote input. Guests replay only host-confirmed frames. Remove the old shared input-delay negotiation. |
| `game-client.ts`: link closure, required-controller backpressure and missing input call global pause/failure | Ordinary guest failures affect that peer's delivery/control availability. Host frame completion and healthy-peer delivery continue. |
| Scheduler hash collection waits for every controller; missing collections can throw | Compare hashes by completed frame and peer, within bounded retained history. A missing or mismatching guest hash never gates host simulation. |
| `player.ts`: input sampling tied to emulator advancement; guest network errors can invoke shared pause | Sample/transmit remote controls independently of guest replay. Keep local native-worker failures distinct from remote delivery failure. |
| Coordinator `GameSession` freezes playing games when any controller becomes unavailable | Only loss of the host or an explicit authorized shared operation freezes the authoritative ordinary game. Remote availability and recovery are per member. |
| `gameplay.ts` contracts, readiness/start contexts and coordinator start choose a shared delay | Define and validate one new gameplay protocol version; derive browser/coordinator rules from these contracts. Retain ROM/core/schema/settings identity separately. |
| Observer history/checkpoint transfer and shared Save/Load/role barriers | Extend the existing transfer owner for recovering guests; preserve deliberate coordinated transactions. No second checkpoint or replacement implementation. |

Inventory affected callers, fixtures and tests repository-wide before implementation. Retire superseded lockstep assertions, delay fields and instructions in the same delivery that replaces their owner. Preserve native codecs, saves, fingerprints, membership, RTC routing and existing controlled barriers. Historical feasibility reports remain historical evidence.

## Frame and input contract

1. **One authority.** The lobby host owns frame selection regardless of its controller role. For the next native frame F, read its current locally assigned mask, select the available remote mask, and dispatch `(epoch, F, p1, p2)` to the existing worker. An empty/unavailable controller contributes zero. No future local-input queue and no await on a peer.
2. **Confirm completed work.** Publish and retain the frame command only after the native worker confirms F completed. A worker error cannot advertise an unexecuted frame. Frame/state captures and hashes refer to completed boundaries; guest progress is tracked separately from the host cursor.
3. **Remote input is state, not a future-frame promise.** Send bounded state updates containing gameplay epoch, controller-assignment revision, connection generation, monotonic sequence and mask. Authenticate the sender through the existing membership/RTC binding. Validate size, integer range, role and context before recording it. Duplicates, old generations and superseded roles cannot alter controls. Local timestamps are diagnostics, never authority for another browser's clock.
4. **Independent sampling.** Poll gamepad/rapid controls at the game's native input cadence and send changed keyboard/touch states immediately, plus a bounded heartbeat of held state. This continues while a guest waits for frame delivery or a hash, and stops/releases when focus, ownership or game context is lost. Bind all asynchronous work to the current context.
5. **Short presses and freshness.** Between host samples, latch received press edges so a press followed by release can be applied for one native frame rather than disappearing; subsequent frames use current held state. Repeated identical states do not become extra presses. Do not replay a backlog as a long sequence of old holds. Verify directional chords, simultaneous changes and rapid A/B against the existing input semantics. Bound pending state/edges per controller, not by game duration.
6. **Lost control.** Clear remote state on link closure, role/membership/epoch change or input-heartbeat expiry. Reuse the existing 3-second network deadline initially as the hard stale-input ceiling; heartbeat cadence must be comfortably below it. Measure the release delay and healthy jitter before tightening it. On recovery, require a fresh current-generation state after synchronization; old queued input cannot revive a held button.
7. **Guest replay.** Guests accept ordered, contiguous host frame commands for the current epoch. Record assignment changes at their authoritative frame boundary: a lagging guest must replay valid earlier commands under that boundary history, not discard them merely because the lobby now has a newer assignment. Execute every committed simulation frame exactly once at its numbered position. Never simulate a missing frame with guessed input. P2's display is behind the host, so P2's perceived response includes network travel and guest display lag; there is no equal-latency promise.

Keep the current small frame/input envelopes and explicit bounded validation. Any new fields and limits belong in the contracts once. Remote packet receipt, peer fan-out, hashing and transfers must not introduce asynchronous peer waits into the local-input → native-frame path.

## Delivery, lag and deterministic recovery

- **Peer isolation:** Maintain independent send cursors and bounded buffers for each guest. A channel that exceeds the existing transport limit stops accepting live delivery and enters that peer's recovery path; never throw a global controller-transport failure. Serve healthy peers first and cap per-pump transfer work. Invalid remote input isolates its sender; an invalid authoritative stream stops that guest, with an explicit reason.
- **Presentation:** Keep the NES simulation rate from the loaded core. A guest maintains a small delivery buffer based on observed frame arrival and completion, then adjusts presentation/catch-up within bounded work. It may omit intermediate drawing/audio while catching up, but must execute all simulation frames. Never slow the host to the slowest guest or stretch the emulator's frame duration to fit ping.
- **History:** Reuse the existing 2,048-frame retention and bounded checkpoint transport as initial limits. Retain frame commands and same-boundary hashes together. If a guest can no longer recover within that history, capture a fresh host checkpoint and replay subsequent confirmed commands. Reuse a validated capture for compatible concurrent recipients; limit retries/transfer resources. A permanently underspeed browser stays in clear recoverable synchronization rather than an endless unreported loop.
- **Checks:** Keep periodic native hashes (currently every 120 completed frames). Hash computation must capture the exact native boundary and may briefly serialize with that local worker; it must not await remote hashes. Track comparison obligations per peer and frame, expire them within retention, and compare only matching epochs/frames/identities. A guest behind the host is not a mismatch. A genuine guest mismatch triggers that guest's checkpoint recovery; a corrupt authoritative/native state remains a real host failure.
- **Catch-up:** Reuse checkpoint identity/digest validation and live-boundary fencing for P2 as well as spectators. Do not grant recovered controller input until the current transfer, membership and controller revision acknowledge the live boundary. The host keeps playing while a returning member watches/synchronizes. Retry uses a new transfer generation and cancels stale callbacks. A timeout reports the failed phase; it does not claim progress was restored or automatically reset the host's cartridge.

The existing checkpoint export can briefly occupy the host worker. Measure its cost and schedule bounded work between completed frames. This requirement eliminates **waiting for peers**, not all local computation. No extra full emulator on the host or custom core is justified by this plan.

## Shared operations and lifecycle

Keep [shared Save/Load and cartridge replacement](shared-timeline-controls.md), [slot authority](five-slot-lobby.md) and [host recovery](host-game-recovery.md) as their existing owners.

- Initial Start still requires every required controller to be prepared with matching native state. Spectators remain nonblocking.
- Explicit Pause/Load/Restart/Change game/role transactions choose an authoritative completed boundary, retain rollback state and wait for the operation's required native acknowledgements. A lagging participant catches up to that boundary or fails the transaction under the existing deadline; it cannot produce a partial resume. This bounded deliberate freeze is distinct from ordinary play.
- Remote network/focus/device failure uses neutral input and peer recovery. Keep explicit user Pause shared; audit `pause`/`gameAbort`, coordinator availability updates and native busy timeouts so failure provenance is not lost. The host's own worker/authority loss retains genuine shared recovery.
- Every committed timeline/assignment change invalidates held input, pending edges, sequences, peer cursors, hashes, timers, audio and captures under the old context. Preserve saves/preferences only under their established ROM identity and storage generations.
- Mid-game admission and controller promotion use the existing slot/membership owner. Recovery alone cannot assign a role. Host kick remains authorized; no automatic kick or host migration is added. Audit automatic slot compaction after departure/expiry: it cannot reintroduce a global wait through implicit role changes. Revoke departed input at an authoritative frame boundary; any automatically promoted member stays neutral until current-state synchronization and the new assignment are acknowledged. Preserve the existing slot ordering while the host keeps advancing.

## Protocol rollout

ROM fingerprints do not identify the network scheduler. Add an explicit gameplay capability/version to the existing session admission and readiness contracts, checked by the coordinator before create/join/prepare and bound to the start epoch. The new protocol must not silently interpret old future-frame input as current control state.

Ship the browser, coordinator and contracts together through the existing main CD. Use the current service-restart/closed-lobby behavior for incompatible active sessions during cutover; seamless survival across a coordinator restart is not existing support. Older tabs may retain their local NES and saves, but cannot host/join the new gameplay protocol until refreshed. New clients show the normal update/reconnect reason. Validate old-client rejection through its actual released parser and existing service-interruption flow; do not promise new text rendered by an old bundle. Do not maintain two gameplay schedulers or introduce a mode selector.

Rollback deploys the prior compatible browser/coordinator pair and uses the same existing lobby-reset behavior. It must preserve browser-local saves and must not permit mixed-protocol Start. Run mixed-client and stale-packet checks before enabling the new path.

## Verification and delivery

Use text logs and native receipts for timing/network debugging. Chromium is the one browser gate. Local automated audio uses the verified `retro-coop-test-audio` sink, preserving decoded audio/voice checks. Follow the platform's existing [verification strategy](browser-nes-platform.md#verification-strategy): preflight ≤60 seconds, ordinary PR checks ≤300 seconds and integrated main gate ≤600 seconds. Longer route/soak runs have their own post-submit owner and retained results.

| Proof | Required observation |
|---|---|
| Focused scheduler/protocol | Given host press or release just before the next eligible dispatch, that native frame uses it with P2 silent, late or disconnected. Commit only after worker completion; bound buffers/history; reject stale/unauthorized/malformed updates. Missing hashes/backpressure cannot block host advancement. |
| Remote controls | Actual P2 native input after receipt, including a short tap, held direction, release, rapid A/B and simultaneous buttons; heartbeats preserve a healthy hold; loss clears it by the deadline. Sampling continues when guest replay stalls. |
| Paired public journey | Host/join → load → Prepare/Start → control both players through the public app. Log local event, selected/native/completed frame, committed masks and hash. Measure added frame delay separately from event-to-presentation milliseconds. Compare the released automatic 6–8-frame input scheduling with the candidate; do not assert literal zero milliseconds. |
| Failure isolation | Independently delay input delivery, stall P2's worker, stop its hashes, fill its outgoing channel and disconnect it. Host native frames and healthy guest delivery continue. Resume/rejoin through checkpoint/history; prove matching native hash at the same completed frame and real recovered P2 input. Include all five slots with a slow spectator. |
| Shared operations | Perform Pause/Resume, Q Save/E Load, Restart, role move/kick and two-controller→one-controller→two-controller cartridge replacement while a guest is behind. Assert exact boundaries, no partial commit, preserved lobby/saves and working current controls; inject one transaction failure and verify rollback/retry. Host refresh still uses existing recovery. |
| Deployment and sustained play | Public direct and forced-relay paired sessions, correct deployed source identity and mixed old/new-client rejection. Extend existing route/long-game harnesses rather than add overlapping scripts. Retain baseline and candidate native frame-rate, response, lag, recovery and resource metrics; report failures honestly. |

### Delivery map

The [repository Project](https://github.com/orgs/TuringTestee/projects/1) owns status, priority, dependencies and assignment. Publish these draft cards with immutable governing links before implementation:

1. **[Immediate host play and isolated guest recovery](https://github.com/orgs/TuringTestee/projects/1?pane=issue&itemId=264296875):** contracts/admission, native-confirmed host timeline, independent remote sampling, bounded per-peer replay/hash/checkpoint recovery, coordinator failure isolation and paired public proof. This is one complete usable vertical change; an immediate host path that still stalls on hashes is unfinished.
2. **[Preserve shared controls and lifecycle](https://github.com/orgs/TuringTestee/projects/1?pane=issue&itemId=264296887):** depends on 1; integrate existing transactions, role/admission/rejoin/host recovery, mixed-version cutover, remove superseded callers/tests/docs and prove those journeys. Do not release the changed scheduler until this dependent work passes.
3. **[Integrated release gate](https://github.com/orgs/TuringTestee/projects/1?pane=issue&itemId=264296897):** depends on 1 and 2; independently review current combined source, run bounded integrated checks and owned direct/relay/long-game proof, merge eligible source and verify deployed main. No runtime behavior is claimed complete by this planning PR.

Merge the independently reviewed governing plan first. Keep a single runtime release candidate across the two implementation cards so users never receive an intermediate scheduler without its lifecycle protections. Assign builders only after plan acceptance. Numeric tuning of guest buffering, heartbeat cadence and catch-up work is based on measured results and committed alongside its focused checks; it cannot add delay to host input or change native simulation semantics.
