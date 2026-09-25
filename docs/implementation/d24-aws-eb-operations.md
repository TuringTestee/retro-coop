Audience: Agent

The AWS package builds one immutable website release and runs it on one Elastic Beanstalk instance behind HTTPS. Its separate TURN relay and budget alerts use named resources in account `599796577790`, region `us-east-1`. Do not run cloud setup until the reviewed cost policy and alert recipient are available.

# AWS website operations

## Files and boundaries

- `deploy/aws-eb/Dockerfile` builds the static edge and coordinator from one source revision. `scripts/aws_eb/build_release.py` pushes both to the dedicated immutable ECR repository and creates a small EB source bundle. Its `release.json` records the commit, exact image digests, every static asset hash, and the emulator WASM hash. The bundle contains no image build context, ROM, or secret value.
- `deploy/aws-eb/docker-compose.yml` is the source template. `package.py` puts exact image digests in the EB bundle. Both containers use host networking on one instance; the coordinator binds only `127.0.0.1:8787`. The ALB sends traffic to the edge at port `8080`. The instance security group accepts that port only from the ALB security group. Nginx selects the last address appended by the ALB to `X-Forwarded-For` and passes only that literal to the coordinator. EB reads the TURN signing key from Secrets Manager as an environment secret; the relay reads the same secret through its scoped instance role. Neither container publishes a secret to the browser.
- `deploy/aws-eb/foundation.yaml` owns the new ACM certificate, scoped security groups and instance roles, ECR repository, managed TURN secret, `t3.micro` relay, Elastic IP and SSM access. It does not touch unrelated VPCs or GCP resources. `website.py` creates the EB environment and the exact website DNS alias. Account-wide budget notices include unrelated account spending; they are conservative and do not enforce a hard charge cap.

## Local and CI proof before cloud work

Run `sh scripts/preflight.sh`, `python3 scripts/aws_eb/source_smoke.py`, and `python3 scripts/aws_eb/turn_smoke.py`. A Linux host with Docker can build both Docker targets and run `sh scripts/aws_eb/container_smoke.sh`; CI does this from the PR head. The Compose probe covers edge and coordinator health, immutable assets, Origin rejection, forged forwarding headers, distinct IPv4/IPv6 admission, WebSocket room creation, authorized host upload and guest download, and denied transfer attempts. `aws cloudformation validate-template --template-body file://deploy/aws-eb/foundation.yaml --region us-east-1` validates the infrastructure syntax without creating resources.

## Provision and deploy after reviewed main and cost gate

Run from a clean `main` equal to `origin/main`. Prepare a private JSON cost record with `reviewedPlanRevision` (40-character merged plan commit), `projected31DayUsd` (strictly below 100), `warningUsd: 50`, and `shutdownProjectedUsd: 100`. The estimate must include EC2, ALB, EBS, IPv4, ECR/S3, logs, DNS and egress. Supply the real billing recipient through `--alert-email`; do not commit the address or cost record. `website.py setup` checks the account, public `1001.page` zone, VPC, public relay subnet, official Canonical Ubuntu AMI, and absence of the named site before creating resources. It establishes account-wide $50 actual, $100 actual and $100 forecast Budget emails before the foundation stack. A budget notice needs an operator to run the shutdown command; treat it as an alert, not a hard cap.

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

The deploy command waits for one healthy internet-facing ALB, then creates the exact `retro-coop.1001.page` alias. Check its public certificate, HTTP-to-HTTPS redirect, `/healthz`, WebSocket upgrade, ROM transfer and two-network direct/forced-relay gameplay before recording acceptance. EB's own Nginx proxy is disabled for Compose. The AWS documentation for [Docker Compose](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/create_deploy_docker.container.console.html), [ALB processes](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/environments-cfg-alb.html), [environment secrets](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/AWSHowTo.secrets.env-vars.html), and [ALB HTTP redirects](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/configuring-https-httpredirect.html) supplies these platform settings.

## Recovery and removal

Keep the previous `main-<12 hex>` application version. After a bad release, run `python3 scripts/aws_eb/website.py rollback --version main-PREVIOUSREV`; expect ephemeral rooms to end and verify that players can recreate or rejoin a room. Run `python3 scripts/aws_eb/website.py teardown --hosted-zone-id PUBLIC_1001_PAGE_ZONE_ID --confirm retro-coop.1001.page` when rollback fails, projected spend reaches the operating threshold, abuse requires shutdown, or the user asks to remove the site. It removes the exact alias, EB environment/application, foundation stack, named S3 object prefixes and budget. Verify stack deletion and absence of the named DNS record, ALB, relay/EIP, secret and ECR repository. An AWS secret may remain scheduled for deletion during its recovery window; no active role should be able to read it after stack removal.

The cloud workflow remains untested until the reviewed cost decision is merged and the site is provisioned. A local Compose probe is evidence for source shape; only the public two-network gate proves the deployed player journey.
