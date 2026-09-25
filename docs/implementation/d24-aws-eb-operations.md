Audience: Agent

Retro Coop's AWS website uses one Elastic Beanstalk `t4g.micro` instance for the browser, coordinator and TURN relay. The source package keeps the coordinator on loopback, serves public HTTPS through Caddy, and stops the named site when the account-wide monthly Budget reaches its $100 actual or forecast trigger.

# AWS website operations

## Source and boundary

`deploy/aws-eb/Dockerfile` has four `linux/arm64` targets: Caddy, Nginx edge, Node coordinator and coturn. `docker-compose.yml` runs all four on the EB **SingleInstance** host network. Caddy owns public TCP 80/443, Nginx binds `127.0.0.1:8080`, the coordinator binds `127.0.0.1:8787`, and coturn uses UDP 3478 and 49160–49175. Caddy replaces all caller-supplied forwarding data with the actual TCP peer before proxying to Nginx; Nginx passes that address to the coordinator. The only public security-group rules are those web and TURN ports. EB supplies one EC2 instance and its managed Elastic IP; no ALB, second VM or public SSH listener is created. [AWS documents the SingleInstance shape](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/using-features-managing-env-types.html).

EB reads the TURN signing key from Secrets Manager into the two services that need it. Coturn's startup script reads its current public Elastic IP and private IP through IMDSv2 and renders bounded allocation settings without logging the key. Caddy obtains a publicly trusted ACME certificate after the exact A record reaches that IP and stores renewal state in a named volume across ordinary app deployments. An instance replacement loses local rooms, ROMs and certificate state; the operator reconciles its new IP and verifies certificate reissuance. [Caddy's automatic HTTPS behavior](https://caddyserver.com/docs/automatic-https) requires DNS and ports 80/443 to reach the instance.

`foundation.yaml` owns only the dedicated ECR repository, secret, app security group and role, named SSM IP parameter, Lambda, six-hour Scheduler group, and failure alerts. It does not create an EC2 instance. `website.py` creates the EB environment, then tests its one-instance/EIP boundary, 20-room small-ROM memory load, Budget and alert wiring, and non-destructive guard invocation before publishing DNS. Lambda handler failures and Scheduler delivery/drop failures alert the confirmed operator email. The account-wide Budget can include unrelated account spend; forecast and billing reporting have delay, so the shutdown is not a hard billing cap.

AWS Budgets can omit `ThresholdType` when reading back a percentage notification, even when creation supplied `PERCENTAGE`. The guard treats an omitted type as percentage and still rejects an explicit `ABSOLUTE_VALUE`; it checks the exact three notification thresholds and their email subscribers before DNS.

The first live environment returned Yellow from enhanced EB health with an “Unable to assume role” warning even when its instance was healthy. The existing service role, its full ARN, AWS's monitoring service-linked role, and a temporary dedicated role all produced the same warning. Basic EB health returned Green with the existing service role, so new environments select Basic health explicitly. The deployment still requires Green and separately checks the exact instance, public ingress, web/coordinator/TURN listeners, `/healthz`, and the 20-room memory workload before DNS. The temporary test role was removed.

## Local and CI proof

From the reviewed source run `sh scripts/preflight.sh`, `python3 scripts/aws_eb/source_smoke.py`, `python3 scripts/aws_eb/website_smoke.py`, `python3 scripts/aws_eb/cost_guard_smoke.py`, `python3 scripts/aws_eb/turn_smoke.py`, and read-only `aws cloudformation validate-template --template-body file://deploy/aws-eb/foundation.yaml --region us-east-1`. PR CI builds all four images on a native `ubuntu-24.04-arm` runner and runs the Compose probe. The probe checks Caddy's forged-header boundary, WebSocket and ROM transfer, Origin denial, room load and a coturn allocation. It cannot prove public ACME, UDP between independent networks or actual EC2 memory; those are live gates before broad release.

The main push workflow saves four native ARM64 Docker image tarballs plus SHA-256 checksums as the `aws-eb-arm64-images` artifact. Its final job runs only after the build and browser checks pass. It checks that the push SHA is still current main, assumes the main-scoped AWS OIDC role, verifies the same run's image checksums and `linux/arm64` digests, and makes one source bundle. `einaregilsson/beanstalk-deploy@v21` uploads that bundle and updates the existing EB environment. The final step checks the exact version, Ready/Green health and public HTTPS. A failed build or superseded main commit leaves the current website in place. The later public two-browser acceptance and rollback workflow is tracked separately in [fast main delivery](fast-main-delivery.md).

`deploy/aws-eb/github-cd-role.yaml` owns the GitHub OIDC provider and dedicated release role. Its trust accepts only this repository's main branch with audience `sts.amazonaws.com`. Supply the exact main-branch OIDC subject as the private `GitHubMainSubject` CloudFormation parameter; no account ARN or subject ID belongs in source. Store the resulting role ARN in the repository secret `AWS_DEPLOY_ROLE_ARN`. The workflow uses temporary OIDC credentials and passes their session token to the EB action; GitHub stores no AWS access key. The local commands below remain an operator recovery path.

The deployment job has a 30-minute emergency ceiling, not a target runtime. The EB action waits for the environment to become Ready/Green, then the workflow checks the public HTTPS endpoint. Normal releases target five minutes after the build gate; report actual elapsed time. The action does not roll back a failed deployment. Inspect the live version and health, and use the operator rollback path below when needed.

## Provision and publish

Run from clean `main` equal to `origin/main`. Prepare a private reviewed 31-day cost JSON with `reviewedPlanRevision` (the merged one-machine plan commit), `projected31DayUsd` below 100, `warningUsd: 50`, and `shutdownProjectedUsd: 100`. Include the one micro instance, EBS, one public IPv4, ECR/S3, logs, DNS, guard and internet egress. Supply the billing recipient as `--alert-email`; never commit the address or cost JSON. The separate SNS failure-alert subscription can be pending while the site is published; check the three CloudWatch failure alarms and the last scheduled invocation daily until the email is confirmed. Direct Budget notices and the scheduled shutdown remain configured.

Set `RETRO_AWS_ACCOUNT_ID` from the private deployment record before running the operator script. It must match the active AWS caller identity.

```sh
python3 scripts/aws_eb/website.py setup \
  --vpc-id VPC_ID --hosted-zone-id BARE_PUBLIC_ZONE_ID \
  --alert-email BILLING_EMAIL --reviewed-cost-record PRIVATE_COST_JSON
GOBIN=/tmp/retro-eb-tools go install github.com/google/go-containerregistry/cmd/crane@v0.20.6
python3 scripts/aws_eb/build_release.py \
  --crane /tmp/retro-eb-tools/crane --output /tmp/retro-coop-release.zip
python3 scripts/aws_eb/website.py deploy \
  --vpc-id VPC_ID --subnet PUBLIC_SUBNET_ID \
  --service-role EXISTING_EB_SERVICE_ROLE \
  --solution-stack '64bit Amazon Linux 2023 v4.13.9 running Docker' \
  --hosted-zone-id BARE_PUBLIC_ZONE_ID --bundle /tmp/retro-coop-release.zip
```

`setup` checks the exact AWS account, public hosted zone and its registrar/public DNS delegation, VPC, absence of the named website, and cost record before creating the named Budget and foundation. `deploy` checks the same delegation, sole ARM64 micro instance and EB-managed EIP, exact security group, loopback listeners, coturn listener, and a 20-room ROM workload with at least 128 MiB available host memory. It then confirms the existing Budget notices, the six-hour schedule's real invocation payload, SNS recipient, Lambda/Scheduler alarms, and a successful guard dry run. It creates or reconciles only `retro-coop.atobot.cloud` A to the current EIP, waits for Route 53, and checks a valid HTTPS certificate and `/healthz`. If certificate issuance fails, it removes the newly created record or restores the previous record and IP guard value. The EB environment remains for diagnosis without publishing a broken endpoint.

For the existing environment created under undelegated `1001.page`, first build a new guard ZIP from the merged `scripts/aws_eb/cost_guard.py` and upload it under a new `retro-coop/bootstrap/` key in the existing EB bucket. Update the **existing** `retro-coop-website-foundation` stack with the merged template, the current public hosted-zone ID obtained from Route 53, that new guard key, and its current VPC, bucket and alert email parameters. Wait for `UPDATE_COMPLETE`; verify the Lambda hostname is `retro-coop.atobot.cloud`, its hosted zone is the new zone, and its IAM DNS delete condition names only the new hostname. Build the immutable release from the same reviewed `main`, then run the above `deploy` command with `--update` and the new hosted zone ID. Elastic Beanstalk does not accept configuration and version changes in one request: the operator first applies and verifies the new coordinator origin/TURN URL, then deploys and verifies the image version. If the version step fails, the script restores the prior version and settings before reporting failure. After public HTTPS succeeds, delete only the stray `retro-coop.1001.page` A record from the undelegated old zone. Do not run this migration by changing DNS alone.

After public HTTPS succeeds, check redirect, assets, WebSocket, custom ROM upload/download, and two independent networks in direct and forced TURN modes. Verify matching game frames, voice/text, reconnect and leave. Recheck memory under larger ROM and relay traffic. Record the EIP, release digests, measured memory/cost and result in D24; keep broad release qualification open if the 1 GiB host cannot sustain the approved capacity. Single-instance replacement can cause downtime.

## Recovery and removal

Keep the previous `main-<12 hex>` application version. A bad release can be rolled back with `python3 scripts/aws_eb/website.py rollback --version main-PREVIOUSREV`; ephemeral rooms restart, so players recreate or rejoin. After EB replacement, rerun the reviewed `deploy --update` command using a bundle from the current clean main. It re-reads the new EIP, reconciles the exact A record, and verifies ACME, web and TURN. To shut down, run:

```sh
python3 scripts/aws_eb/website.py teardown \
  --hosted-zone-id BARE_PUBLIC_ZONE_ID --confirm retro-coop.atobot.cloud
```

Teardown removes only the exact recorded A record, named EB environment/application and its EIP, foundation (secret, ECR, guard schedule/Lambda/alarms/roles), named EB S3 object prefixes and named Budget. For partial setup cleanup use `--bucket` with the exact account's EB storage bucket; for a stranded A record without the stack use `--expected-ip` with its verified prior EIP. Verify all named resources and DNS are absent. A managed secret may remain scheduled for deletion during its recovery window. The cloud path remains unaccepted until live public and two-network checks pass.
