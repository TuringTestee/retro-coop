"""Scheduled, resource-scoped website shutdown when the monthly Budget reaches $100."""

import json
import os
from decimal import Decimal, InvalidOperation


ACCOUNT = "599796577790"
BUDGET = "retro-coop-website-monthly"
APP = "retro-coop"
ENV = "retro-coop-web"
HOST = "retro-coop.1001.page"
LIMIT = Decimal("100")


class GuardError(Exception):
    pass


def amount(value: dict | None) -> Decimal:
    if not isinstance(value, dict) or value.get("Unit") != "USD":
        raise GuardError("Monthly Budget spend is missing or is not USD")
    try:
        parsed = Decimal(str(value["Amount"]))
    except (KeyError, InvalidOperation, TypeError) as error:
        raise GuardError("Monthly Budget spend has no valid amount") from error
    if not parsed.is_finite() or parsed < 0:
        raise GuardError("Monthly Budget spend is not finite and nonnegative")
    return parsed


def current_budget(client) -> tuple[Decimal, Decimal]:
    budget = client.describe_budget(AccountId=ACCOUNT, BudgetName=BUDGET)["Budget"]
    if budget.get("BudgetName") != BUDGET or budget.get("BudgetType") != "COST" or \
            budget.get("TimeUnit") != "MONTHLY" or budget.get("CostFilters") or \
            amount(budget.get("BudgetLimit")) != LIMIT:
        raise GuardError("Named account-wide monthly Budget differs from the reviewed $100 policy")
    spend = budget.get("CalculatedSpend")
    if not isinstance(spend, dict):
        raise GuardError("Monthly Budget has no calculated spend")
    return amount(spend.get("ActualSpend")), amount(spend.get("ForecastedSpend"))


def website_record(route, zone_id: str) -> dict | None:
    rows = route.list_resource_record_sets(HostedZoneId=zone_id, StartRecordName=HOST,
                                           StartRecordType="A", MaxItems="1")["ResourceRecordSets"]
    return rows[0] if rows and rows[0]["Name"].rstrip(".") == HOST and rows[0]["Type"] == "A" else None


def evaluate(event: dict, clients: dict, config: dict) -> dict:
    if config["account"] != ACCOUNT or config["hostname"] != HOST or not config["zoneId"].startswith("Z") or \
            not config["relayInstanceId"].startswith("i-") or config["expectedAlbParameter"] != "/retro-coop/website/expected-alb-dns":
        raise GuardError("Cost guard configuration differs from the named website")
    actual, forecast = current_budget(clients["budgets"])
    result = {"actualUsd": str(actual), "forecastUsd": str(forecast), "limitUsd": str(LIMIT),
              "dryRun": event.get("dryRun") is True, "wouldStop": actual >= LIMIT or forecast >= LIMIT}
    if not result["wouldStop"]:
        result["actions"] = []
        return result

    expected = clients["ssm"].get_parameter(Name=config["expectedAlbParameter"])["Parameter"]["Value"].rstrip(".")
    record = website_record(clients["route53"], config["zoneId"])
    if record:
        alias = record.get("AliasTarget")
        if expected == "UNCONFIGURED" or not isinstance(alias, dict) or alias.get("DNSName", "").rstrip(".") != expected:
            raise GuardError("Website DNS no longer points at the recorded Retro Coop ALB")
    environments = clients["eb"].describe_environments(ApplicationName=APP, EnvironmentNames=[ENV],
                                                          IncludeDeleted=False)["Environments"]
    if len(environments) > 1 or environments and environments[0].get("EnvironmentArn") != \
            f"arn:aws:elasticbeanstalk:us-east-1:{ACCOUNT}:environment/{APP}/{ENV}":
        raise GuardError("EB environment does not match the named website")
    try:
        relay = clients["ec2"].describe_instances(InstanceIds=[config["relayInstanceId"]])["Reservations"]
        relay_instances = [instance for reservation in relay for instance in reservation["Instances"]]
    except Exception as error:
        if getattr(error, "response", {}).get("Error", {}).get("Code") == "InvalidInstanceID.NotFound":
            relay_instances = []
        else:
            raise
    if len(relay_instances) > 1 or relay_instances and relay_instances[0]["InstanceId"] != config["relayInstanceId"]:
        raise GuardError("Relay instance does not match the named website")
    if relay_instances and {item["Key"]: item["Value"] for item in relay_instances[0].get("Tags", [])}.get("Project") != "retro-coop":
        raise GuardError("Relay instance lacks the named website tag")
    actions = []
    if record:
        actions.append("delete_exact_website_alias")
    if environments and environments[0]["Status"] not in ("Terminated", "Terminating"):
        actions.append("terminate_named_eb_environment")
    if relay_instances and relay_instances[0]["State"]["Name"] not in ("terminated", "shutting-down"):
        actions.append("terminate_named_relay")
    result["actions"] = actions
    if result["dryRun"]:
        return result
    if record:
        clients["route53"].change_resource_record_sets(HostedZoneId=config["zoneId"],
            ChangeBatch={"Changes": [{"Action": "DELETE", "ResourceRecordSet": record}]})
    if "terminate_named_eb_environment" in actions:
        clients["eb"].terminate_environment(ApplicationName=APP, EnvironmentName=ENV)
    if "terminate_named_relay" in actions:
        clients["ec2"].terminate_instances(InstanceIds=[config["relayInstanceId"]])
    return result


def handler(event, _context):
    import boto3

    clients = {name: boto3.client(service, region_name="us-east-1") for name, service in {
        "budgets": "budgets", "ssm": "ssm", "route53": "route53",
        "eb": "elasticbeanstalk", "ec2": "ec2"}.items()}
    config = {"account": os.environ["ACCOUNT_ID"], "hostname": os.environ["HOSTNAME"],
              "zoneId": os.environ["HOSTED_ZONE_ID"], "relayInstanceId": os.environ["RELAY_INSTANCE_ID"],
              "expectedAlbParameter": os.environ["EXPECTED_ALB_PARAMETER"]}
    result = evaluate(event if isinstance(event, dict) else {}, clients, config)
    print(json.dumps(result, sort_keys=True))
    return result
