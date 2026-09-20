Audience: Agent

# Anonymous rooms and reservations

A valid local NES file now creates a public or unlisted room without a naming form. Friends can open an invitation and reserve Player 2 before choosing their own file. The coordinator protects room ownership and reservation deadlines, while local play remains available if the room service fails. Shared gameplay is a later delivery slice.

## Run and inspect

Use the README's pinned Node/npm/Rust tools. Run `npm ci`, `sh scripts/foundation/prepare.sh`, then `npm run coordinator` and `npm run dev` in separate terminals. Open `http://127.0.0.1:5173`. Public is the fresh default; choose Unlisted before selecting a file when wanted. After local validation succeeds, room creation and its internal acknowledgement run automatically. Copy the invitation into another browser/tab, review the room, then Join reserves Player 2 for 120 seconds. No ROM is transferred. Local practice still uses its own controller; the reserved network role does not start synchronized gameplay.

For a built preview on port 4173, set `COORDINATOR_ORIGINS=http://127.0.0.1:4173` and configure the static server's `/coordinator/ws` proxy, or set `PUBLIC_COORDINATOR_URL` explicitly when building. Staging requires `COORDINATOR_STAGE=staging` and an explicit comma-separated `COORDINATOR_ORIGINS` allowlist of exact HTTPS client origins. The coordinator accepts `/ws` or `/coordinator/ws`; the test-only gateway in `scripts/rooms/browser-server.ts` demonstrates same-origin routing without choosing a deployment provider.

Run `npm test` for model and actual WebSocket checks, and the README's complete `timeout 60s sh scripts/preflight.sh`. With the built client and Playwright 1.58.0/Chromium installed:

```sh
python3 scripts/rooms/browser_smoke.py --output /tmp/rooms.local.json
python3 scripts/foundation/browser_smoke.py --output /tmp/foundation.local.json
```

Use `--chrome` for installed Chrome. The room suite launches its own coordinator and static gateway on private ephemeral loopback ports. It covers public/unlisted creation, invite preview, independent-client slot races, mismatch correction, cancel/retry, host settings, text rendering, close, stale creation cancellation and service failure. It inspects outgoing messages for private filenames and forbidden upload fields. It never records raw session tokens in JSON evidence; screenshots use synthetic invitations that expire when the test service exits. Application gain remains muted; no system/browser-global audio changes occur.

## Contracts and state ownership

- `packages/contracts/src/rooms.ts`: strict, metadata-only message union and validation. All commands require a request ID. Unknown fields, malformed fingerprints, control characters and binary frames are rejected. The server caps frames at 4 KiB and outgoing backlog at 64 KiB; there is no ROM/save/upload endpoint.
- `apps/coordinator/src/rooms.ts`: synchronous, in-memory ownership and transitions. Slot availability checks and claims cannot interleave. Server-generated names never use file data. Roles are host P1 and reserved guest P2; no client command promotes a reservation to established gameplay.
- `apps/coordinator/src/server.ts`: origin-checked WebSocket upgrade and authenticated session binding. Display names cannot confer authority. Tokens and invitations each use 32 random bytes. Invitations live in URL fragments and the page sets `no-referrer`; neither invite nor token is put in coordinator URLs. Public codes contain eight unambiguous characters and are allocated with collision retries. Unlisting removes the code; unlisted rooms have no public lookup path.
- `apps/client/src/room-client.ts` and `RoomPanel.tsx`: connection/operation lifetimes, recovery and accessible room controls. Cancellation invalidates pending intent. Creating is provisional for at most five seconds until the current client intent acknowledges it; provisional invitations cannot be previewed or joined. A held/stale create response cannot activate a cancelled room. A valid replacement game closes its old hosted room only after explicit confirmation and successful local validation. Invalid files preserve the previous game and room. A recovered host selecting the same exact file/build reuses its room and preserves the guest’s original lease.

`Fingerprint` is the existing local file/core/settings identity. Matching it satisfies only the local-file prerequisite; the UI explicitly states that shared gameplay is unavailable in this build. D10/D11 own peer connection, state-schema compatibility, automatic shared barriers and successful reservation promotion. D09 owns public directory/search subscriptions. No coordinator gameplay, peer contact, microphone request or fake Ready/Playing state is introduced here.

## Deadlines, authority and bounded admission

Heartbeats run every 10 seconds. A host missing them for 30 seconds becomes reconnecting and has a further 60 seconds to recover with its original session token; expiry closes the room. A pending guest retains only its original 120-second reservation deadline through mismatch, socket recovery and prerequisite failures. It receives no additional reconnect grace and cannot recover an expired reservation without a new explicit Join. Cancel releases it immediately. Each join carries a bounded intent identifier; leave is authorized against both the authenticated guest and that exact live reservation. A delayed response from a cancelled join cannot release a newer reservation, even in the same room. Kick revokes that token's access to the room. Close removes the room/invitation immediately. Server restart discards all room/session state; the client explains that an old token expired or the service restarted.

The host alone can rename, change visibility, remove the guest or close. Publishing a previously unlisted room has an explicit exposure confirmation; shared controller reassignment waits for D11's acknowledged state changes. Nicknames are optional plain text, limited to 32 characters; room names are limited to 80.

The current service admits at most 20 rooms, 100 sockets and 1,000 idle-capable sessions. Unused sessions expire after 24 hours. Each transport address has at most 20 concurrent sockets and 30 upgrade attempts per minute; the address table is capped at 1,000 entries and expires idle entries. It uses the actual transport address, not client-controlled forwarding headers. A reverse proxy therefore needs a reviewed admission configuration during D24 deployment; these development defaults must not be presented as measured public capacity.

Per session: five creates/minute, five joins/minute, twenty previews/minute and sixty operations/ten seconds. A transport-level ceiling closes sockets above 120 frames/ten seconds, including repeated unauthenticated/authentication messages. Rate rejection includes a retry duration. Unused cancellation tombstones and expired sessions are cleaned by a one-second sweep; kicked-token records are retained only while their sessions exist. A valid local game is retained after capacity/rate/service rejection. These are bounded starting admission settings within the existing planning envelope, not load or relay cost qualification.

The maintained transport is pinned to `ws` **8.21.3**, checked against its [official release](https://github.com/websockets/ws/releases/tag/8.21.3), with registry-current `@types/ws` **8.18.1**. Compression is disabled; no new client transport dependency is needed. CI uses pinned Node in the core job, installs the lockfile and runs both browser suites inside the existing shared 30-minute deadline. It retains `rooms.local.json` and `rooms.local.*.png` alongside existing artifacts. No long post-submit workload is added.

Source authority: epic #2 / D08 issue #12; reviewed plan `2e8adfcd3259f5bdffdc9a13ef9b983f78cfb965`, merged planning PR #3 at `ecf6bd4c7443526f0a163b721a351c854ee90fd4`; prerequisite D05 merged at `f248296aca30c4a2f60475e4c3e062c73577dd76`. This implements the room/reservation portions of AC-02/03/09/13 and S02/S04/S07, preserving subsequent directory, peer and shared-play dependencies.

## Combined controls verification

The D08 branch integrates D07 candidate `e7f3a1136e8752f172864013afe1698d51c07b7d`; its independent acceptance and integration are owned by the orchestrator. Combined browser evidence in `d08/` exercises both room flows and local settings. The delayed Join A → cancel → Join B → delayed A regression failed against merge `ee70e73` before the intent repair (`d08/join-race-before.txt`) and passes afterward (`d08/browser.json`). This was a pre-handoff audit repair, not an independent acceptance round.

Live main `bb7dda7f71e3edc094247cfea30f1739870c82f5` (merged PR44/46) was integrated at `c9cd91d3e9fbc56ba2452f515ec7b94c0cd2107c`, tree `21196624399e889e99d5d1c65e11d32d94f042aa`. The only merge conflict combined both rooms and featured Python syntax checks in preflight. A separate detached checkout built this tree and passed full preflight in 11.52 seconds, rooms browser in 8.94 seconds and foundation/settings browser in 14.43 seconds. Raw results are `d08/integrated-{preflight.txt,browser.json,foundation.json}`. The client bundle is byte-identical to the inspected screenshots above; the subsequent evidence commit changes documentation only. Earlier head CI is superseded, and final-head CI remains required.
