# Relay status integrated proof

Two local Chromium browsers played the same NES game through direct, deliberate Relay only, and Standard-to-relay routes. The fixed room panel displayed the route message during active play, including at a 390 × 844 viewport. This is local browser evidence; public-network TURN qualification remains part of D24.

## Setup and commands

Source UI revision `40d00a6878fd37169249ed9a77b97c9209ee129c`; Chromium `145.0.7632.6`; Node `24.13.1`; Ubuntu Linux. `sh scripts/foundation/prepare.sh && npm run build:staging` built the public browser entry point. Coturn `4.6.1` came from Ubuntu packages extracted into `/tmp/retro-coturn`, with its libraries supplied through `LD_LIBRARY_PATH`. The tests launched the real local browser server and two separate Chromium processes. Initial viewport was 1366 × 682; the host was also checked at 390 × 844 while playing. The ROM was the included diagnostic NES.

```sh
python3 scripts/gameplay/browser_smoke.py --seconds 8 --short-viewport --screenshots --output /tmp/retro-relay-direct-40d.json
LD_LIBRARY_PATH=/tmp/retro-coturn/usr/lib/x86_64-linux-gnu python3 scripts/gameplay/browser_smoke.py --relay --turnserver /tmp/retro-coturn/usr/bin/turnserver --seconds 8 --short-viewport --screenshots --output /tmp/retro-relay-forced-40d.json
LD_LIBRARY_PATH=/tmp/retro-coturn/usr/lib/x86_64-linux-gnu python3 scripts/gameplay/browser_smoke.py --standard-fallback --turnserver /tmp/retro-coturn/usr/bin/turnserver --seconds 8 --short-viewport --screenshots --output /tmp/retro-relay-standard-40d.json
LD_LIBRARY_PATH=/tmp/retro-coturn/usr/lib/x86_64-linux-gnu python3 scripts/peer/browser_smoke.py --turnserver /tmp/retro-coturn/usr/bin/turnserver --output /tmp/retro-relay-peer-40d.json
```

The Standard fallback test retains Standard in the app but forces the browser's ICE transport to relay. This models a direct route unavailable to the browser and proves that the UI responds to the selected relay candidate pair. It does not claim to reproduce a particular firewall. The gameplay test asserts `is_visible()` on both connection messages while the room game is `playing`, hides the host element to prove the visibility check rejects hidden text, restores it, and checks for horizontal overflow at mobile width.

## Results and visuals

| Route and journey | Active play | Matching final frame/hash | Page errors | Screenshot |
| --- | ---: | --- | ---: | --- |
| Direct, existing copy | 8.02 s | 517 / `42d41ecc8264…` | 0 | [Direct while playing](relay-status-proof/direct-playing.png) |
| Relay only, D2 | 8.02 s | 517 / `42d41ecc8264…` | 0 | [Relay only while playing](relay-status-proof/relay-only-playing.png) |
| Standard fallback, D1 | 8.02 s | 517 / `4d23441a11f5…` | 0 | [Standard relay while playing](relay-status-proof/standard-relay-playing.png) · [390 px view](relay-status-proof/standard-relay-mobile.png) |

Both peers had the same final frame hash in each run. Each run captured at least 8.02 seconds of active shared play, verified the selected route and visible text, and passed the hidden-element negative check. The peer recovery run verifies Relay only reload recovery, unavailable relay without a direct fallback, capacity denial before peer creation, Stay preserving the room/lease, Retry reconnecting over relay, policy changes, and leave freeing relay capacity. Its [JSON result](relay-status-proof/peer-recovery.json) records `result: pass`, a selected relay pair on both sides after reload and retry, no page errors, and 66.21 seconds elapsed. See [relay unavailable](relay-status-proof/relay-unavailable.png) and [retry over relay](relay-status-proof/relay-retry.png).

Public HTTPS, two independent networks, instance memory under TURN load and a real AWS relay are separate D24 gates; these local results do not close them.
