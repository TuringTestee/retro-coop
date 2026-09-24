Audience: Agent

Retro Coop has a tested HTTPS package for a short internet trial. This document tracks the work needed to run it on GKE with a relay, a valid certificate, cost limits and cleanup. No cloud resources have been created.

# GKE staging deployment: current decisions and remaining gates

The approved $100 monthly ceiling needs more than a billing alert.

## Source and observed state

- D24 [issue #28](https://github.com/TuringTestee/retro-coop/issues/28) and the approved [platform plan](browser-nes-platform.md) govern staging. This is staging for independent-network tests, not a public launch.
- Main `703a7ce` has versioned client and coordinator images, a real proxy transfer probe, a bounded relay preparation path, and one shared five-minute PR gate. The coordinator stores rooms and uploaded ROMs only while the service runs. One coordinator Pod is required unless room ownership is redesigned.
- `admission-address.ts` trusts a forwarding header only from an explicitly listed literal proxy IP and only if the header contains one client IP. A standard Google HTTPS load balancer appends a client and load-balancer address, plus any untrusted incoming values. Direct GKE HTTPS Ingress does not satisfy this contract.
- Project `bship-164753-06152350` has billing enabled and two running Autopilot clusters in `us-central1`. A read-only namespace check of `cache-guard-test` found no Retro Coop workload. There is no public Cloud DNS zone in this project. Credits and their applicability have not been verified.

## Deployable shape to prove

1. Build an immutable client image from the pinned Node/Rust toolchains and `scripts/foundation/prepare.sh`. Build the coordinator image from the same commit. Record the client asset manifest, coordinator commit, and emulator hash together; never replace a versioned core asset in place.
2. Put the client edge and exactly one coordinator in an isolated `retro-coop-staging` namespace with bounded CPU, memory, ephemeral storage, upload directory and log retention. Keep coordinator port internal. Configure `COORDINATOR_STAGE=staging`, exact HTTPS `COORDINATOR_ORIGINS`, the two approved `COORDINATOR_EMPTY_OFFERS`, and required custom upload. Keep secrets in Kubernetes Secrets or a managed secret store, never in `PUBLIC_` variables or images.
3. Prefer a regional external passthrough Network Load Balancer with `externalTrafficPolicy: Local` for the HTTPS edge. Google documents that this preserves the transport client IP. A controlled same-Pod proxy can terminate TLS, serve immutable client files, and overwrite `X-Forwarded-For` with its transport peer before forwarding `/coordinator/ws` and `/coordinator/rooms/*/rom` to the coordinator on loopback. Only that loopback proxy is trusted by `COORDINATOR_TRUSTED_PROXIES`. Reject direct access to the coordinator and prove forged incoming headers cannot change admission identity. Do not use a default HTTPS Ingress without replacing this boundary and retesting it.
4. Use a separate, short-lived TURN endpoint for the forced-relay staging test. Autopilot does not allow fixed host ports, while a TURN relay needs a reachable allocation port range; a normal single-port Kubernetes Service is insufficient. The selected e2-micro coturn VM has a six-hour self-delete action, narrow tester firewall, 16-allocation quota including reconnect overlap, and 3 Mbit/s outbound traffic shaping. It uses the existing `TURN_SECRET` credential contract. Keep relay-only policy from falling back to direct when the relay is unavailable.
5. Reserve a public regional IPv4 address before deployment and issue a valid short-lived certificate for that IP. Let's Encrypt currently supports IP certificates valid for 160 hours; Certbot 5.4+ supports issuance through an HTTP challenge. The edge serves only `/.well-known/acme-challenge/` on port 80. End the planned test inside one certificate lifetime; an extension needs renewed certificate evidence. A user-controlled hostname remains an option, but no public DNS zone was found in the inspected project.

## Cost gate before any provisioning

Use current list prices and count only incremental Retro Coop resources; no assumed credits are deducted. The reviewed trial is six hours, after which the GKE Job stops and the GCE relay VM deletes itself. Manual teardown should happen earlier. Model a 31-day mistake that leaves the forwarding rule and reserved IP behind, since those do not stop with the Job.

| Six-hour trial item | Calculation at checked `us-central1` list prices | Upper scenario |
|---|---:|---:|
| Edge replies | 256 KiB/s × six connections × two admitted IPv4 addresses × six hours = 63.28 GiB | $14.56 at the highest listed $0.23/GiB internet tier |
| TURN replies | 3 Mbit/s traffic shaper × six hours = 7.54 GiB | $1.74 at $0.23/GiB |
| Load-balancer response processing | 63.28 GiB × $0.008/GiB | $0.51 |
| Job Pod, VM, VM IPv4 | 0.5 vCPU/1 GiB Pod, e2-micro and its IPv4 for six hours | under $0.30 before disk |
| Stranded forwarding rule and idle IPv4 | 744 hours × ($0.025 + $0.01); counting both is conservative because the IP is free while attached to the rule | $26.04 |
| Inbound load-balancer traffic scenario | Four TiB × $0.008/GiB | $32.77 |
| Storage, image registry and logs allowance | Reserve beyond the above line items | $10.00 |
| **Modeled total** | No discounts or credits assumed | **about $85.92** |

The four-TiB inbound line is a scenario, not an enforced limit. Public ACME port 80 briefly accepts requests from any IP, and GKE's passthrough load balancer has no configured absolute byte cutoff. The $100 ceiling therefore cannot be guaranteed solely by these controls; a bill alert also does not stop spending, and Google's preview spend cap does not cover GKE. Before provisioning, obtain explicit acceptance of this residual billing risk or replace the public-IP certificate path with an enforceable ingress cap. Watch ingress and cost during the trial, close ACME exposure immediately after validation, and run teardown on any unexpected traffic. Actual charges and credit applicability must be checked after the trial.

## Acceptance sequence

1. In a detached checkout, build both images at one commit and run the static site, coordinator, proxy and chosen TURN service locally. Test health, WebSocket upgrade, custom upload/download, generated immutable asset URLs, forged forwarding headers and multiple real client addresses. Preserve the README preflight and current CI budget.
2. Review the exact Kubernetes/relay manifests, hostname, certificate, secret names, resource limits, current-price worksheet, credit status and teardown command. Confirm the selected cluster and that no unrelated namespace or workload changes.
3. Deploy staging for a bounded window. From two independent internet networks, create and join a custom game, verify automatic guest download, Prepare, Start, matching shared frames, text and opt-in voice. Repeat with forced relay, then test pause/reconnect/leave. Capture sanitized endpoint, route, timing, status and recovery evidence.
4. Exercise old/new client and coordinator rollback. Existing rooms may close on coordinator restart; show the player-facing recovery. Remove staging resources and verify load balancer, IP, VM/relay and secret cleanup. Post actual measured costs and results on #28. Keep the epic open for broader release validation.

## Prepared deployment package

- `deploy/staging/k8s/base` defines one Job Pod with an Nginx edge and loopback-only coordinator, a regional external passthrough Service with `externalTrafficPolicy: Local`, and namespace quota. The Job stops the Pod after six hours with no retry; the Service and other billable resources still require teardown. The Pod does not mount a Kubernetes API token. TLS and TURN values come from named Secrets; the coordinator's exact HTTPS Origin comes from a generated ConfigMap.
- `scripts/staging/render_k8s.py` requires two image digests, a public reserved IP and up to two tester `/32` addresses. It renders locally through `kubectl kustomize`; it never applies resources. `--acme-bootstrap --allow 0.0.0.0/0` temporarily exposes only port 80 for certificate issuance, with no public HTTPS port. Re-render with the tester addresses immediately after issuance.
- `scripts/staging/acme_hook.sh` writes one HTTP challenge into the edge Pod, checks public reachability, and removes it afterward. The hook accepts only the configured IP and a single safe token. `scripts/staging/container_smoke.sh`, `render_smoke.py`, `acme_hook_smoke.py` and `kubernetes_smoke.sh` check the edge, render boundaries and both containers' Kubernetes startup without cloud access. The Kubernetes smoke imports the exact candidate images into a disposable K3s node, creates only temporary Secrets, applies the rendered workload from a default namespace context, and waits for both containers to become Ready.
- `deploy/staging/cloudbuild.yaml` describes both image targets at one source revision. Before submitting it, use a clean, reviewed commit, confirm the isolated Artifact Registry repository and builder permissions, and record the resulting digests. The rendered Kubernetes manifest must use those digests, not mutable tags.
- `scripts/staging/prepare_cloud.sh` performs those checks from clean, published `main`, creates only the named immutable-tag repository and regional IPv4 address, builds both images at that revision, and prints their exact digest references. Its CLI mock smoke proves failed inventory queries stop before creation, a missing build tag stops before address reservation, and the successful command uses one revision. It has not been run against Google Cloud. If it stops after creating a resource, run `teardown.sh` and inspect the named resources before retrying.
- `scripts/staging/provision_turn.sh` creates a dedicated VPC, a tester-only TURN rule, an operator-only SSH rule, and an e2-micro relay VM using a dated Debian image and a six-hour delete action. `render_turn.py` writes a mode-0600 coturn configuration from the same exact 64-character hexadecimal secret used by the coordinator. `configure_turn.sh` installs coturn and persistent systemd traffic shaping on that VM. `teardown.sh` deletes only the named staging namespace, VM, firewall, VPC, reserved IP and isolated image repository, then checks for leftovers. With coturn's client utility available, `turn_smoke.py` proves an authenticated local allocation returns the configured public relay address and a wrong secret is rejected; `turn_operator_smoke.py` verifies create/delete command wiring against disposable CLI mocks. None of these tests proves that Google Cloud accepted the commands or that public relay packets reach a peer.

### Relay setup after the spending decision

These steps are prepared but have not been executed. Confirm the project, `cache-guard-test` cluster, two public tester `/32` addresses and one operator `/32` address. Confirm `retro-coop-staging` does not already own a namespace, VPC, VM, reserved address or image repository. Set `TESTER_ONE`, `TESTER_TWO` and `OPERATOR_CIDR` to the full `/32` values. Use a private directory outside Git, disable shell tracing and create an exact 64-character secret file named `turn-secret`:

```sh
PRIVATE_DIR=$(mktemp -d)
umask 077
printf '%s' "$(openssl rand -hex 32)" > "$PRIVATE_DIR/turn-secret"
```

Record only its fingerprint; do not print or commit its contents.

1. Run `sh scripts/staging/provision_turn.sh "$STAGING_PROJECT" us-central1-a "$TESTER_ONE" "$TESTER_TWO" "$OPERATOR_CIDR"`. The script prints the VM's private/public addresses and termination timestamp. If any resource is left after an error, run the teardown script immediately.
2. Set `TURN_PUBLIC_IP` and `TURN_PRIVATE_IP` to the addresses returned by the VM describe command. Copy the renderer, VM setup script and owner-only secret to the VM, then configure it from the operator address:

```sh
gcloud compute scp --project="$STAGING_PROJECT" --zone=us-central1-a --scp-flag=-p \
  scripts/staging/render_turn.py scripts/staging/configure_turn.sh "$PRIVATE_DIR/turn-secret" \
  retro-coop-staging-turn:~/
gcloud compute ssh retro-coop-staging-turn --project="$STAGING_PROJECT" --zone=us-central1-a \
  --command="sudo sh ./configure_turn.sh '$TURN_PUBLIC_IP' '$TURN_PRIVATE_IP' ./turn-secret"
```

Verify `systemctl is-active retro-coop-turn.service`, `tc qdisc show`, the recorded coturn version and a real authenticated TURN allocation. The setup removes the transferred secret file after creating coturn's owner-only configuration; the local file remains until the coordinator Secret is created.
3. Create `retro-coop-staging-turn` in the staging namespace from that exact local file. Do not display the generated Secret YAML:

```sh
kubectl -n retro-coop-staging create secret generic retro-coop-staging-turn \
  --from-file="TURN_SECRET=$PRIVATE_DIR/turn-secret" \
  --from-literal="TURN_URLS=turn:$TURN_PUBLIC_IP:3478?transport=udp,turn:$TURN_PUBLIC_IP:3478?transport=tcp" \
  --dry-run=client -o yaml | kubectl -n retro-coop-staging apply -f -
```

The coordinator's `TURN_ROOM_LIMIT=2` and coturn's allocation quota must both be present before any Relay only test. Remove the local secret file after both endpoints are configured and validated.
4. After the six-hour window or any failed setup, run `sh scripts/staging/teardown.sh "$STAGING_PROJECT"`. It stops the relay VM first, waits for the namespace Service to disappear before releasing the IP, then removes and verifies the named network and image resources. Record the command output, measured billing and actual browser route evidence on #28.

### Certificate bootstrap and shutdown sequence

These are operator steps for the reviewed deployment, not commands already run. Set `STAGING_PROJECT`, `STAGING_IP`, `EDGE_IMAGE` and `COORDINATOR_IMAGE` from the reserved address and built image digests. Confirm the selected `kubectl` context points at `cache-guard-test` in `us-central1`; a different cluster requires a fresh environment check. Keep the Secret input files off Git and out of command output. Create the TURN Secret only after its endpoint and credential are selected; it must contain `TURN_URLS` and `TURN_SECRET`.

1. On reviewed, clean `main`, run `sh scripts/staging/prepare_cloud.sh "$STAGING_PROJECT"` after the final spending decision. Record its `EDGE_IMAGE`, `COORDINATOR_IMAGE` and `STAGING_IP` values; all image references must end in `@sha256:<64 hex digits>`. The script checks `cache-guard-test` is running and fails before creation if the named repository or address already exists. Confirm that the account used by Cloud Build can push to this isolated repository; a permission failure requires teardown.
2. Confirm the current `kubectl` context is `cache-guard-test` in `us-central1`. Create the namespace and a one-day bootstrap certificate with an IP Subject Alternative Name; keep the key in the private directory introduced above:

```sh
kubectl create namespace retro-coop-staging
openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 1 \
  -subj "/CN=$STAGING_IP" -addext "subjectAltName=IP:$STAGING_IP" \
  -keyout "$PRIVATE_DIR/bootstrap.key" -out "$PRIVATE_DIR/bootstrap.crt"
kubectl -n retro-coop-staging create secret tls retro-coop-staging-tls \
  --key="$PRIVATE_DIR/bootstrap.key" --cert="$PRIVATE_DIR/bootstrap.crt"
```

Create the TURN Secret using the relay setup command above. Render and inspect the bootstrap manifest before applying it; this mode exposes only the certificate challenge on port 80, with no public HTTPS port:

```sh
python3 scripts/staging/render_k8s.py --public-ip "$STAGING_IP" \
  --edge-image "$EDGE_IMAGE" --coordinator-image "$COORDINATOR_IMAGE" \
  --acme-bootstrap --allow 0.0.0.0/0 > "$PRIVATE_DIR/bootstrap.yaml"
kubectl apply -f "$PRIVATE_DIR/bootstrap.yaml"
kubectl -n retro-coop-staging wait --for=condition=Ready pod \
  -l app=retro-coop-staging --timeout=10m
```

Check that the Service's assigned address equals `STAGING_IP`. A failed wait requires teardown.
3. With Certbot 5.4 or later, set `ACME_EMAIL` to an address the operator controls and issue one staging test certificate, then one production certificate. The hooks run through `sh` because the checked-in hook is not executable:

```sh
export RETRO_STAGING_PUBLIC_IP="$STAGING_IP"
for authority in acme-test acme-live; do
  test "$authority" = acme-test && stage_flag=--staging || stage_flag=
  certbot certonly --manual --preferred-challenges http \
    --preferred-profile shortlived --ip-address "$STAGING_IP" \
    --cert-name retro-coop-staging --agree-tos --email "$ACME_EMAIL" \
    --manual-auth-hook "sh $PWD/scripts/staging/acme_hook.sh auth" \
    --manual-cleanup-hook "sh $PWD/scripts/staging/acme_hook.sh cleanup" \
    --config-dir "$PRIVATE_DIR/$authority/config" \
    --work-dir "$PRIVATE_DIR/$authority/work" \
    --logs-dir "$PRIVATE_DIR/$authority/logs" $stage_flag
done
```

Certbot supplies `CERTBOT_IDENTIFIER`, `CERTBOT_TOKEN` and `CERTBOT_VALIDATION`; the hook rejects a different IP. Inspect the trusted certificate's IP SAN, issuer and expiry before replacing the bootstrap Secret:

```sh
live_cert="$PRIVATE_DIR/acme-live/config/live/retro-coop-staging/fullchain.pem"
live_key="$PRIVATE_DIR/acme-live/config/live/retro-coop-staging/privkey.pem"
openssl x509 -in "$live_cert" -noout -checkip "$STAGING_IP" -issuer -dates
kubectl -n retro-coop-staging create secret tls retro-coop-staging-tls \
  --cert="$live_cert" --key="$live_key" --dry-run=client -o yaml |
  kubectl -n retro-coop-staging apply -f -
set -- $(kubectl -n retro-coop-staging get pods -l app=retro-coop-staging -o jsonpath='{.items[*].metadata.name}')
test "$#" -eq 1
STAGING_POD=$1
```

Wait until `kubectl -n retro-coop-staging exec "pod/$STAGING_POD" -c edge -- cat /run/tls/tls.crt | openssl x509 -noout -fingerprint -sha256` equals the local certificate's SHA-256 fingerprint. Then run `kubectl -n retro-coop-staging exec "pod/$STAGING_POD" -c edge -- nginx -s reload`. Do not use a certificate past its 160-hour lifetime. [Certbot documents IP identifiers and manual hook variables](https://eff-certbot.readthedocs.io/en/stable/using.html).
4. Immediately render with the two actual tester `/32` CIDRs and without `--acme-bootstrap`, apply it, and inspect the Service source ranges and ports:

```sh
python3 scripts/staging/render_k8s.py --public-ip "$STAGING_IP" \
  --edge-image "$EDGE_IMAGE" --coordinator-image "$COORDINATOR_IMAGE" \
  --allow "$TESTER_ONE" --allow "$TESTER_TWO" > "$PRIVATE_DIR/trial.yaml"
kubectl apply -f "$PRIVATE_DIR/trial.yaml"
kubectl -n retro-coop-staging get service retro-coop-staging -o yaml
curl --fail --show-error --silent "https://$STAGING_IP/healthz"
```

The Service must show only the two tester ranges and ports 80/443, and HTTPS must validate with the normal trust store. No player should see the bootstrap certificate. Schedule the test end before certificate expiry. At the end, run `sh scripts/staging/teardown.sh "$STAGING_PROJECT"`, verify the output and named resources, and record sanitized route evidence and measured cost on #28. Deleting only the namespace does not release the reserved IP, VM or registry images.

The prepared package has a six-hour Job and VM cutoff, per-address edge limits, relay quotas, a traffic shaper and a teardown command. The Service, reserved IP, registry and logs still need explicit cleanup. The modeled total is under $100 for the stated traffic scenario, but public ACME ingress and tester uploads have no enforceable absolute byte cap. The next review must verify the scripts and cost assumptions; deployment still needs the final spending and residual-risk decision.

## Integrated package evidence through `703a7ce`

The candidate Dockerfile builds an edge image and one coordinator image from the same source. The edge Nginx configuration serves the Vite bundle, terminates TLS, overwrites forwarding identity with its transport peer, and sends only WebSocket and membership-scoped ROM routes to loopback. It disables request-path and address access logs. `scripts/staging/edge_probe.mjs` exercises admission, host ROM upload and guest ROM download through the real proxy. The image job in the shared CI workflow builds and runs the exact containers within the same pull-request deadline as the browser gate.

The merged [PR #121](https://github.com/TuringTestee/retro-coop/pull/121) built exact containers and proved HTTPS delivery, forged-header rejection, a host upload lasting 6.31 seconds, room confirmation, and a byte-for-byte authorized guest download. [PR #122](https://github.com/TuringTestee/retro-coop/pull/122) proved that the rendered staging workload starts its exact images as one ready Pod in local Kubernetes. [PR #123](https://github.com/TuringTestee/retro-coop/pull/123) added the Job cutoff, HTTP-only certificate bootstrap and exact edge limits; its current-head image and browser checks passed. Local preflight passed 29 Rust and 138 Node tests, TypeScript typecheck and hygiene. This still does not prove GKE source-address preservation, TURN on Google Cloud, valid public TLS, independent networks, or actual cost. Those remain explicit gates above.

[PR #124](https://github.com/TuringTestee/retro-coop/pull/124) added isolated TURN VM preparation and full named-resource teardown. Its independent reviewer verified that qualified Artifact Registry names are deleted and failed inventory queries cannot be mistaken for absent resources. Its current-head CI passed in 3m43s. No Google Cloud command in the package has been run against the target project.

## Sources checked 2026-09-24

- [Google load balancer forwarding headers](https://docs.cloud.google.com/load-balancing/docs/https#x-forwarded-for_header)
- [GKE LoadBalancer source-IP behavior](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/service-load-balancer#effect_of_externaltrafficpolicy)
- [Autopilot host-port restrictions](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/autopilot-security)
- [GKE Autopilot prices](https://cloud.google.com/kubernetes-engine/pricing) and [load-balancer prices](https://cloud.google.com/load-balancing/pricing)
- [Google budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets) and [eligible spend-cap services](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps)
- [GKE static-IP and regional external Service parameters](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/service-load-balancer-parameters)
- [Let's Encrypt IP certificates](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability) and [Certbot instructions](https://letsencrypt.org/2026/03/11/shorter-certs-certbot)
- [GCE e2-micro prices](https://cloud.google.com/products/compute/pricing/general-purpose) and [external IP/egress prices](https://cloud.google.com/vpc/network-pricing)
- [GCE VM runtime limit and delete action](https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime) and [coturn configuration](https://github.com/coturn/coturn/blob/master/examples/etc/turnserver.conf)
