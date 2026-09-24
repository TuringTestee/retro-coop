Audience: Agent

# GKE staging deployment: current decisions and remaining gates

Retro Coop can use the selected GKE platform for a short-lived internet test, but the current repository is not deployable there yet. The web edge must preserve each player's real address, the relay needs a reachable UDP port range, and the approved $100 monthly ceiling needs more than a billing alert. This document records the deployment shape to build and the checks required before creating cloud resources.

## Source and observed state

- D24 [issue #28](https://github.com/TuringTestee/retro-coop/issues/28) and the approved [platform plan](browser-nes-platform.md) govern staging. This is staging for independent-network tests, not a public launch.
- Main `90b00a4` has a versioned Vite client build and a Node coordinator. The coordinator stores rooms and uploaded ROMs only while the service runs. One coordinator replica is required unless room ownership is redesigned.
- `admission-address.ts` trusts a forwarding header only from an explicitly listed literal proxy IP and only if the header contains one client IP. A standard Google HTTPS load balancer appends a client and load-balancer address, plus any untrusted incoming values. Direct GKE HTTPS Ingress does not satisfy this contract.
- Project `bship-164753-06152350` has billing enabled and two running Autopilot clusters in `us-central1`. A read-only namespace check of `cache-guard-test` found no Retro Coop workload. There is no public Cloud DNS zone in this project. Credits and their applicability have not been verified.

## Deployable shape to prove

1. Build an immutable client image from the pinned Node/Rust toolchains and `scripts/foundation/prepare.sh`. Build the coordinator image from the same commit. Record the client asset manifest, coordinator commit, and emulator hash together; never replace a versioned core asset in place.
2. Put the client edge and exactly one coordinator replica in an isolated `retro-coop-staging` namespace with bounded CPU, memory, ephemeral storage, upload directory and log retention. Keep coordinator port internal. Configure `COORDINATOR_STAGE=staging`, exact HTTPS `COORDINATOR_ORIGINS`, the two approved `COORDINATOR_EMPTY_OFFERS`, and required custom upload. Keep secrets in Kubernetes Secrets or a managed secret store, never in `PUBLIC_` variables or images.
3. Prefer a regional external passthrough Network Load Balancer with `externalTrafficPolicy: Local` for the HTTPS edge. Google documents that this preserves the transport client IP. A controlled same-Pod proxy can terminate TLS, serve immutable client files, and overwrite `X-Forwarded-For` with its transport peer before forwarding `/coordinator/ws` and `/coordinator/rooms/*/rom` to the coordinator on loopback. Only that loopback proxy is trusted by `COORDINATOR_TRUSTED_PROXIES`. Reject direct access to the coordinator and prove forged incoming headers cannot change admission identity. Do not use a default HTTPS Ingress without replacing this boundary and retesting it.
4. Use a separate, short-lived TURN endpoint for the forced-relay staging test. Autopilot does not allow fixed host ports, while a TURN relay needs a reachable allocation port range; a normal single-port Kubernetes Service is insufficient. Compare a bounded GCE coturn VM with a managed TURN provider against the approved cost ceiling and existing `TURN_SECRET` credential contract before selecting one. Keep relay-only policy from falling back to direct when the relay is unavailable.
5. Make the HTTPS hostname and certificate explicit before deployment. No public DNS zone is available in the inspected project. Use a user-controlled hostname and a valid certificate; an unverified wildcard DNS service is not a release dependency.

## Cost gate before any provisioning

Use a current-price worksheet for requested Autopilot vCPU, memory and storage hours; one or more load-balancer forwarding rules and bytes; static asset, upload and log bytes; TURN fixed charge and worst-case relayed GiB; external egress; and DNS/certificate charges. Model the actual short staging window and the accidental 30-day left-running case. Include the existing project's charges only when they are incremental to Retro Coop, and verify whether credits apply rather than subtracting assumed credits.

Google's alerts-only budgets do not stop spending, and its current preview spend cap does not cover GKE. The deployment needs bounded room/connection/relay admission, workload and storage quotas, a time-limited shutdown/teardown path, and a measured test before claiming the $100 ceiling. A budget alert remains useful but is not the enforcement proof. Do not provision if the worst-case left-running calculation or unbounded network use can exceed the ceiling without an accepted cutoff.

## Acceptance sequence

1. In a detached checkout, build both images at one commit and run the static site, coordinator, proxy and chosen TURN service locally. Test health, WebSocket upgrade, custom upload/download, generated immutable asset URLs, forged forwarding headers and multiple real client addresses. Preserve the README preflight and current CI budget.
2. Review the exact Kubernetes/relay manifests, hostname, certificate, secret names, resource limits, current-price worksheet, credit status and teardown command. Confirm the selected cluster and that no unrelated namespace or workload changes.
3. Deploy staging for a bounded window. From two independent internet networks, create and join a custom game, verify automatic guest download, Prepare, Start, matching shared frames, text and opt-in voice. Repeat with forced relay, then test pause/reconnect/leave. Capture sanitized endpoint, route, timing, status and recovery evidence.
4. Exercise old/new client and coordinator rollback. Existing rooms may close on coordinator restart; show the player-facing recovery. Remove staging resources and verify load balancer, IP, VM/relay and secret cleanup. Post actual measured costs and results on #28. Keep the epic open for broader release validation.

## Sources checked 2026-09-24

- [Google load balancer forwarding headers](https://docs.cloud.google.com/load-balancing/docs/https#x-forwarded-for_header)
- [GKE LoadBalancer source-IP behavior](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/service-load-balancer#effect_of_externaltrafficpolicy)
- [Autopilot host-port restrictions](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/autopilot-security)
- [GKE Autopilot prices](https://cloud.google.com/kubernetes-engine/pricing) and [load-balancer prices](https://cloud.google.com/load-balancing/pricing)
- [Google budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets) and [eligible spend-cap services](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps)
