#!/usr/bin/env python3
"""Provision, deploy, roll back or remove only the named Retro Coop AWS website."""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

from package import ROOT, IMAGE


ACCOUNT = "599796577790"
REGION = "us-east-1"
HOST = "retro-coop.1001.page"
APP = "retro-coop"
ENV = "retro-coop-web"
STACK = "retro-coop-website-foundation"
BUDGET = "retro-coop-website-monthly"
BOOTSTRAP_PREFIX = "retro-coop/bootstrap"
RELEASE_PREFIX = "retro-coop/releases"


def aws(*args: str) -> dict:
    result = subprocess.run(["aws", *args, "--region", REGION, "--output", "json"], check=True, capture_output=True, text=True)
    return json.loads(result.stdout or "{}")


def command(*args: str) -> None:
    subprocess.run(["aws", *args, "--region", REGION], check=True, stdout=subprocess.DEVNULL)


def identity() -> None:
    if aws("sts", "get-caller-identity").get("Account") != ACCOUNT:
        raise ValueError("AWS account does not match the reviewed website account")


def reviewed_main() -> None:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    if git("branch", "--show-current") != "main" or git("status", "--porcelain"):
        raise ValueError("Provision only from a clean reviewed main checkout")
    if git("rev-parse", "HEAD") != git("rev-parse", "origin/main"):
        raise ValueError("Main differs from origin/main")


def stack_outputs() -> dict[str, str]:
    rows = aws("cloudformation", "describe-stacks", "--stack-name", STACK)["Stacks"]
    if len(rows) != 1 or rows[0]["StackStatus"] not in ("CREATE_COMPLETE", "UPDATE_COMPLETE"):
        raise ValueError("The Retro Coop foundation stack is not ready")
    return {row["OutputKey"]: row["OutputValue"] for row in rows[0]["Outputs"]}


def stack_status() -> str | None:
    rows = aws("cloudformation", "list-stacks")["StackSummaries"]
    active = [row["StackStatus"] for row in rows if row["StackName"] == STACK and row["StackStatus"] != "DELETE_COMPLETE"]
    if len(active) > 1:
        raise ValueError("More than one active foundation stack has the reviewed name")
    return active[0] if active else None


def stack_parameters() -> dict[str, str]:
    stack = aws("cloudformation", "describe-stacks", "--stack-name", STACK)["Stacks"][0]
    return {row["ParameterKey"]: row["ParameterValue"] for row in stack["Parameters"]}


def environment() -> dict | None:
    rows = aws("elasticbeanstalk", "describe-environments", "--application-name", APP,
               "--environment-names", ENV).get("Environments", [])
    return rows[0] if rows else None


def dns_record(zone: str) -> dict | None:
    rows = aws("route53", "list-resource-record-sets", "--hosted-zone-id", zone,
               "--start-record-name", HOST, "--start-record-type", "A", "--max-items", "1")["ResourceRecordSets"]
    return rows[0] if rows and rows[0]["Name"].rstrip(".") == HOST and rows[0]["Type"] == "A" else None


def public_subnet(subnet_id: str, vpc_id: str) -> bool:
    subnet = aws("ec2", "describe-subnets", "--subnet-ids", subnet_id)["Subnets"][0]
    if subnet["VpcId"] != vpc_id:
        return False
    tables = aws("ec2", "describe-route-tables", "--filters", f"Name=vpc-id,Values={vpc_id}")["RouteTables"]
    explicit = [table for table in tables if any(association.get("SubnetId") == subnet_id for association in table["Associations"])]
    selected = explicit or [table for table in tables if any(association.get("Main") for association in table["Associations"])]
    return len(selected) == 1 and any(route.get("DestinationCidrBlock") == "0.0.0.0/0" and
                                      route.get("GatewayId", "").startswith("igw-") and route.get("State") == "active"
                                      for route in selected[0]["Routes"])


def change_dns(zone: str, action: str, record: dict) -> None:
    payload = {"Changes": [{"Action": action, "ResourceRecordSet": record}]}
    command("route53", "change-resource-record-sets", "--hosted-zone-id", zone,
            "--change-batch", json.dumps(payload, separators=(",", ":")))


def wait_for_environment(desired: str, timeout: int = 1800) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = environment()
        if desired == "Terminated" and not current:
            return {}
        if current and current.get("Status") == desired:
            if desired != "Ready" or current.get("Health") == "Green":
                return current
        if current and current.get("Status") in ("Terminated", "Terminating") and desired != "Terminated":
            raise RuntimeError("Elastic Beanstalk environment terminated during deployment")
        time.sleep(15)
    raise TimeoutError(f"Elastic Beanstalk environment did not become {desired}")


def budget(alert_email: str) -> None:
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", alert_email):
        raise ValueError("Supply an email address for AWS Budget alerts")
    definition = {"BudgetName": BUDGET, "BudgetLimit": {"Amount": "100", "Unit": "USD"},
                  "TimeUnit": "MONTHLY", "BudgetType": "COST"}
    subscriber = [{"SubscriptionType": "EMAIL", "Address": alert_email}]
    notices = [{"Notification": {"NotificationType": mode, "ComparisonOperator": "GREATER_THAN",
                                 "Threshold": amount, "ThresholdType": "PERCENTAGE"}, "Subscribers": subscriber}
               for mode, amount in (("ACTUAL", 50), ("ACTUAL", 100), ("FORECASTED", 100))]
    command("budgets", "create-budget", "--account-id", ACCOUNT, "--budget", json.dumps(definition),
            "--notifications-with-subscribers", json.dumps(notices))


def setup(args: argparse.Namespace) -> None:
    reviewed_main()
    identity()
    if args.reviewed_cost_record is None or not args.reviewed_cost_record.is_file():
        raise ValueError("Supply the reviewed 31-day cost record before provisioning")
    cost = json.loads(args.reviewed_cost_record.read_text())
    if cost.get("warningUsd") != 50 or cost.get("shutdownProjectedUsd") != 100 or not re.fullmatch(r"[a-f0-9]{40}", str(cost.get("reviewedPlanRevision", ""))):
        raise ValueError("Cost record must name the reviewed plan and $50/$100 operating thresholds")
    projected = cost.get("projected31DayUsd")
    if isinstance(projected, bool) or not isinstance(projected, (int, float)) or not 0 < projected < 100:
        raise ValueError("The 31-day cost scenario exceeds the reviewed $100 operating ceiling")
    if dns_record(args.hosted_zone_id):
        raise ValueError("Website DNS name already exists; inspect it before provisioning")
    if stack_status():
        raise ValueError("The named foundation stack already exists; inspect or tear it down before setup")
    if environment():
        raise ValueError("The named EB environment already exists")
    if aws("elasticbeanstalk", "describe-applications", "--application-names", APP)["Applications"]:
        raise ValueError("The named EB application already exists; inspect it before provisioning")
    hosted = aws("route53", "get-hosted-zone", "--id", args.hosted_zone_id)["HostedZone"]
    if hosted["Name"].rstrip(".") != "1001.page" or hosted["Config"].get("PrivateZone"):
        raise ValueError("Expected the public 1001.page hosted zone")
    vpc = aws("ec2", "describe-vpcs", "--vpc-ids", args.vpc_id)["Vpcs"][0]
    image = aws("ec2", "describe-images", "--image-ids", args.relay_ami_id)["Images"][0]
    if not public_subnet(args.relay_subnet_id, vpc["VpcId"]):
        raise ValueError("Relay subnet must be public and in the selected VPC")
    if image["OwnerId"] != "099720109477" or "ubuntu" not in image["Name"].lower():
        raise ValueError("Relay AMI must be an official Canonical Ubuntu image")
    bucket = aws("elasticbeanstalk", "create-storage-location")["S3Bucket"]
    for name in ("render_turn.py", "configure_turn.sh"):
        command("s3", "cp", str(ROOT / "scripts/aws_eb" / name), f"s3://{bucket}/{BOOTSTRAP_PREFIX}/{name}")
    guard_key = f"{BOOTSTRAP_PREFIX}/cost-guard-{subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()}.zip"
    with tempfile.TemporaryDirectory(prefix="retro-eb-guard-") as directory:
        package = Path(directory) / "cost-guard.zip"
        with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(ROOT / "scripts/aws_eb/cost_guard.py", "cost_guard.py")
        command("s3", "cp", str(package), f"s3://{bucket}/{guard_key}")
    budget(args.alert_email)
    command("cloudformation", "deploy", "--template-file", str(ROOT / "deploy/aws-eb/foundation.yaml"),
            "--stack-name", STACK, "--capabilities", "CAPABILITY_NAMED_IAM", "--parameter-overrides",
            f"VpcId={args.vpc_id}", f"RelaySubnetId={args.relay_subnet_id}", f"RelayAmiId={args.relay_ami_id}",
            f"HostedZoneId={args.hosted_zone_id}", f"BootstrapBucket={bucket}", f"BootstrapPrefix={BOOTSTRAP_PREFIX}",
            f"GuardCodeKey={guard_key}", f"AlertEmail={args.alert_email}")
    outputs = stack_outputs()
    print(json.dumps({"foundation": STACK, "relayPublicIp": outputs["RelayPublicIp"],
                      "certificateArn": outputs["CertificateArn"], "ecrRepository": outputs["EcrRepository"],
                      "bucket": bucket}))


def setting(namespace: str, name: str, value: str) -> dict:
    return {"Namespace": namespace, "OptionName": name, "Value": value}


def options(outputs: dict[str, str], args: argparse.Namespace) -> list[dict]:
    environment_ns = "aws:elasticbeanstalk:environment"
    launch = "aws:autoscaling:launchconfiguration"
    return [
        setting(environment_ns, "EnvironmentType", "LoadBalanced"),
        setting(environment_ns, "LoadBalancerType", "application"),
        setting(environment_ns, "ServiceRole", args.service_role),
        setting("aws:autoscaling:asg", "MinSize", "1"),
        setting("aws:autoscaling:asg", "MaxSize", "1"),
        setting(launch, "IamInstanceProfile", outputs["EbProfileName"]),
        setting(launch, "InstanceType", "t3.small"),
        setting(launch, "RootVolumeType", "gp3"),
        setting(launch, "RootVolumeSize", "28"),
        setting(launch, "DisableDefaultEC2SecurityGroup", "true"),
        setting(launch, "SecurityGroups", outputs["AppSecurityGroupId"]),
        setting("aws:elbv2:loadbalancer", "SecurityGroups", outputs["AlbSecurityGroupId"]),
        setting("aws:elbv2:listener:443", "ListenerEnabled", "true"),
        setting("aws:elbv2:listener:443", "Protocol", "HTTPS"),
        setting("aws:elbv2:listener:443", "SSLCertificateArns", outputs["CertificateArn"]),
        setting("aws:elbv2:listener:443", "DefaultProcess", "default"),
        setting("aws:ec2:vpc", "VPCId", args.vpc_id),
        setting("aws:ec2:vpc", "Subnets", args.subnets),
        setting("aws:ec2:vpc", "ELBSubnets", args.subnets),
        setting("aws:ec2:vpc", "AssociatePublicIpAddress", "true"),
        setting("aws:elasticbeanstalk:application:environment", "COORDINATOR_ORIGINS", f"https://{HOST}"),
        setting("aws:elasticbeanstalk:application:environment", "TURN_URLS", f"turn:{outputs['RelayPublicIp']}:3478?transport=udp"),
        setting("aws:elasticbeanstalk:application:environmentsecrets", "TURN_SECRET", outputs["TurnSecretArn"]),
    ]


def verify_live_boundary(outputs: dict[str, str], resources: dict, alb: dict) -> None:
    instances = resources["Instances"]
    if len(instances) != 1:
        raise ValueError("Expected exactly one EB app instance")
    instance_id = instances[0]["Id"]
    instance = aws("ec2", "describe-instances", "--instance-ids", instance_id)["Reservations"][0]["Instances"][0]
    attached = {group["GroupId"] for group in instance["SecurityGroups"]}
    if attached != {outputs["AppSecurityGroupId"]} or set(alb["SecurityGroups"]) != {outputs["AlbSecurityGroupId"]}:
        raise ValueError("EB attached an unexpected security group")
    if instance["InstanceType"] != "t3.small":
        raise ValueError("EB did not launch the reviewed t3.small app instance")
    groups = aws("ec2", "describe-security-groups", "--group-ids", outputs["AppSecurityGroupId"])["SecurityGroups"]
    inbound = groups[0]["IpPermissions"]
    if len(inbound) != 1 or inbound[0].get("FromPort") != 8080 or inbound[0].get("ToPort") != 8080 or \
            {pair["GroupId"] for pair in inbound[0].get("UserIdGroupPairs", [])} != {outputs["AlbSecurityGroupId"]} or \
            inbound[0].get("IpRanges") or inbound[0].get("Ipv6Ranges"):
        raise ValueError("The app instance is reachable outside the ALB or on an unexpected port")
    listeners = aws("elbv2", "describe-listeners", "--load-balancer-arn", alb["LoadBalancerArn"])["Listeners"]
    by_port = {row["Port"]: row for row in listeners}
    if set(by_port) != {80, 443} or by_port[80]["Protocol"] != "HTTP" or \
            by_port[80]["DefaultActions"][0]["Type"] != "redirect" or \
            by_port[80]["DefaultActions"][0]["RedirectConfig"]["Port"] != "443" or \
            by_port[443]["Protocol"] != "HTTPS" or \
            outputs["CertificateArn"] not in {item["CertificateArn"] for item in by_port[443].get("Certificates", [])}:
        raise ValueError("ALB listeners lack the reviewed HTTPS certificate or HTTP redirect")
    attributes = {row["Key"]: row["Value"] for row in aws("elbv2", "describe-load-balancer-attributes",
                   "--load-balancer-arn", alb["LoadBalancerArn"])["Attributes"]}
    if attributes.get("routing.http.xff_header_processing.mode") != "append":
        raise ValueError("ALB must append the transport peer to X-Forwarded-For")
    targets = aws("elbv2", "describe-target-groups", "--load-balancer-arn", alb["LoadBalancerArn"])["TargetGroups"]
    if not any(row["Port"] == 8080 and row["Protocol"] == "HTTP" and row["HealthCheckPath"] == "/healthz" for row in targets):
        raise ValueError("ALB target group does not probe the edge and coordinator on port 8080")
    command_id = aws("ssm", "send-command", "--instance-ids", instance_id, "--document-name", "AWS-RunShellScript",
                     "--parameters", json.dumps({"commands": ["ss -H -ltn", "curl -fsS http://127.0.0.1:8787/health", "curl -fsS http://127.0.0.1:8080/healthz"]}))[
                         "Command"]["CommandId"]
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        result = aws("ssm", "get-command-invocation", "--command-id", command_id, "--instance-id", instance_id)
        if result["Status"] == "Success":
            output = result["StandardOutputContent"]
            listeners = [line for line in output.splitlines() if ":8787" in line]
            if len(listeners) != 1 or "127.0.0.1:8787" not in listeners[0] or "0.0.0.0:8080" not in output or \
                    output.count("retro-coop-coordinator") < 2:
                raise ValueError("The instance did not keep the coordinator on loopback behind the edge")
            return
        if result["Status"] in ("Failed", "Cancelled", "TimedOut"):
            raise ValueError("SSM could not confirm the EB loopback boundary")
        time.sleep(5)
    raise TimeoutError("SSM instance boundary check did not finish")


def verify_guard(outputs: dict[str, str], alb_dns: str) -> dict:
    email = stack_parameters()["AlertEmail"]
    monitored = aws("budgets", "describe-budget", "--account-id", ACCOUNT, "--budget-name", BUDGET)["Budget"]
    limit = monitored.get("BudgetLimit", {})
    try:
        valid_limit = limit.get("Unit") == "USD" and Decimal(str(limit.get("Amount"))) == 100
    except InvalidOperation:
        valid_limit = False
    if monitored.get("BudgetType") != "COST" or monitored.get("TimeUnit") != "MONTHLY" or \
            monitored.get("CostFilters") or not valid_limit:
        raise ValueError("The named account-wide monthly $100 Budget is missing or changed")
    notifications = aws("budgets", "describe-notifications-for-budget", "--account-id", ACCOUNT,
                        "--budget-name", BUDGET)["Notifications"]
    present = {(row["NotificationType"], float(row["Threshold"])) for row in notifications
               if row.get("ComparisonOperator") == "GREATER_THAN" and row.get("ThresholdType") == "PERCENTAGE"}
    if not {("ACTUAL", 50.0), ("ACTUAL", 100.0), ("FORECASTED", 100.0)}.issubset(present):
        raise ValueError("The $50/$100 actual and forecast Budget alerts are incomplete")
    for row in notifications:
        if (row.get("NotificationType"), float(row.get("Threshold", -1))) not in {("ACTUAL", 50.0), ("ACTUAL", 100.0), ("FORECASTED", 100.0)}:
            continue
        notice = {key: row[key] for key in ("NotificationType", "ComparisonOperator", "Threshold", "ThresholdType")}
        subscribers = aws("budgets", "describe-subscribers-for-notification", "--account-id", ACCOUNT,
                          "--budget-name", BUDGET, "--notification", json.dumps(notice))["Subscribers"]
        if {"SubscriptionType": "EMAIL", "Address": email} not in subscribers:
            raise ValueError("The Budget alert recipient differs from the reviewed operator input")
    schedule = aws("scheduler", "get-schedule", "--name", outputs["GuardScheduleName"])
    if schedule.get("State") != "ENABLED" or schedule.get("ScheduleExpression") != "rate(6 hours)" or \
            schedule.get("Target", {}).get("Arn") != outputs["GuardFunctionArn"]:
        raise ValueError("The six-hour cost guard schedule is not enabled")
    subscribers = aws("sns", "list-subscriptions-by-topic", "--topic-arn", outputs["GuardAlertTopicArn"])["Subscriptions"]
    if not any(row.get("Endpoint") == email and row.get("Protocol") == "email" and
               row.get("SubscriptionArn", "PendingConfirmation") != "PendingConfirmation" for row in subscribers):
        raise ValueError("Confirm the cost guard failure alert email subscription before public DNS")
    alarm = aws("cloudwatch", "describe-alarms", "--alarm-names", "retro-coop-cost-guard-errors")["MetricAlarms"]
    if len(alarm) != 1 or not alarm[0].get("ActionsEnabled") or outputs["GuardAlertTopicArn"] not in alarm[0]["AlarmActions"]:
        raise ValueError("Cost guard failures have no active operator alarm")
    parameter = outputs["ExpectedAlbParameterName"]
    previous = aws("ssm", "get-parameter", "--name", parameter)["Parameter"]["Value"]
    if previous not in ("UNCONFIGURED", alb_dns):
        raise ValueError("Recorded website ALB differs from this EB environment")
    if previous != alb_dns:
        command("ssm", "put-parameter", "--name", parameter, "--type", "String", "--value", alb_dns, "--overwrite")
    if aws("ssm", "get-parameter", "--name", parameter)["Parameter"]["Value"] != alb_dns:
        raise ValueError("Cost guard did not record the exact website ALB")
    with tempfile.TemporaryDirectory(prefix="retro-eb-guard-probe-") as directory:
        path = Path(directory) / "result.json"
        metadata = aws("lambda", "invoke", "--function-name", outputs["GuardFunctionArn"],
                       "--payload", '{"dryRun":true}', "--cli-binary-format", "raw-in-base64-out", str(path))
        if metadata.get("StatusCode") != 200 or metadata.get("FunctionError"):
            raise ValueError("Cost guard dry run failed; inspect its content-free CloudWatch error log")
        result = json.loads(path.read_text())
    if result.get("dryRun") is not True or result.get("wouldStop") is not False or result.get("actions") != []:
        raise ValueError("Cost guard dry run did not confirm operation below the shutdown threshold")
    return result


def release_record(bundle: Path) -> dict:
    with zipfile.ZipFile(bundle) as archive:
        if set(archive.namelist()) != {"docker-compose.yml", "release.json", ".ebextensions/01-environment.config", ".ebextensions/02-http-redirect.config"}:
            raise ValueError("Unexpected source bundle contents")
        record = json.loads(archive.read("release.json"))
        compose = archive.read("docker-compose.yml").decode()
    if not IMAGE.fullmatch(record.get("edgeImage", "")) or not IMAGE.fullmatch(record.get("coordinatorImage", "")):
        raise ValueError("Release images are not pinned to the reviewed ECR repository")
    if record["edgeImage"] not in compose or record["coordinatorImage"] not in compose:
        raise ValueError("Bundle and release record disagree on image digests")
    return record


def deploy(args: argparse.Namespace) -> None:
    reviewed_main()
    identity()
    outputs = stack_outputs()
    record = release_record(args.bundle)
    if record["sourceRevision"] != subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip():
        raise ValueError("Release bundle was not built from the checked-out reviewed main")
    if args.vpc_id != aws("ec2", "describe-security-groups", "--group-ids", outputs["AppSecurityGroupId"])["SecurityGroups"][0]["VpcId"]:
        raise ValueError("EB VPC differs from the scoped security groups")
    subnets = args.subnets.split(",")
    rows = aws("ec2", "describe-subnets", "--subnet-ids", *subnets)["Subnets"]
    if len(set(subnets)) < 2 or len({row["AvailabilityZone"] for row in rows}) < 2 or any(not public_subnet(row["SubnetId"], args.vpc_id) for row in rows):
        raise ValueError("An ALB needs two subnets in different zones of the selected VPC")
    if environment() and not args.update:
        raise ValueError("The EB environment exists; pass --update for a reviewed release")
    bucket = aws("elasticbeanstalk", "create-storage-location")["S3Bucket"]
    revision = record["sourceRevision"]
    version = f"main-{revision[:12]}"
    key = f"{RELEASE_PREFIX}/{version}.zip"
    command("s3", "cp", str(args.bundle), f"s3://{bucket}/{key}")
    applications = aws("elasticbeanstalk", "describe-applications", "--application-names", APP)["Applications"]
    if not applications:
        command("elasticbeanstalk", "create-application", "--application-name", APP)
    versions = aws("elasticbeanstalk", "describe-application-versions", "--application-name", APP,
                   "--version-labels", version)["ApplicationVersions"]
    if versions:
        if versions[0]["SourceBundle"] != {"S3Bucket": bucket, "S3Key": key}:
            raise ValueError("Version label already references a different bundle")
    else:
        command("elasticbeanstalk", "create-application-version", "--application-name", APP,
                "--version-label", version, "--source-bundle", f"S3Bucket={bucket},S3Key={key}")
    if args.update:
        command("elasticbeanstalk", "update-environment", "--environment-name", ENV, "--version-label", version)
    else:
        command("elasticbeanstalk", "create-environment", "--application-name", APP,
                "--environment-name", ENV, "--version-label", version,
                "--solution-stack-name", args.solution_stack, "--option-settings", json.dumps(options(outputs, args)))
    current = wait_for_environment("Ready")
    resources = aws("elasticbeanstalk", "describe-environment-resources", "--environment-name", ENV)["EnvironmentResources"]
    load_balancers = resources["LoadBalancers"]
    if len(load_balancers) != 1:
        raise ValueError("Expected exactly one EB load balancer")
    alb = aws("elbv2", "describe-load-balancers", "--names", load_balancers[0]["Name"])["LoadBalancers"][0]
    if alb["Type"] != "application" or alb["Scheme"] != "internet-facing":
        raise ValueError("EB did not create an internet-facing ALB")
    verify_live_boundary(outputs, resources, alb)
    guard = verify_guard(outputs, alb["DNSName"])
    record_set = {"Name": HOST + ".", "Type": "A", "AliasTarget": {
        "HostedZoneId": alb["CanonicalHostedZoneId"], "DNSName": alb["DNSName"], "EvaluateTargetHealth": True}}
    existing = dns_record(args.hosted_zone_id)
    if existing and existing != record_set:
        raise ValueError("Website DNS already points elsewhere; inspect before changing it")
    if not existing:
        change_dns(args.hosted_zone_id, "CREATE", record_set)
    print(json.dumps({"endpoint": f"https://{HOST}", "version": version, "status": current["Status"],
                      "health": current.get("Health"), "alb": alb["DNSName"], "bundle": f"s3://{bucket}/{key}",
                      "costGuard": {"schedule": outputs["GuardScheduleName"], "actualUsd": guard["actualUsd"],
                                    "forecastUsd": guard["forecastUsd"]}}))


def rollback(args: argparse.Namespace) -> None:
    identity()
    current = environment()
    if not current or current["Status"] != "Ready":
        raise ValueError("The named EB environment is not ready")
    versions = aws("elasticbeanstalk", "describe-application-versions", "--application-name", APP,
                   "--version-labels", args.version)["ApplicationVersions"]
    if len(versions) != 1 or not re.fullmatch(r"main-[a-f0-9]{12}", args.version):
        raise ValueError("Rollback target must be an existing immutable Retro Coop main version")
    if current["VersionLabel"] == args.version:
        raise ValueError("The requested version is already active")
    command("elasticbeanstalk", "update-environment", "--environment-name", ENV, "--version-label", args.version)
    finished = wait_for_environment("Ready")
    print(json.dumps({"rolledBackTo": finished["VersionLabel"], "health": finished.get("Health"),
                      "note": "Ephemeral rooms restart; players recover by creating or joining a room again."}))


def teardown(args: argparse.Namespace) -> None:
    identity()
    if args.confirm != HOST:
        raise ValueError(f"Use --confirm {HOST} to remove the named website")
    if args.bucket and args.bucket != f"elasticbeanstalk-{REGION}-{ACCOUNT}":
        raise ValueError("Deployment bucket does not match the reviewed account and region")
    current = environment()
    existing = dns_record(args.hosted_zone_id)
    status = stack_status()
    parameters = stack_parameters() if status in ("CREATE_COMPLETE", "UPDATE_COMPLETE") else {}
    outputs = stack_outputs() if parameters else {}
    if existing:
        if current:
            resources = aws("elasticbeanstalk", "describe-environment-resources", "--environment-name", ENV)["EnvironmentResources"]
            lbs = resources["LoadBalancers"]
            if len(lbs) != 1:
                raise ValueError("Cannot verify DNS ownership: unexpected EB load balancers")
            alb = aws("elbv2", "describe-load-balancers", "--names", lbs[0]["Name"])["LoadBalancers"][0]
            if existing["AliasTarget"]["DNSName"].rstrip(".") != alb["DNSName"].rstrip("."):
                raise ValueError("Website DNS does not point at the named environment")
        else:
            expected = args.expected_alb_dns
            if outputs:
                recorded = aws("ssm", "get-parameter", "--name", outputs["ExpectedAlbParameterName"])["Parameter"]["Value"]
                if expected and expected != recorded:
                    raise ValueError("Supplied ALB differs from the named foundation record")
                expected = recorded
            if not expected or expected == "UNCONFIGURED" or existing.get("AliasTarget", {}).get("DNSName", "").rstrip(".") != expected.rstrip("."):
                raise ValueError("No named EB environment exists; supply and verify the exact prior ALB before deleting DNS")
        change_dns(args.hosted_zone_id, "DELETE", existing)
    if current and current.get("Status") not in ("Terminating", "Terminated"):
        command("elasticbeanstalk", "terminate-environment", "--environment-name", ENV)
    if current:
        wait_for_environment("Terminated")
    apps = aws("elasticbeanstalk", "describe-applications", "--application-names", APP)["Applications"]
    if apps:
        versions = aws("elasticbeanstalk", "describe-application-versions", "--application-name", APP)["ApplicationVersions"]
        for version in versions:
            if not version["VersionLabel"].startswith("main-"):
                raise ValueError("Unexpected application version; inspect before deleting the application")
        command("elasticbeanstalk", "delete-application", "--application-name", APP)
    if status:
        command("cloudformation", "delete-stack", "--stack-name", STACK)
        command("cloudformation", "wait", "stack-delete-complete", "--stack-name", STACK)
    bucket = parameters.get("BootstrapBucket") or args.bucket
    if bucket:
        if bucket != f"elasticbeanstalk-{REGION}-{ACCOUNT}":
            raise ValueError("Deployment bucket does not match the reviewed account and region")
        for prefix in (RELEASE_PREFIX, BOOTSTRAP_PREFIX):
            command("s3", "rm", f"s3://{bucket}/{prefix}/", "--recursive")
    names = {row["BudgetName"] for row in aws("budgets", "describe-budgets", "--account-id", ACCOUNT)["Budgets"]}
    if BUDGET in names:
        command("budgets", "delete-budget", "--account-id", ACCOUNT, "--budget-name", BUDGET)
    print(json.dumps({"removed": HOST, "foundation": STACK, "deploymentPrefixes": [RELEASE_PREFIX, BOOTSTRAP_PREFIX]}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    setup_parser = sub.add_parser("setup", help="Create the reviewed foundation, alerts and relay")
    for name in ("vpc-id", "relay-subnet-id", "relay-ami-id", "hosted-zone-id", "alert-email"):
        setup_parser.add_argument("--" + name, required=True)
    setup_parser.add_argument("--reviewed-cost-record", required=True, type=Path)
    deploy_parser = sub.add_parser("deploy", help="Deploy an immutable source bundle to EB")
    for name in ("vpc-id", "subnets", "service-role", "solution-stack", "hosted-zone-id"):
        deploy_parser.add_argument("--" + name, required=True)
    deploy_parser.add_argument("--bundle", required=True, type=Path)
    deploy_parser.add_argument("--update", action="store_true")
    rollback_parser = sub.add_parser("rollback", help="Restore a previous immutable EB version")
    rollback_parser.add_argument("--version", required=True)
    teardown_parser = sub.add_parser("teardown", help="Remove only Retro Coop website resources")
    teardown_parser.add_argument("--hosted-zone-id", required=True)
    teardown_parser.add_argument("--confirm", required=True)
    teardown_parser.add_argument("--expected-alb-dns")
    teardown_parser.add_argument("--bucket", help="Exact EB storage bucket for partial setup cleanup")
    args = parser.parse_args()
    try:
        {"setup": setup, "deploy": deploy, "rollback": rollback, "teardown": teardown}[args.action](args)
    except (ValueError, KeyError, subprocess.CalledProcessError, TimeoutError) as error:
        print(f"{args.action} stopped: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
