Audience: Agent

The AWS package builds one immutable website release and runs it on one Elastic Beanstalk instance behind HTTPS. Its separate TURN relay and budget alerts use named resources in account `599796577790`, region `us-east-1`. Do not run cloud setup until the reviewed cost policy and alert recipient are available.

# AWS website operations

## Files and boundaries

- `deploy/aws-eb/Dockerfile` builds the static edge and coordinator from one source revision. `scripts/aws_eb/build_release.py` pushes both to the dedicated immutable ECR repository and creates a small EB source bundle. Its `release.json` records the commit, exact image digests, every static asset hash, and the emulator WASM hash. The bundle contains no image build context, ROM, or secret value.
- `deploy/aws-eb/docker-compose.yml` is the source template. `package.py` puts exact image digests in the EB bundle. Both containers use host networking on one instance; the coordinator binds only `127.0.0.1:8787`. The ALB sends traffic to the edge at port `8080`. The instance security group accepts that port only from the ALB security group. Nginx selects the last address appended by the ALB to `X-Forwarded-For` and passes only that literal to the coordinator. EB reads the TURN signing key from Secrets Manager as an environment secret; the relay reads the same secret through its scoped instance role. Neither container publishes a secret to the browser.
- `deploy/aws-eb/foundation.yaml` owns the new ACM certificate, scoped security groups and instance roles, ECR repository, managed TURN secret, `t3.micro` relay, Elastic IP, SSM access, and a six-hour Lambda cost guard scheduled by EventBridge. It does not touch unrelated VPCs or GCP resources. `website.py` creates the EB environment and the exact website DNS alias only after the guard's dry run and alert subscriptions pass. Account-wide budget notices include unrelated account spending; they are conservative and do not enforce a hard charge cap.

## Local and CI proof before cloud work

Run `sh scripts/preflight.sh`, `python3 scripts/aws_eb/source_smoke.py`, `python3 scripts/aws_eb/website_smoke.py`, `python3 scripts/aws_eb/cost_guard_smoke.py`, and `python3 scripts/aws_eb/turn_smoke.py`. A Linux host with Docker can build both Docker targets and run `sh scripts/aws_eb/container_smoke.sh`; CI does this from the PR head. The Compose probe covers edge and coordinator health, immutable assets, Origin rejection, forged forwarding headers, distinct IPv4/IPv6 admission, WebSocket room creation, authorized host upload and guest download, and denied transfer attempts. The guard probe checks below/above threshold, dry-run, wrong-resource, missing-forecast and idempotent shutdown cases. `aws cloudformation validate-template --template-body file://deploy/aws-eb/foundation.yaml --region us-east-1` validates the infrastructure syntax without creating resources.

## Provision and deploy after reviewed main and cost gate

Run from a clean `main` equal to `origin/main`. Prepare a private JSON cost record with `reviewedPlanRevision` (40-character merged plan commit), `projected31DayUsd` (strictly below 100), `warningUsd: 50`, and `shutdownProjectedUsd: 100`. The estimate must include EC2, ALB, EBS, IPv4, ECR/S3, logs, DNS, scheduled guard and egress. Supply the real billing recipient through `--alert-email`; do not commit the address or cost record. `website.py setup` checks the account, public `1001.page` zone, VPC, public relay subnet, official Canonical Ubuntu AMI, and absence of the named site before creating resources. It establishes account-wide $50 actual, $100 actual and $100 forecast Budget emails before the foundation stack. The scheduled guard checks that Budget every six hours and removes only this site's exact DNS alias and named EB/relay resources if actual or forecast monthly spend reaches $100. Failed guard runs alert the operator by SNS; confirm that subscription before publication. The operator also checks daily and can run teardown as a fallback. Reporting lag and traffic charges mean this is not a hard dollar cap.

```sh
python3 scripts/aws_eb/website.py setup \
  --vpc-id VPC_ID --relay-subnet-id PUBLIC_SUBNET_ID --relay-ami-id OFFICIAL_UBUNTU_AMI_ID \
  --hosted-zone-id PUBLIC_1001_PAGE_ZONE_ID --alert-email BILLING_EMAIL \
  --reviewed-cost-record PRIVATE_COST_JSON
python3 scripts/aws_eb/build_release.py --output /tmp/retro-coop-release.zip
python3 scripts/aws_eb/website.py deploy \
  --vpc-id VPC_ID --subnets PUBLIC_SUBNET_A,PUBLIC_SUBNET_B \
  --service-role EXISTING_EB_SERVICE_ROLE --solution-stack '64bit Amazon Linux 2023 v4.13.9 running Docker' \
  --hosted-zone-id PUBLIC_1001_PAGE_ZONE_ID --bundle /tmp/retro-coop-release.zip
```

The deploy command waits for one healthy internet-facing ALB, verifies the attached groups, HTTP redirect, certificate, target port, ALB forwarding mode and instance loopback listeners, then records the ALB DNS name for the guard. It confirms the named Budget thresholds/recipient, enabled six-hour schedule, confirmed failure-alert email, alarm and a non-destructive Lambda dry run before creating the exact `retro-coop.1001.page` alias. If any check fails, it leaves the site without public DNS for repair. After publication, check its public certificate, HTTP-to-HTTPS redirect, `/healthz`, WebSocket upgrade, ROM transfer and two-network direct/forced-relay gameplay before recording acceptance. EB's own Nginx proxy is disabled for Compose. The AWS documentation for [Docker Compose](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/create_deploy_docker.container.console.html), [ALB processes](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/environments-cfg-alb.html), [environment secrets](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/AWSHowTo.secrets.env-vars.html), and [ALB HTTP redirects](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/configuring-https-httpredirect.html) supplies these platform settings.

## Recovery and removal

Keep the previous `main-<12 hex>` application version. After a bad release, run `python3 scripts/aws_eb/website.py rollback --version main-PREVIOUSREV`; expect ephemeral rooms to end and verify that players can recreate or rejoin a room. Run `python3 scripts/aws_eb/website.py teardown --hosted-zone-id PUBLIC_1001_PAGE_ZONE_ID --confirm retro-coop.1001.page` when rollback fails, the guard or operator sees projected spend at the threshold, abuse requires shutdown, or the user asks to remove the site. It removes the exact alias, EB environment/application, foundation stack (including relay, schedule, Lambda, alarm, SNS topic, roles and logs), named S3 object prefixes and budget. A partial setup without a complete stack may require `--bucket` with the exact EB storage bucket; a stranded alias without a live environment requires `--expected-alb-dns` and rejects a mismatched target. Verify stack deletion and absence of the named DNS record, ALB, relay/EIP, secret and ECR repository. An AWS secret may remain scheduled for deletion during its recovery window; no active role should be able to read it after stack removal.

The cloud workflow remains untested until the reviewed cost decision is merged and the site is provisioned. A local Compose probe is evidence for source shape; only the public two-network gate proves the deployed player journey.
