#!/usr/bin/env python3
"""Provision, deploy, roll back or remove only the named one-machine Retro Coop AWS website."""

import argparse
import ipaddress
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
HOST = "retro-coop.atobot.cloud"
PARENT_DOMAIN = "atobot.cloud"
APP = "retro-coop"
ENV = "retro-coop-web"
STACK = "retro-coop-website-foundation"
BUDGET = "retro-coop-website-monthly"
BOOTSTRAP_PREFIX = "retro-coop/bootstrap"
RELEASE_PREFIX = "retro-coop/releases"
INSTANCE_TYPE = "t4g.micro"
REVIEWED_PLAN_REVISION = "8a516aa4bb49364df38c514e184abcbcae7b216a"


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


def stack_status() -> str | None:
    rows = aws("cloudformation", "list-stacks")["StackSummaries"]
    active = [row["StackStatus"] for row in rows if row["StackName"] == STACK and row["StackStatus"] != "DELETE_COMPLETE"]
    if len(active) > 1:
        raise ValueError("More than one active foundation stack has the reviewed name")
    return active[0] if active else None


def stack_details() -> dict:
    stack = aws("cloudformation", "describe-stacks", "--stack-name", STACK)["Stacks"]
    if len(stack) != 1 or stack[0]["StackStatus"] not in ("CREATE_COMPLETE", "UPDATE_COMPLETE"):
        raise ValueError("The Retro Coop foundation stack is not ready")
    return stack[0]


def stack_outputs() -> dict[str, str]:
    return {row["OutputKey"]: row["OutputValue"] for row in stack_details()["Outputs"]}


def stack_parameters() -> dict[str, str]:
    return {row["ParameterKey"]: row["ParameterValue"] for row in stack_details()["Parameters"]}


def environment() -> dict | None:
    rows = aws("elasticbeanstalk", "describe-environments", "--application-name", APP,
               "--environment-names", ENV).get("Environments", [])
    return rows[0] if rows else None


def dns_record(zone: str) -> dict | None:
    rows = aws("route53", "list-resource-record-sets", "--hosted-zone-id", zone,
               "--start-record-name", HOST, "--start-record-type", "A", "--max-items", "1")["ResourceRecordSets"]
    return rows[0] if rows and rows[0]["Name"].rstrip(".") == HOST and rows[0]["Type"] == "A" else None


def address(record: dict | None) -> str | None:
    if record is None:
        return None
    rows = record.get("ResourceRecords")
    if record.get("AliasTarget") or not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("Website A record has an unexpected shape")
    try:
        return str(ipaddress.IPv4Address(rows[0]["Value"]))
    except (KeyError, ipaddress.AddressValueError) as error:
        raise ValueError("Website A record has an invalid IPv4 address") from error


def a_record(ip: str) -> dict:
    return {"Name": HOST + ".", "Type": "A", "TTL": 60, "ResourceRecords": [{"Value": str(ipaddress.IPv4Address(ip))}]}


def verify_delegation(zone: str) -> None:
    hosted = aws("route53", "get-hosted-zone", "--id", zone)
    if hosted["HostedZone"]["Name"].rstrip(".") != PARENT_DOMAIN or \
            hosted["HostedZone"]["Config"].get("PrivateZone"):
        raise ValueError("Expected the public atobot.cloud hosted zone")
    expected = {name.lower().rstrip(".") for name in hosted["DelegationSet"]["NameServers"]}
    registered = aws("route53domains", "get-domain-detail", "--domain-name", PARENT_DOMAIN)
    registrar = {row["Name"].lower().rstrip(".") for row in registered["Nameservers"]}
    public = subprocess.run(["dig", "+short", "NS", PARENT_DOMAIN, "@8.8.8.8"],
                            capture_output=True, text=True, check=True)
    resolved = {name.lower().rstrip(".") for name in public.stdout.splitlines()}
    if not expected or registrar != expected or resolved != expected:
        raise ValueError("atobot.cloud is not publicly delegated to the reviewed Route 53 zone")


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
    response = aws("route53", "change-resource-record-sets", "--hosted-zone-id", zone,
                   "--change-batch", json.dumps(payload, separators=(",", ":")))
    change_id = response["ChangeInfo"]["Id"]
    command("route53", "wait", "resource-record-sets-changed", "--id", change_id)


def wait_for_environment(desired: str, timeout: int = 1800) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = environment()
        if desired == "Terminated" and (not current or current.get("Status") == "Terminated"):
            return current or {}
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
    if cost.get("warningUsd") != 50 or cost.get("shutdownProjectedUsd") != 100 or \
            cost.get("reviewedPlanRevision") != REVIEWED_PLAN_REVISION:
        raise ValueError("Cost record must name the reviewed plan and $50/$100 operating thresholds")
    projected = cost.get("projected31DayUsd")
    if isinstance(projected, bool) or not isinstance(projected, (int, float)) or not 0 < projected < 100:
        raise ValueError("The 31-day cost scenario exceeds the reviewed $100 operating ceiling")
    if not re.fullmatch(r"Z[A-Z0-9]+", args.hosted_zone_id):
        raise ValueError("Use the bare Route 53 hosted zone ID")
    if dns_record(args.hosted_zone_id) or stack_status() or environment():
        raise ValueError("Named website DNS, foundation or environment already exists; inspect before setup")
    if aws("elasticbeanstalk", "describe-applications", "--application-names", APP)["Applications"]:
        raise ValueError("The named EB application already exists; inspect it before provisioning")
    verify_delegation(args.hosted_zone_id)
    aws("ec2", "describe-vpcs", "--vpc-ids", args.vpc_id)["Vpcs"][0]
    bucket = aws("elasticbeanstalk", "create-storage-location")["S3Bucket"]
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    guard_key = f"{BOOTSTRAP_PREFIX}/cost-guard-{revision}.zip"
    with tempfile.TemporaryDirectory(prefix="retro-eb-guard-") as directory:
        package = Path(directory) / "cost-guard.zip"
        with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(ROOT / "scripts/aws_eb/cost_guard.py", "cost_guard.py")
        command("s3", "cp", str(package), f"s3://{bucket}/{guard_key}")
    budget(args.alert_email)
    command("cloudformation", "deploy", "--template-file", str(ROOT / "deploy/aws-eb/foundation.yaml"),
            "--stack-name", STACK, "--capabilities", "CAPABILITY_NAMED_IAM", "--parameter-overrides",
            f"VpcId={args.vpc_id}", f"HostedZoneId={args.hosted_zone_id}", f"BootstrapBucket={bucket}",
            f"GuardCodeKey={guard_key}", f"AlertEmail={args.alert_email}")
    outputs = stack_outputs()
    print(json.dumps({"foundation": STACK, "ecrRepository": outputs["EcrRepository"], "bucket": bucket,
                      "operatorStep": "Inspect the cost guard failure alarms until its email subscription is confirmed."}))


def setting(namespace: str, name: str, value: str) -> dict:
    return {"Namespace": namespace, "OptionName": name, "Value": value}


def connection_options() -> list[dict]:
    namespace = "aws:elasticbeanstalk:application:environment"
    return [setting(namespace, "COORDINATOR_ORIGINS", f"https://{HOST}"),
            setting(namespace, "TURN_URLS", f"turn:{HOST}:3478?transport=udp")]


def connection_values() -> dict[str, str]:
    rows = aws("elasticbeanstalk", "describe-configuration-settings", "--application-name", APP,
               "--environment-name", ENV)["ConfigurationSettings"]
    deployed = [row for row in rows if row.get("DeploymentStatus") == "deployed"]
    if len(deployed) != 1:
        raise ValueError("Expected one deployed EB configuration")
    expected = {row["OptionName"] for row in connection_options()}
    relevant = [row for row in deployed[0]["OptionSettings"]
                if row.get("Namespace") == "aws:elasticbeanstalk:application:environment" and
                row.get("OptionName") in expected]
    if len(relevant) != len(expected):
        raise ValueError("EB connection settings are missing or duplicated")
    return {row["OptionName"]: row["Value"] for row in relevant}


def wait_for_existing_state(version: str, values: dict[str, str], timeout: int = 1800) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = environment()
        if current and current.get("Status") == "Ready" and current.get("Health") == "Green" and \
                current.get("VersionLabel") == version and connection_values() == values:
            return current
        if current and current.get("Status") in ("Terminated", "Terminating"):
            raise RuntimeError("EB environment terminated during migration")
        time.sleep(15)
    raise TimeoutError("EB did not finish the requested version and connection settings")


def update_existing_environment(version: str, previous_version: str) -> dict:
    target = {row["OptionName"]: row["Value"] for row in connection_options()}
    previous = connection_values()
    changed = previous != target
    try:
        if changed:
            command("elasticbeanstalk", "update-environment", "--environment-name", ENV,
                    "--option-settings", json.dumps(connection_options()))
            wait_for_existing_state(previous_version, target)
        command("elasticbeanstalk", "update-environment", "--environment-name", ENV, "--version-label", version)
        return wait_for_existing_state(version, target)
    except Exception as error:
        if not changed:
            # A timed-out EB request can still finish. Observe the in-flight update
            # before reporting failure, so the next release does not race it.
            try:
                current = wait_for_environment("Ready", timeout=1800)
                if current.get("VersionLabel") == version and connection_values() == target:
                    return current
                if current.get("VersionLabel") != previous_version or connection_values() != previous:
                    raise ValueError("EB settled on an unexpected version or connection settings")
            except Exception as recovery_error:
                raise RuntimeError("EB update did not settle on the expected website version; inspect the environment") from recovery_error
            raise error
        if changed:
            try:
                current = wait_for_environment("Ready", timeout=300)
                if current.get("VersionLabel") == version:
                    command("elasticbeanstalk", "update-environment", "--environment-name", ENV,
                            "--version-label", previous_version)
                    current = wait_for_existing_state(previous_version, target)
                if current.get("VersionLabel") != previous_version:
                    raise ValueError("EB is on an unexpected version")
                if connection_values() != previous:
                    restored = [setting("aws:elasticbeanstalk:application:environment", name, value)
                                for name, value in previous.items()]
                    command("elasticbeanstalk", "update-environment", "--environment-name", ENV,
                            "--option-settings", json.dumps(restored))
                    wait_for_existing_state(previous_version, previous)
            except Exception as restore_error:
                raise RuntimeError("EB migration failed and previous settings could not be restored; inspect the environment") from restore_error
        raise error


def options(outputs: dict[str, str], args: argparse.Namespace) -> list[dict]:
    environment_ns = "aws:elasticbeanstalk:environment"
    launch = "aws:autoscaling:launchconfiguration"
    return [
        setting(environment_ns, "EnvironmentType", "SingleInstance"),
        setting(environment_ns, "ServiceRole", args.service_role),
        setting("aws:elasticbeanstalk:healthreporting:system", "SystemType", "basic"),
        setting("aws:autoscaling:asg", "MinSize", "1"),
        setting("aws:autoscaling:asg", "MaxSize", "1"),
        setting(launch, "IamInstanceProfile", outputs["EbProfileName"]),
        setting(launch, "InstanceType", INSTANCE_TYPE),
        setting(launch, "RootVolumeType", "gp3"),
        setting(launch, "RootVolumeSize", "28"),
        setting(launch, "DisableIMDSv1", "true"),
        setting(launch, "DisableDefaultEC2SecurityGroup", "true"),
        setting(launch, "SecurityGroups", outputs["AppSecurityGroupId"]),
        setting("aws:ec2:vpc", "VPCId", args.vpc_id),
        setting("aws:ec2:vpc", "Subnets", args.subnet),
        setting("aws:ec2:vpc", "AssociatePublicIpAddress", "true"),
        *connection_options(),
        setting("aws:elasticbeanstalk:application:environmentsecrets", "TURN_SECRET", outputs["TurnSecretArn"]),
    ]


def instance_and_eip(outputs: dict[str, str], resources: dict) -> tuple[str, str]:
    instances = resources["Instances"]
    if len(instances) != 1 or resources.get("LoadBalancers"):
        raise ValueError("Expected exactly one EB app instance and no load balancer")
    instance_id = instances[0]["Id"]
    instance = aws("ec2", "describe-instances", "--instance-ids", instance_id)["Reservations"][0]["Instances"][0]
    groups = {group["GroupId"] for group in instance["SecurityGroups"]}
    if groups != {outputs["AppSecurityGroupId"]} or instance["InstanceType"] != INSTANCE_TYPE or \
            instance.get("Architecture") != "arm64":
        raise ValueError("EB attached unexpected groups or did not launch the reviewed ARM64 micro instance")
    addresses = aws("ec2", "describe-addresses", "--filters", f"Name=instance-id,Values={instance_id}")["Addresses"]
    if len(addresses) != 1 or addresses[0].get("InstanceId") != instance_id or \
            addresses[0].get("Domain") != "vpc" or not addresses[0].get("AssociationId"):
        raise ValueError("The sole EB instance has no verified Elastic IP")
    ip = str(ipaddress.IPv4Address(addresses[0]["PublicIp"]))
    group = aws("ec2", "describe-security-groups", "--group-ids", outputs["AppSecurityGroupId"])["SecurityGroups"][0]
    actual = {(row["IpProtocol"], row.get("FromPort"), row.get("ToPort"),
               tuple(item["CidrIp"] for item in row.get("IpRanges", []))) for row in group["IpPermissions"]}
    expected = {("tcp", 80, 80, ("0.0.0.0/0",)), ("tcp", 443, 443, ("0.0.0.0/0",)),
                ("udp", 3478, 3478, ("0.0.0.0/0",)), ("udp", 49160, 49175, ("0.0.0.0/0",))}
    if actual != expected or any(row.get("Ipv6Ranges") or row.get("UserIdGroupPairs") for row in group["IpPermissions"]):
        raise ValueError("The single instance has unexpected public ingress")
    return instance_id, ip


def verify_live_boundary(outputs: dict[str, str], resources: dict, load_test: bool) -> str:
    instance_id, ip = instance_and_eip(outputs, resources)
    commands = ["ss -H -ltn", "ss -H -lun", "curl -fsS http://127.0.0.1:8080/healthz",
                "docker ps --format '{{.Names}}'"]
    if load_test:
        commands.append("set -e; coordinator=$(docker ps --filter label=com.docker.compose.service=coordinator --format '{{.ID}}'); test -n \"$coordinator\"; docker exec \"$coordinator\" node /app/memory_probe.mjs; docker restart \"$coordinator\" >/dev/null; for n in $(seq 1 20); do curl -fsS http://127.0.0.1:8080/healthz >/dev/null && break; sleep 1; done; curl -fsS http://127.0.0.1:8080/healthz")
    else:
        commands.append("awk '/MemAvailable/{print \"AvailableKiB:\" $2}' /proc/meminfo")
    command_id = aws("ssm", "send-command", "--instance-ids", instance_id, "--document-name", "AWS-RunShellScript",
                     "--parameters", json.dumps({"commands": commands}))["Command"]["CommandId"]
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            result = aws("ssm", "get-command-invocation", "--command-id", command_id, "--instance-id", instance_id)
        except subprocess.CalledProcessError as error:
            if "InvocationDoesNotExist" not in (error.stderr or ""):
                raise
            time.sleep(5)
            continue
        if result["Status"] == "Success":
            output = result["StandardOutputContent"]
            if not all(value in output for value in ("127.0.0.1:8787", "127.0.0.1:8080", ":80", ":443", ":3478", "retro-coop-coordinator")):
                raise ValueError("The single instance lacks its loopback web or public TURN listeners")
            names = output.splitlines()
            if not all(any(service in name for name in names) for service in ("coordinator", "edge", "caddy", "turn")):
                raise ValueError("The single-instance Compose services are incomplete")
            if load_test:
                match = re.search(r"^MEMORY_PROOF:(\{[^\n]+\})$", output, re.MULTILINE)
                proof = json.loads(match.group(1)) if match else {}
                if proof.get("rooms") != 20 or proof.get("romBytes") != 20 * (16 + 16384) or \
                        proof.get("availableKiB", 0) < 128000:
                    raise ValueError("The 20-room ROM workload lacks 128 MiB host memory headroom; inspect before DNS")
            else:
                match = re.search(r"AvailableKiB:(\d+)", output)
                if not match or int(match.group(1)) < 128000:
                    raise ValueError("The micro instance has less than 128 MiB available after update")
            return ip
        if result["Status"] in ("Failed", "Cancelled", "TimedOut"):
            raise ValueError("SSM could not confirm the single-instance boundary")
        time.sleep(5)
    raise TimeoutError("SSM instance boundary check did not finish")


def verify_guard(outputs: dict[str, str], ip: str, old_ip: str | None) -> tuple[dict, str]:
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
    notices = aws("budgets", "describe-notifications-for-budget", "--account-id", ACCOUNT,
                  "--budget-name", BUDGET)["Notifications"]
    required = {("ACTUAL", 50.0), ("ACTUAL", 100.0), ("FORECASTED", 100.0)}
    present = {(row["NotificationType"], float(row["Threshold"])) for row in notices
               if row.get("ComparisonOperator") == "GREATER_THAN" and row.get("ThresholdType", "PERCENTAGE") == "PERCENTAGE"}
    if not required.issubset(present):
        raise ValueError("The $50/$100 actual and forecast Budget alerts are incomplete")
    for row in notices:
        if (row.get("NotificationType"), float(row.get("Threshold", -1))) not in required:
            continue
        notice = {key: row[key] for key in ("NotificationType", "ComparisonOperator", "Threshold")}
        notice["ThresholdType"] = row.get("ThresholdType", "PERCENTAGE")
        subscribers = aws("budgets", "describe-subscribers-for-notification", "--account-id", ACCOUNT,
                          "--budget-name", BUDGET, "--notification", json.dumps(notice))["Subscribers"]
        if {"SubscriptionType": "EMAIL", "Address": email} not in subscribers:
            raise ValueError("The Budget alert recipient differs from the reviewed operator input")
    schedule = aws("scheduler", "get-schedule", "--name", outputs["GuardScheduleName"],
                   "--group-name", outputs["GuardScheduleGroupName"])
    if schedule.get("State") != "ENABLED" or schedule.get("ScheduleExpression") != "rate(6 hours)" or \
            schedule.get("Target", {}).get("Arn") != outputs["GuardFunctionArn"] or \
            json.loads(schedule.get("Target", {}).get("Input", "null")) != {"dryRun": False}:
        raise ValueError("The six-hour cost guard schedule is not enabled for real shutdown")
    subscribers = aws("sns", "list-subscriptions-by-topic", "--topic-arn", outputs["GuardAlertTopicArn"])["Subscriptions"]
    if not any(row.get("Endpoint") == email and row.get("Protocol") == "email" for row in subscribers):
        raise ValueError("The cost guard failure alert recipient is missing")
    if not any(row.get("Endpoint") == email and row.get("Protocol") == "email" and
               row.get("SubscriptionArn", "PendingConfirmation") != "PendingConfirmation" for row in subscribers):
        print("Guard failure email is pending; inspect its CloudWatch alarms until confirmed.", file=sys.stderr)
    for name, namespace, metric, dimension in (
        ("retro-coop-cost-guard-errors", "AWS/Lambda", "Errors", "FunctionName"),
        ("retro-coop-cost-guard-delivery-errors", "AWS/Scheduler", "TargetErrorCount", "ScheduleGroup"),
        ("retro-coop-cost-guard-dropped-invocations", "AWS/Scheduler", "InvocationDroppedCount", "ScheduleGroup"),
    ):
        alarms = aws("cloudwatch", "describe-alarms", "--alarm-names", name)["MetricAlarms"]
        dimension_value = "retro-coop-cost-guard" if dimension == "FunctionName" else outputs["GuardScheduleGroupName"]
        if len(alarms) != 1 or not alarms[0].get("ActionsEnabled") or \
                outputs["GuardAlertTopicArn"] not in alarms[0].get("AlarmActions", []) or \
                alarms[0].get("Namespace") != namespace or alarms[0].get("MetricName") != metric or \
                alarms[0].get("Dimensions") != [{"Name": dimension, "Value": dimension_value}] or \
                alarms[0].get("ComparisonOperator") != "GreaterThanThreshold" or alarms[0].get("Threshold") != 0:
            raise ValueError(f"Cost guard alarm {name} is missing or changed")
    parameter = outputs["ExpectedIpParameterName"]
    previous = aws("ssm", "get-parameter", "--name", parameter)["Parameter"]["Value"]
    if previous not in ("UNCONFIGURED", ip) and previous != old_ip:
        raise ValueError("Recorded website Elastic IP differs from this EB environment and DNS")
    if old_ip and previous != old_ip and previous != ip:
        raise ValueError("The existing DNS A record is not owned by this website")
    if previous != ip:
        command("ssm", "put-parameter", "--name", parameter, "--type", "String", "--value", ip, "--overwrite")
    if aws("ssm", "get-parameter", "--name", parameter)["Parameter"]["Value"] != ip:
        raise ValueError("Cost guard did not record the exact website Elastic IP")
    try:
        with tempfile.TemporaryDirectory(prefix="retro-eb-guard-probe-") as directory:
            path = Path(directory) / "result.json"
            metadata = aws("lambda", "invoke", "--function-name", outputs["GuardFunctionArn"],
                           "--payload", '{"dryRun":true}', "--cli-binary-format", "raw-in-base64-out", str(path))
            if metadata.get("StatusCode") != 200 or metadata.get("FunctionError"):
                raise ValueError("Cost guard dry run failed; inspect its content-free CloudWatch error log")
            result = json.loads(path.read_text())
        if result.get("dryRun") is not True or result.get("wouldStop") is not False or result.get("actions") != []:
            raise ValueError("Cost guard dry run did not confirm operation below the shutdown threshold")
    except Exception:
        if previous != ip:
            command("ssm", "put-parameter", "--name", parameter, "--type", "String", "--value", previous, "--overwrite")
        raise
    return result, previous


def release_record(bundle: Path) -> dict:
    with zipfile.ZipFile(bundle) as archive:
        if set(archive.namelist()) != {"docker-compose.yml", "release.json", ".ebextensions/01-environment.config"}:
            raise ValueError("Unexpected source bundle contents")
        record = json.loads(archive.read("release.json"))
        compose = archive.read("docker-compose.yml").decode()
    for name in ("edgeImage", "coordinatorImage", "caddyImage", "turnImage"):
        if not IMAGE.fullmatch(record.get(name, "")) or record[name] not in compose:
            raise ValueError("Release images are not pinned to the reviewed ECR repository")
    return record


def https_probe(ip: str, timeout: int = 300) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(["curl", "--silent", "--show-error", "--fail", "--max-time", "10", "--resolve",
                                 f"{HOST}:443:{ip}", f"https://{HOST}/healthz"], capture_output=True, text=True)
        if result.returncode == 0 and "retro-coop" in result.stdout:
            return
        time.sleep(10)
    raise TimeoutError("Public HTTPS certificate and health did not become ready after DNS publication")


def deploy(args: argparse.Namespace) -> None:
    reviewed_main()
    identity()
    outputs = stack_outputs()
    if args.hosted_zone_id != stack_parameters()["HostedZoneId"]:
        raise ValueError("Deploy hosted zone differs from the named foundation")
    verify_delegation(args.hosted_zone_id)
    record = release_record(args.bundle)
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    if record["sourceRevision"] != revision:
        raise ValueError("Release bundle was not built from the checked-out reviewed main")
    group = aws("ec2", "describe-security-groups", "--group-ids", outputs["AppSecurityGroupId"])["SecurityGroups"][0]
    if args.vpc_id != group["VpcId"] or not public_subnet(args.subnet, args.vpc_id):
        raise ValueError("EB subnet must be public and in the scoped VPC")
    existing_env = environment()
    if existing_env and not args.update:
        raise ValueError("The EB environment exists; pass --update for a reviewed release")
    if not existing_env and args.update:
        raise ValueError("The EB environment does not exist for an update")
    bucket = aws("elasticbeanstalk", "create-storage-location")["S3Bucket"]
    version = f"main-{revision[:12]}"
    key = f"{RELEASE_PREFIX}/{version}.zip"
    command("s3", "cp", str(args.bundle), f"s3://{bucket}/{key}")
    if not aws("elasticbeanstalk", "describe-applications", "--application-names", APP)["Applications"]:
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
        current = update_existing_environment(version, existing_env["VersionLabel"])
    else:
        command("elasticbeanstalk", "create-environment", "--application-name", APP,
                "--environment-name", ENV, "--version-label", version,
                "--solution-stack-name", args.solution_stack, "--option-settings", json.dumps(options(outputs, args)))
        current = wait_for_environment("Ready")
    resources = aws("elasticbeanstalk", "describe-environment-resources", "--environment-name", ENV)["EnvironmentResources"]
    old_record = dns_record(args.hosted_zone_id)
    ip = verify_live_boundary(outputs, resources, load_test=old_record is None)
    old_ip = address(old_record)
    guard, previous = verify_guard(outputs, ip, old_ip)
    new_record = a_record(ip)
    changed = old_record != new_record
    if changed:
        try:
            change_dns(args.hosted_zone_id, "UPSERT" if old_record else "CREATE", new_record)
        except Exception:
            if previous != ip:
                command("ssm", "put-parameter", "--name", outputs["ExpectedIpParameterName"],
                        "--type", "String", "--value", previous, "--overwrite")
            raise
    try:
        https_probe(ip)
    except Exception:
        if changed:
            change_dns(args.hosted_zone_id, "UPSERT" if old_record else "DELETE", old_record or new_record)
        if previous != ip:
            command("ssm", "put-parameter", "--name", outputs["ExpectedIpParameterName"],
                    "--type", "String", "--value", previous, "--overwrite")
        raise
    print(json.dumps({"endpoint": f"https://{HOST}", "version": version, "status": current["Status"],
                      "health": current.get("Health"), "elasticIp": ip, "bundle": f"s3://{bucket}/{key}",
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
    if parameters and args.hosted_zone_id != parameters["HostedZoneId"]:
        raise ValueError("Teardown hosted zone differs from the named foundation")
    if existing:
        expected = args.expected_ip
        if outputs:
            recorded = aws("ssm", "get-parameter", "--name", outputs["ExpectedIpParameterName"])["Parameter"]["Value"]
            if expected and expected != recorded:
                raise ValueError("Supplied Elastic IP differs from the named foundation record")
            expected = recorded
        if not expected or expected == "UNCONFIGURED" or address(existing) != expected:
            raise ValueError("Website DNS does not match the exact recorded Elastic IP")
        change_dns(args.hosted_zone_id, "DELETE", existing)
    if current and current.get("Status") not in ("Terminating", "Terminated"):
        command("elasticbeanstalk", "terminate-environment", "--environment-name", ENV)
    if current:
        wait_for_environment("Terminated")
    apps = aws("elasticbeanstalk", "describe-applications", "--application-names", APP)["Applications"]
    if apps:
        versions = aws("elasticbeanstalk", "describe-application-versions", "--application-name", APP)["ApplicationVersions"]
        if any(not row["VersionLabel"].startswith("main-") for row in versions):
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
    setup_parser = sub.add_parser("setup", help="Create the reviewed foundation and cost alerts")
    for name in ("vpc-id", "hosted-zone-id", "alert-email"):
        setup_parser.add_argument("--" + name, required=True)
    setup_parser.add_argument("--reviewed-cost-record", required=True, type=Path)
    deploy_parser = sub.add_parser("deploy", help="Deploy an immutable source bundle to one EB instance")
    for name in ("vpc-id", "subnet", "service-role", "solution-stack", "hosted-zone-id"):
        deploy_parser.add_argument("--" + name, required=True)
    deploy_parser.add_argument("--bundle", required=True, type=Path)
    deploy_parser.add_argument("--update", action="store_true")
    rollback_parser = sub.add_parser("rollback", help="Restore a previous immutable EB version")
    rollback_parser.add_argument("--version", required=True)
    teardown_parser = sub.add_parser("teardown", help="Remove only Retro Coop website resources")
    teardown_parser.add_argument("--hosted-zone-id", required=True)
    teardown_parser.add_argument("--confirm", required=True)
    teardown_parser.add_argument("--expected-ip")
    teardown_parser.add_argument("--bucket", help="Exact EB storage bucket for partial setup cleanup")
    args = parser.parse_args()
    try:
        {"setup": setup, "deploy": deploy, "rollback": rollback, "teardown": teardown}[args.action](args)
    except (ValueError, KeyError, subprocess.CalledProcessError, TimeoutError) as error:
        print(f"{args.action} stopped: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
