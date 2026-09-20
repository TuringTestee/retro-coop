Audience: Agent

# Peer connectivity and connection privacy

Friends can now establish an encrypted browser-to-browser connection after reserving Player 2. Standard can connect directly; Relay only requires a relay on both ends. The choice appears before file selection and Join and is shared with Settings. This delivery proves transport, not synchronized gameplay: the guest keeps the original reservation until D11's separate gameplay barrier succeeds.

## Run and reproduce

Use the README's pinned Node, Rust and browser setup. `npm ci`, `sh scripts/foundation/prepare.sh`, `npm run build`, then coordinator/client development servers give direct local connectivity without a TURN provider. Select Relay only with no configured service to inspect honest denial and retry. Existing local games survive connection failures.

A configured coordinator accepts `TURN_URLS` (comma-separated turn/turns URLs), `TURN_SECRET` (at least 32 characters), and `TURN_ROOM_LIMIT` (0–20). These are operator settings, not browser-exposed shared secrets. Coturn must use the matching REST authentication secret and enforce its own allocation/bandwidth quotas. The service issues member-only credentials with 300-second expiry; it never logs credentials or SDP. TURN allocation quotas must include transient allocations from replaced ICE epochs, not only current room count; browser closure does not guarantee immediate relay deallocation. Zero configured capacity denies Relay only before creating peers. Standard may use direct connectivity when relay capacity is unavailable; Relay only never changes to Standard automatically.

```sh
npm test
timeout 60s sh scripts/preflight.sh
python3 scripts/peer/browser_smoke.py --output /tmp/peer.local.json
python3 scripts/rooms/browser_smoke.py --output /tmp/rooms.local.json
python3 scripts/foundation/browser_smoke.py --output /tmp/foundation.local.json
```

The peer suite requires Playwright 1.58.0, Chromium and `turnserver` (coturn). Use `--chrome` for installed Chrome and `--turnserver /path/to/turnserver` for an unprivileged local extraction. It launches a temporary, loopback-only authenticated relay with bounded allocations/bandwidth and random credentials in a mode-0600 temporary file. No public service or account is provisioned. CI installs coturn on its disposable runner and executes the suite inside the existing shared 30-minute deadline. Version and aggregate route evidence are retained; raw SDP, tokens, credentials and candidate addresses are not published.

## Ownership and lifecycle

- `packages/contracts/src/peer.ts` owns privacy policy, stricter-policy combination, negotiation limits and signaling schemas. Generic structural validation lives in `protocol-validation.ts`; fingerprint identity remains solely in `fingerprint.ts`.
- `apps/coordinator/src/peer.ts` owns current negotiation epochs and relay admission. `Rooms` remains the sole membership/reservation authority. Only the authenticated current room members can signal; replacing a socket revokes the old sender's authority. Signaling is immediately forwarded and not retained as history.
- The coordinator first sends Prepare with the effective policy and scoped ICE configuration. Both members acknowledge configuration before Start permits an offer, local description or ICE exchange. A policy or socket/membership change invalidates the old epoch and closes its transport. Old candidates, role-forged descriptions and non-relay candidates in relay mode are rejected. Each epoch permits one host offer and one guest answer; future media negotiation uses a separately reviewed extension.
- `apps/client/src/peer.ts` owns the RTCPeerConnection and reliable ordered control channel. The browser uses standard WebRTC DTLS/SCTP encryption, with no custom cryptography. A nonce round-trip over the real channel verifies transport. An optional channel-ready callback is the D11 integration boundary; it does not promote membership or start the emulator together.
- App owns the displayed policy; inline and Settings controls reuse it. The preference persists in this tab's session storage so reload cannot silently weaken Relay only. Authentication carries the displayed policy before a recovered room can prepare peers. Changing policy pauses local play and reconnects peers; gameplay resume remains explicit.

Preparations expire after 15 seconds and connection attempts after another 20 seconds. Retry creates a fresh epoch without extending the guest's original 120-second lease. Cancel, kick, room close, reservation expiry and signaling loss tear down peer resources. A failed peer connection leaves local game state intact. Server admission bounds sessions/signaling as before, with additional per-member policy/retry limits and bounded SDP/candidate payloads. Transport frame allowance is 16 KiB for signaling; ordinary room metadata remains capped at 4 KiB.

## Evidence limits and remaining release work

Local browser tests inspect the selected ICE candidate pair and positive bidirectional bytes after the channel round-trip. They cover direct host candidates, forced relay on both ends, stricter guest preference, relay-only reload recovery, unavailable relay, capacity denial before any peer is created, and explicit retry after capacity is released. Node tests exercise authentication, epoch invalidation, the two-sided policy acknowledgement, forged role/candidate rejection, timeout and unchanged reservation leases. Existing player/settings and room suites remain required.

These loopback checks do not establish internet NAT coverage, public-provider quota enforcement, pricing, geographical latency, release browser-matrix success rates or the public-network startup budget. Those remain D21/D24 and the approved launch qualification. The 20-room coordinator admission envelope is not a measured public relay capacity. Credential renewal for established gameplay and shared recovery must be integrated with D11; D10 reservations expire before the current credential lifetime.

Primary API references: [W3C WebRTC](https://www.w3.org/TR/webrtc/) defines ICE transport policy and gathering; [coturn configuration](https://github.com/coturn/coturn/blob/master/examples/etc/turnserver.conf) and [REST authentication example](https://github.com/coturn/coturn/blob/master/examples/scripts/restapi/secure_relay_secret.sh) define short-lived credentials and quotas. No additional browser networking package is introduced.

Source authority: epic #2 and D10 #14; approved plan head `2e8adfcd3259f5bdffdc9a13ef9b983f78cfb965`, merged planning PR #3 `ecf6bd4c7443526f0a163b721a351c854ee90fd4`; D08 merged `c82957f`, integrated base `564bc37`. Scope is S09/S28 and AC-10/11 connectivity; public launch and gameplay synchronization remain separately gated.

During development, rapid policy changes hit coturn's allocation bandwidth quota (ICE 486). Coturn reserves each allocation's configured maximum bandwidth, including briefly overlapping replaced allocations: the initial fixture reserved 1 MB/s each against a 4 MB/s global allowance. The corrected fixture aligns 16 allocations with 100 KB/s each and a 1.6 MB/s global bound, 4 allocations per credential, 50 relay ports and one relay thread. Application room admission remains one in the capacity test. This preserves the denied-admission workload and makes the test infrastructure limits consistent; it does not raise public capacity or any operating budget.
