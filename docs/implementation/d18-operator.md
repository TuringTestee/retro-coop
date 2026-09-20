Audience: Agent

# Restricted operator removal and admission blocks

An operator can remove a room or temporarily disconnect and block an address through a private local tool. Each mutation first names its target and requires confirmation. The public website has no operator endpoint or dashboard; affected players retain their local game and receive removal or restriction feedback.

## Scope and shared owners

This implements the remaining operational slice of D18/#22, approved epic #2, design S27 and AC-10/11. Approved head `2e8adfcd3259f5bdffdc9a13ef9b983f78cfb965` and merged planning PR #3 remain authoritative. Root owns `feat/d18-operator` and its merge under the existing repository-scoped policy B. Hosting, deployment rehearsal and capacity/cost qualification remain D24/D22 work.

`Rooms` owns room removal, guest release and session revocation. The coordinator's existing admission map owns the canonical transport/proxy address, connection set, quota and temporary block. No second forwarding-header interpretation is introduced. Revocation verifies the current connection's sender, so an obsolete socket cannot revoke a session that moved to another connection. Block confirmation also captures the address subject's connection revision; changed connections require a new preview.

`operator.ts` owns one-use, 30-second confirmation tickets and the private HTTP-over-Unix-socket listener. Tickets are bounded to 64 pending entries; bodies are limited to 4 KiB, operator connections to eight, and request/socket deadlines to five seconds. Address blocks last 1–3,600 seconds. They reject new connections and revoke active sessions on that address; other addresses retain access. All state is ephemeral, including blocks, and coordinator restart clears it. This is not a promise to identify or permanently ban an anonymous person.

## Authentication and configuration

The listener is disabled unless `COORDINATOR_OPERATOR_DIR` is set. Its directory must already exist at an absolute, canonical path, belong to the coordinator service UID, have mode `0700`, and contain no symlink path components. The socket has mode `0600`. The service UID and privileged root authenticate through OS filesystem access. Use the deployment's existing restricted service-user access to run the CLI; this does not add public accounts or operator passwords. This optional tool requires a Unix coordinator host; browser support is unchanged.

Create the private directory as the service user using the deployment's normal provisioning method. For an example directory `/run/retro-coop/operator`, start with:

```sh
COORDINATOR_OPERATOR_DIR=/run/retro-coop/operator npm run coordinator
node apps/coordinator/src/operator-cli.ts /run/retro-coop/operator list
node apps/coordinator/src/operator-cli.ts /run/retro-coop/operator remove-room ROOM_ID
node apps/coordinator/src/operator-cli.ts /run/retro-coop/operator block-address SUBJECT_ID 600
```

Replace IDs with the private listing's exact values. The CLI displays the room ID/name or address/subject ID/connection count and action, then asks for literal `CONFIRM`. Anything else cancels; expired, reused or stale confirmations fail without applying the change. Blocking an address affects everyone sharing it, including users behind the same NAT. First use room removal when that is the intended target.

The private listing exposes room labels/IDs and admission addresses needed for the action. It omits authentication tokens, private invitations, chat and ROM/core hashes. Keep this terminal output within operator access; the coordinator does not add it to application logs or public telemetry. Existing startup logging still includes configured proxy addresses. Never forward this socket through the public reverse proxy. The main TCP listener continues to return 404 for `/operator`, and the public WebSocket schema rejects operator commands.

The tool never deletes an existing socket path to force startup. An occupied or stale path fails startup; investigate ownership and the stopped service before removing a stale socket during deployment maintenance. Normal shutdown closes the private listener with the public coordinator. Actual staging provisioning, access delegation and operator rehearsal remain pending until a hosting environment is selected.

## Verification

`node --test apps/coordinator/src/operator.test.ts apps/coordinator/src/proxy.test.ts` exercises actual private-socket requests and public WebSockets, public-route/schema rejection, directory permissions, exact target confirmation, cancellation, expiry, bounded pending tickets, stale subject and stale connection ownership, privacy, token revocation, block expiry and the actual process startup/shutdown path. The full existing Node suite and type checking also apply.

`python3 scripts/rooms/operator_smoke.py --output /tmp/operator.local.json` uses the built product, real private CLI confirmation, peer connections and fake-microphone audio transport. It checks room removal, public feedback, peer/microphone teardown, unchanged local load/import counts, and address-block feedback. Game audio is muted in the app and incoming voice volume is set to zero; global browser audio muting is removed. This proves transport/teardown, not physical-microphone or human-listening quality. CI runs this check under a separate 60-second limit inside the unchanged shared 30-minute deadline, retaining JSON and screenshots.

The [actual browser result](d18-operator/browser.json) passed in **5.12 seconds** with full bundled Chromium 145.0.7632.6. [Candidate metadata](d18-operator/candidate.json) pins source and actual client/core file hashes; the [build output](d18-operator/build.txt) and [raw browser output](d18-operator/browser.txt) are retained. Inspected [before](d18-operator/before.png), [removed](d18-operator/removed.png) and [blocked](d18-operator/blocked.png) screenshots show the active session followed by distinct removal/restriction feedback with the local game retained. Private invitation text is masked. All eight [focused operator tests](d18-operator/focused.txt) pass, including real process startup/shutdown. Current preflight, CI and independent acceptance are recorded in [issue #22 and its linked PR](https://github.com/TuringTestee/retro-coop/issues/22).

The final integration includes actual main `d54b985dd576d57281aa03e9390e343ed6b87b05`, including the accepted banked-memory core. The [integrated browser proof](d18-operator/integrated/browser.json) passes in **4.40 seconds** with the accepted core artifact; [metadata](d18-operator/integrated/candidate.json) identifies every client build file. Inspected [before](d18-operator/integrated/before.png)/[blocked](d18-operator/integrated/blocked.png) screenshots preserve the same public feedback. The [integrated source preflight](d18-operator/integrated/preflight.txt) passed in **36.93 seconds** with 28 native and 67 Node tests; the final evidence-commit gate is published in the PR handoff.
