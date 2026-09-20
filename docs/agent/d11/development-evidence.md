Audience: Agent

These are observed development runs, including failures and repaired outcomes. They establish specific behavior but do not substitute for final integrated CI or the ten-minute browser matrix.

| Evidence | What it establishes and its limit |
| --- | --- |
| `slow-first-frame.json` | A guest worker response took 912.5 ms before any injected fault. Both peers paused at frame 14. Later quiet runs did not reproduce it; no specific scheduler/OS cause is claimed. |
| `silent-drain-before.json` / `silent-drain-after.json` | Dropping all guest inputs exposed a drain loop that relied on new packet/worker callbacks. Periodic bounded admission checks restored the one-second failure path and retained membership. |
| `checkpoint-before.txt` / `checkpoint-after.txt` | A real scheduler regression first accepted an omitted checkpoint. Ordered checkpoint admission now rejects missing checkpoints and repeats after comparison; it also prevents stale hash entries accumulating over time. |
| `delayed-start-harness-before.json` / `delayed-start-after.json` | A delayed Start test initially pressed P2 before its local worker started, yielding a wrong input oracle. Waiting for actual worker readiness fixed the harness. The production receiver then accepted bounded early packets and completed shared play. |
| `mixed-short.json` | Actual Chrome145–Firefox146 workers, kernel packet impairment and identical per-pair checkpoints/final state. This is a 30-second development sample, not ten-minute qualification. |
| `firefox-short.json` | Firefox146–Firefox146 completed 30.0 measured active seconds, 1,810 matching committed frames and every ordered checkpoint under actual kernel impairment. Core/build hashes are recorded. This passes the stricter duration verifier but remains short development evidence. |
| `relay-short.json` | Actual shared frames and pause/resume over a forced local coturn route, with its existing quotas. This is local route evidence, not public relay qualification. |
| `device-short.json` | Controlled gamepad removal pauses both clients. An unresolved device cannot acknowledge readiness; keyboard fallback and both readiness acknowledgements permit a new epoch. |
| `cancel-short.json` | Canceling an unacknowledged initial barrier preserves frame zero and membership rules; explicit local Resume then runs the host’s preserved game. |
| `shared-chat-short.json` | Both controller ports reach CPU WRAM; typing chat releases only the typing player’s game input, while shared play and actual message delivery continue. |
| `asset-suite.json` | All 13 production browser journeys pass with the approved hashed-core asset path integrated. Full individual output remains in the eventual CI artifact. |
| `before.png` | Actual main `31713b0` at the same desktop viewport, with matching local files and connected transport before D11. Both pages are held at true initial state; no synchronized gameplay exists in this baseline. |
| `initial.png`, `playing.png`, `paused.png`, `paused-mobile.png` | Inspected real-product states at matching desktop widths and a narrow viewport. The plain gray image is the repository’s original diagnostic cartridge output. Voice remains off; hidden invite inputs are excluded from screenshot masks. |

The final harness additionally requires a full measured active interval and derives its frame target from the worker-reported region rate. Earlier short samples predate that stricter duration check and are intentionally labeled development evidence. Source/core artifact hashes in the later samples identify what actually ran; uncommitted author repairs are not retroactively credited with these results.
