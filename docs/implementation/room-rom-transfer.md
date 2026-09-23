Audience: Agent

# Room game transfer — proposed delivery plan

This plan lets a room host upload a NES file once and lets each guest download and cache verified bytes automatically. It is a proposed amendment to the existing no-upload architecture, not a description of current support. [Human behavior and acceptance](../design/room-rom-transfer.md) are authoritative for the experience.

**Review snapshot:** updated against `origin/main` `fa15c99` and the user's 2026-09-23 Lilac Harbor report. [PR #85](https://github.com/TuringTestee/retro-coop/pull/85) is merged: separate browser tabs, explicit guest Prepare, accurate host readiness, and continued background play are now the baseline. Plan review, user approval of this version, and merged governing documents are pending. Do not dispatch implementation from this draft.

## Existing owners to reuse

| Responsibility | Current owner | Change |
| --- | --- | --- |
| File structure, exact SHA-256, emulator identity | `apps/client/src/cartridge.ts`, `player.ts`, `packages/contracts/src/fingerprint.ts` | Move structural NES validation into one shared owner so the server and client apply the same rules. Retain one fingerprint rule. Keep the selected `File` available until upload completes. Verify guest bytes before calling the existing player load path. |
| Room reservation, membership, visibility and readiness | `apps/coordinator/src/rooms.ts`, `apps/client/src/room-client.ts`, `game-client.ts` | Gate room confirmation on committed content; scope guest download to its current reservation. Keep explicit guest Prepare and the existing gameplay barrier. |
| Included-game acquisition | `catalog-download.ts`, `RoomPanel.tsx` | Extract one verified download/cache path with catalog and host-room sources; do not create a second independent file validation rule. |
| Local browser data | `apps/client/src/saves.ts`, Local data UI | Evolve the existing IndexedDB database with a `roms` store keyed by exact ROM SHA-256; add list/delete to Local data. No filenames or host identity in the cache key. |
| Network entry and admission | `apps/coordinator/src/server.ts` | Add authenticated binary HTTP upload/download routes beside WebSocket signaling. Keep binary data out of the 4 KiB room-message protocol. |

## Transfer contract and state

1. **Host selection:** `LocalPlayer` validates and fingerprints the file. `RoomClient` creates an unconfirmed room intent. An authenticated upload sends the original `File` as an octet-stream body; the room remains absent from the public directory. The host UI shows progress using an upload API with observable progress; Fetch upload progress is not available across the target browsers ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/File_API/Using_files_from_web_applications)).
2. **Server commit:** The coordinator streams bytes to a private temporary file under an operator-controlled content directory, with a global byte quota, per-transfer time/concurrency limits, and reserved capacity before accepting the body. It computes SHA-256 and checks the exact length and structural header against the pending room fingerprint using the shared structural validator. It cannot independently derive the browser emulator's core identity from the ROM bytes; that identity remains part of the host's fingerprint and is checked by the guest's load path. A mismatch or interrupted body deletes the temporary file and leaves the intent unconfirmed. An atomic rename attaches the verified blob to that exact intent; `confirmCreate` requires it. The room stores a private content handle, not a filename or public URL. No title or mapper allowlist and no blanket 8 MiB rule are added; capacity denial is explicit.
3. **Guest acquisition:** After `join`/`joinCode` reserves Guest, the authenticated guest requests the current room's bytes. The server checks token, membership, room ID, reservation and content handle on every request; other rooms and unauthenticated callers receive no bytes. Its response has the exact byte length, no filename, and `Cache-Control: no-store`. The client checks an existing IndexedDB copy first, reads it back and rehashes it; otherwise it streams the download with visible byte progress, verifies length/SHA-256, then saves the verified bytes. Recheck current room/membership and operation generation before cache write, load, or readiness. Automatic cache writes must also compare the existing Local data generation inside the write transaction, so a concurrent clear in another tab cannot be undone by a late download.
4. **Preparation:** Pass verified bytes through the existing `LocalPlayer.load` path. Its computed core/settings/cartridge fingerprint still must match the room. The guest's explicit **Prepare to play** sends the existing `gameReady` only after load and peer connection. Host Start and controller ownership remain server-authoritative.
5. **Lifecycle:** Cancel aborts the current transfer and releases only its own unconfirmed intent or guest reservation. A retry creates a new transfer for the same current intent if valid; late completions cannot publish a cancelled room or load into a replacement membership. Room close, expiry, operator removal and server shutdown delete its private blob. Startup sweeps any orphaned temporary files; existing ephemeral rooms do not survive restart. An authenticated download already in progress may finish from an open file handle, but it cannot create readiness after room closure.

HTTP routes use exact allowed origins, an `Authorization` bearer session token in a header, no token in a URL, and no arbitrary CORS origin. The WebSocket-issued token remains the membership authority; upload additionally requires the pending host intent and download requires a current guest reservation. Reuse admission rate limits and add transfer-specific concurrency/byte budgets. The reverse proxy must stream request/response bodies without logging them. Disallow intermediary caching. Do not record ROM bytes, hashes, filenames, tokens or paths in analytics or routine logs.

The guest reservation currently lasts 120 seconds. A verified, progressing download may extend only that reservation up to a bounded five-minute total; idle or failed transfers do not hold the place indefinitely. Expiry removes the guest place and aborts its transfer. This bound and the byte budget must be measured against the existing connection and PR CI budgets before release.

## Browser storage behavior

Use the existing `retro-coop-local` IndexedDB owner, with a versioned `roms` store holding only verified bytes, hash, size and saved time. Reuse its `meta.generation` guard for automatic writes: read the generation before download, compare it within the ROM write transaction, and skip persistence if another tab cleared Local data. Browser storage can be denied, run out of quota, or be evicted ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)). A failed or generation-rejected write does not turn a valid download into a false ready state: keep verified bytes in memory for the present tab, display “Available in this tab; download again next time,” and continue to player load. Local data lists stored games by neutral identity and size and can remove one or clear all. Do not silently delete other saves or preferences to make space.

## Delivery map and dependencies

| Order | Delivery | Acceptance and evidence |
| --- | --- | --- |
| RT1 | Authenticated private blob store and upload contract | Pending room cannot be published without committed matching bytes; wrong token, wrong intent, truncated body, capacity denial, cancel, expiry and cleanup tested. |
| RT2 | Host creation path and progress | From the documented demo, selecting a custom NES file uploads once, shows progress, publishes only on success, and recovers without a ghost row. Depends on RT1. |
| RT3 | Membership-scoped download and shared verified cache | Guest Join fetches exact bytes, caches/reuses them, detects corrupt/partial data, and handles quota fallback. A cross-tab Clear local data during download prevents the late automatic cache write while the current tab may play its verified in-memory copy. Depends on RT1; reuse existing catalog acquisition. |
| RT4 | Guest room UI and Local data | Remove matching-file path; show download, Cancel/Retry, Prepare, and cache management with one forward action per state. Depends on RT2/RT3. |
| RT5 | Integrated two-browser journey gate | Public and unlisted host-provided ROMs join without guest file picker; 200+ synchronized frames and matching hashes, repeat join from cache, interrupted transfer recovery, cross-tab Clear during download followed by another Join, slow-download lease, quota denial, room closure cleanup, included-game regression and accessibility states. Depends on RT1–RT4. |

One coherent release gate owns the host-to-guest acquisition and shared-start journeys plus their recovery. The existing issue #66 journey gate can be extended only after its scope/acceptance is updated; the browser-nes-platform epic #2 must record this replacement architecture, priorities, dependencies and operational budget. Create linked delivery issues and board entries after approval rather than treating this table as live assignments.

## Verification and rollout

- Focused server tests cover authorization, immutable bytes, hash/length checks, storage capacity, transfer races and cleanup. Browser tests use a generated redistributable diagnostic NES, never a commercial fixture, and separate browser sessions.
- Keep the README preflight under 60 seconds and pull-request build plus relevant browser journey within the five-minute shared CI deadline in the [current verification strategy](browser-nes-platform.md#verification-strategy). Run full browser/network qualification after integration under its existing budget; measure upload/download at representative file sizes and connection conditions before promising speed.
- The local demo and staging proxy both need binary routes. Do not flip the guest UI until the server can serve every confirmed host-provided room. Remove the obsolete guest file picker, matching-file copy, no-upload wording, old tests, and alternate code paths in the same delivery. Update README and governing design/implementation documents when this plan is approved and merged.
- Before public deployment, review content-sharing policy, server storage/bandwidth cost and retention operations. This is a release requirement, not a new step in the player's room flow.

## Review and alignment

The requested behavior is explicit. The main review choices are the bounded server capacity, the five-minute maximum download reservation, and the in-memory fallback if browser storage fails. Those choices are proposed here for user approval with the whole plan. No production implementation is authorized by this draft alone.
