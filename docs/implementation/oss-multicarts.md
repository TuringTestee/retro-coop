Audience: Agent

# OSS multicart support

The supplied 64-in-1 cartridge needs an emulator board that the current core does not implement. Add the existing FCEUmm core for this cartridge family, chosen automatically, while keeping existing games and their saved progress on TetaNES. No new player-facing choice or custom mapper is needed.

## Direction and scope

[Issue #248](https://github.com/TuringTestee/retro-coop/issues/248) records the current production upload failure and local `UnimplementedMapper(225)` result. The owner requested testing both supplied multicarts after Save/Load, high-priority repair of failures, and existing OSS solutions only. The 1200-in-1 cartridge already loads; its successful title screen does not prove every bundled game.

Reuse [the lobby journey](../design/unified-lobbies-direction.md), [five-slot play](five-slot-lobby.md), and the existing shared Save/Load and host-recovery contracts. Keep the lobby-first flow, automatic connection selection, fixed shell, and all current controls. Private ROMs remain local test input, never committed, distributed or made default games.

## Architecture

- Pin unmodified [FCEUmm](https://github.com/libretro/libretro-fceumm/tree/7a542dab1e87679921962a9f056186eca425c0c2), including its GPL notices and corresponding source/build instructions. Use its existing mapper 225, single-frame libretro interface and state serialization. Write only the application adapter and boundary checks; do not port board logic or implement emulation.
- Select FCEUmm internally for the verified mapper-225 profile. TetaNES remains authoritative for existing supported cartridges and saved progress. Reject other unsupported profiles honestly until verified; a second core is not a promise of universal compatibility. The player never chooses an emulator.
- Keep one worker request/response contract and the current coordinator protocol. Each backend implements loading, preview, P1/P2 input, frame/audio output, save/restore and peer checkpoint operations. Hash the actual pinned WASM/build/settings in the existing compatibility fingerprint. A different backend must never accept another core's state.
- Preserve existing TetaNES binaries, fingerprint and state format for currently supported games. Do not convert, delete or relabel old saves. The rejected mapper-225 profile has no valid TetaNES saves to migrate. Automatic recovery and local-data actions use their existing owners.
- FCEUmm's upstream loader can modify live state before reporting a failed import. Prepare candidate imports in a separate fresh WASM instance. Check bounded size, exact core/ROM/settings identity, canonical expected structure and complete state consumption before accepting. A digest alone is not validation. Commit only a validated candidate; cancellation, failure, late completion and replacement must leave the current game and save untouched. Retain the existing frame/epoch/hash and rollback ownership rules.
- Keep filesystem access inside the selected ROM's private in-memory workspace, with bounded WASM memory and worker deadlines. Invalid states, traps and nonprogressing work must be terminated without blocking the shell. Reuse upstream parsers; do not add custom emulation to make a fixture pass. The existing checkpoint security contract remains a gate, not an exemption for the new core.
- Clear presentation buffers across restore, replacement and disposal. Keep region selection, zeroed RAM, 48kHz audio and standard P1/P2 settings explicit. Disable optional untracked audio-history effects. Use fresh instances for cartridge loads so upstream global mapper state cannot leak between games.

## Delivery and acceptance

The existing #248 Project card owns this vertical repair; the final 1.0 journey gate remains on #2. Merge this reviewed plan before production implementation. Root owns integration and merging; a separate reviewer owns acceptance.

1. Prove the pinned unmodified core in browser WASM: the exact private 64-in-1 ROM loads its menu, selects a game and responds to input. Verify frame-by-frame deterministic replay, P1/P2 input and restored progress. Native-only proof is enabling evidence, not browser acceptance.
2. Integrate the backend through the public Host → Load NES game → Ready → Start journey. Verify failed loading and failed/cancelled restores preserve the existing lobby/game; replacement and leaving dispose all pending work. Show current screenshots and runtime observations without exposing ROM bytes.
3. Verify actual paired play, observer checkpoint transfer, shared Save/Load and automatic host recovery on mapper 225. Include identity mismatch, damaged/truncated or malformed state, bounded-resource failure, stale completion, cancellation and rollback. Failure of the existing security/determinism contract blocks enabling the backend.
4. Verify 1200-in-1 still loads and one selected title plays. Reuse unchanged TetaNES proof, with a focused existing-save compatibility check and representative included-game play. Do not repeat unaffected full suites or claim every bundled title works.
5. Run README preflight and affected existing CI/browser gates locally before review; keep preflight under 60s and presubmit under 30 minutes. Preserve one Chromium product check. After independent review and merge, verify main deployment and the original public upload path before closing #248. Final-source network and five-member release qualification remain separate obligations.

Keep emulator artifacts out of git when the existing generated build mechanism applies. Document the authoritative backend routing and license/source location; do not retain a competing demo, public entry point or obsolete instruction.
