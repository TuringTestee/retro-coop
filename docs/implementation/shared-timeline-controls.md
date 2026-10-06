Save and load progress directly inside the existing game. The host loads the quick save for everyone without an approval menu; validate every required machine and retain rollback state before changing shared progress.

Audience: Agent

# Shared Save and Load

Governing behavior: [gameplay controls](../design/gameplay-controls.md), [#261](https://github.com/TuringTestee/retro-coop/issues/261), [five-slot authority](five-slot-lobby.md) and [host recovery](host-game-recovery.md). This updates the delivered #236 flow; manual saves remain separate from automatic captures. Confirmed Restart uses the same replacement transaction; deferred rewind remains outside this scope.

## Direct journey

Public Host/Join → choose NES → prepare/start → Q Save → advance → host E/Load → restored play. Remove the quick-save confirmation and all participant acceptance menus from this path. One handler serves the Load button and its current shortcut. Only the host changes the shared timeline; other players may save their own copies. Save/Load notifications share the game’s top-right region, including expanded play, without hiding Return. Keep the lobby, slots, settings, chat and current presentation.

An empty, corrupt, incompatible, inaccessible or changed save reports its reason without replacing current progress. A Load while another timeline/role operation owns the game is rejected visibly. Storage and game-context changes revoke delayed work. After a successful load, restore the prior running/paused intent; shared play resumes only after every required controller acknowledges the validated state.

## Existing owners and validation

`GameSession` owns transaction authority and phase; `Rooms` binds membership, selected game and controller revision. `GameClient` owns input fencing and checkpoint transport. `LocalPlayer`/worker/native codec own atomic capture, validation and import; `saves.ts` owns persisted slots and generations. Reuse these owners instead of adding a second load path.

Q captures bytes, compatible identity, completed frame and hash atomically; existing compare-and-swap and storage-generation guards preserve the prior save on failure. Load rechecks the selected slot and current room/member/game epoch through completion. Validate native identity, bounded size, codec content and actual candidate frame/hash against the current ROM/core/settings. Existing byte-only saves remain usable through native validation; missing historical scheduler metadata establishes a truthful new timeline origin, never power-on freshness. Backup import/export and automatic capture remain distinct.

## One coordinated replacement

1. **Freeze and validate.** Bind the host request to membership, controller revision, old epoch, selected fingerprint and operation. Freeze at a completed boundary and retain prior frame/hash plus rollback snapshots. Validate the compatible save in an isolated native candidate. No user acceptance phase or dialog is needed.
2. **Stage required controllers.** Transfer the candidate through the existing bounded checkpoint path; verify identity/digest/frame/hash. Recheck authority and required participants before commit. Keep the old timeline until every required machine is ready, and prevent concurrent role/load/selection changes. Observers do not gate commit.
3. **Commit or roll back.** Verify every native commit acknowledgement before declaring success. On failed import, transfer, acknowledgement, disconnect or changed authority, restore prior snapshots on reachable controllers and keep the old authoritative timeline paused and recoverable. Returning members synchronize from it before resuming. Never run a partially replaced game or lose manual saves.
4. **Finish.** Bind the fresh committed epoch and clear stale inputs, held buttons, hashes, audio queues and transfers. Resume the prior running game through the existing shared barrier; otherwise keep the restored game paused. Synchronize observers to the committed state. Discard rollback state only after committed acceptance by the machines, and ignore stale packets/callbacks.

Remove superseded quick-load dialogs, consent commands/phases, callers and test expectations. Keep actual recovery/exit/Restart blockers and backup/delete confirmations. Automatic captures must not publish a provisional replacement as recovered progress; `gameRestore` remains a distinct initialization owned by host recovery.

## Cartridge restart

Prepare a temporary machine using the selected ROM and the existing OSS worker/core initialization, without replacing the active machine. Its fresh native capture enters the same host-authorized stage/commit/rollback transaction as Load. Cancel, failed initialization and changed game/membership preserve current progress and saved copies. Local restart imports the same validated state and restores prior running/paused intent. The actual Restart binding is configurable; migration preserves all prior personal and unbound mappings, assigning N only if free.

## Verification

Extend essential deterministic and Chromium journeys through real public controls: Q → advance → E has no approval menu; host/P2/observer keep membership/presentation, match restored native frame/hash and accept real P2 input. Cover local/shared running and paused intent, later use with the matching ROM, byte-only saves, empty/incompatible/corrupt state, denied/cleared/overwritten storage, delayed read/capture after timeline replacement, transfer/native-commit failure, concurrent requests and disconnect/reconnect. Observe the prior frame/hash and no partial resume on failure. Check top-right progress/result and Return at narrow views and real zoom. Publish portable evidence, run bounded preflight/hosted checks, obtain independent review and verify deployed main before claiming delivery.
