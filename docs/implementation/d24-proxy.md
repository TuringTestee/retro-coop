Audience: Agent

# Coordinator proxy admission

An explicit proxy boundary preserves each browser address for admission limits without trusting headers supplied by direct clients. This prepares D24 deployment; it does not provision a public service or establish measured public capacity.

## One owner and supported topology

`apps/coordinator/src/admission-address.ts` owns literal-address validation, canonical quota keys and the trust decision. `server.ts` uses its result before upgrading a WebSocket; existing origin, socket, session and rate limits are unchanged. `main.ts` passes the validated configuration into the server. No client address, forwarding header, invitation or chat content is added to logging. Startup configuration logging includes the operator-configured trusted proxy addresses.

By default no proxy is trusted: only the transport peer determines the admission address. `COORDINATOR_TRUSTED_PROXIES` accepts comma-separated literal IP addresses, without hostnames, CIDR ranges, wildcards or ports. The peer must match an explicitly configured address before its `X-Forwarded-For` header is used. That trusted path must contain exactly one valid client IP; missing, malformed or chained values fail admission. IPv6 spellings and IPv4-mapped forms normalize to the same quota key. Other forwarding headers grant no authority.

This supports one controlled reverse proxy that overwrites the header. It intentionally does not infer trust through an arbitrary proxy chain. Configure the coordinator listener/firewall so only the chosen proxy can reach that trusted path; never mark an uncontrolled intermediary or client network trusted. A proxy topology change needs an explicit configuration review and the same admission checks.

## Deployment configuration example

For a same-machine HTTPS proxy connecting to the coordinator at `127.0.0.1:8787`, keep `COORDINATOR_HOST=127.0.0.1` and set `COORDINATOR_TRUSTED_PROXIES=127.0.0.1`. Set `COORDINATOR_STAGE=staging` and the exact deployed HTTPS origin in `COORDINATOR_ORIGINS`. In the existing TLS server, an Nginx location can forward only the room endpoint:

```nginx
location = /coordinator/ws {
    proxy_pass http://127.0.0.1:8787;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header X-Forwarded-For $remote_addr;
}
```

The assignment overwrites any incoming header; do not append it with `$proxy_add_x_forwarded_for`. This is a configuration example, not an executed HTTPS deployment. Provider selection/access, TLS installation, concrete proxy rehearsal, relay/cost enforcement, rollback and independent-network checks remain under issue #28.

## Evidence and reproduction

Baseline `bc60beda8aeaa6523bfe72f5f07e3db1bf842c7a` applies its 20-concurrent-socket address limit to all clients behind the same proxy. The original [before output](d24-proxy/before.txt) fails at the 21st distinct client (HTTP 403 instead of WebSocket 101). The other before failures show the absent explicit trust/configuration behavior. To reproduce, copy [baseline-test.ts](d24-proxy/baseline-test.ts) into `apps/coordinator/src/proxy.test.ts` in a detached baseline checkout with Node dependencies installed, then run `node --test apps/coordinator/src/proxy.test.ts`.

Candidate `b3f16ca` passes all 55 Node tests and type checking ([output](d24-proxy/node.txt)). Real loopback WebSockets establish 21 distinct clients through the explicitly trusted peer, still reject the 21st connection for one client, and reject attempts to split an untrusted transport address using different forged headers. Trusted missing/ambiguous values fail; canonical IPv6/mapped-address checks cover equivalent quota keys. These tests exercise actual server upgrades, not merely the address helper. No visual behavior changes, so screenshots are unnecessary. The full final preflight, CI and independent review remain pending; current status belongs to the PR.

## Scope and authority

This bounded technical preparation follows D24/#28 and approved epic #2 / planning PR #3 (approved head `2e8adfcd3259f5bdffdc9a13ef9b983f78cfb965`, merged governing revision `ecf6bd4c7443526f0a163b721a351c854ee90fd4`). The observed shared-proxy ceiling is its concrete cause. It does not change the product's anonymous admission or privacy policy. Root owns this branch and merge under the existing repository-scoped policy B, after fresh independent acceptance and passing required checks. The issue remains open for actual staging acceptance.
