"""Scheduled, resource-scoped single-instance website shutdown at the monthly $100 Budget."""

import ipaddress
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
            config["expectedIpParameter"] != "/retro-coop/website/expected-ip":
        raise GuardError("Cost guard configuration differs from the named website")
    actual, forecast = current_budget(clients["budgets"])
    result = {"actualUsd": str(actual), "forecastUsd": str(forecast), "limitUsd": str(LIMIT),
              "dryRun": event.get("dryRun") is True, "wouldStop": actual >= LIMIT or forecast >= LIMIT}
    if not result["wouldStop"]:
        result["actions"] = []
        return result

    expected = clients["ssm"].get_parameter(Name=config["expectedIpParameter"])["Parameter"]["Value"]
    record = website_record(clients["route53"], config["zoneId"])
    if record:
        try:
            expected = str(ipaddress.IPv4Address(expected))
        except ipaddress.AddressValueError as error:
            raise GuardError("Recorded website Elastic IP is invalid") from error
        if record.get("ResourceRecords") != [{"Value": expected}] or record.get("AliasTarget"):
            raise GuardError("Website DNS no longer points at the recorded Retro Coop Elastic IP")
    environments = clients["eb"].describe_environments(ApplicationName=APP, EnvironmentNames=[ENV],
                                                          IncludeDeleted=False)["Environments"]
    if len(environments) > 1 or environments and environments[0].get("EnvironmentArn") != \
            f"arn:aws:elasticbeanstalk:us-east-1:{ACCOUNT}:environment/{APP}/{ENV}":
        raise GuardError("EB environment does not match the named website")
    actions = []
    if record:
        actions.append("delete_exact_website_a_record")
    if environments and environments[0]["Status"] not in ("Terminated", "Terminating"):
        actions.append("terminate_named_eb_environment_and_instance")
    result["actions"] = actions
    if result["dryRun"]:
        return result
    if record:
        clients["route53"].change_resource_record_sets(HostedZoneId=config["zoneId"],
            ChangeBatch={"Changes": [{"Action": "DELETE", "ResourceRecordSet": record}]})
    if "terminate_named_eb_environment_and_instance" in actions:
        clients["eb"].terminate_environment(ApplicationName=APP, EnvironmentName=ENV)
    return result


def handler(event, _context):
    import boto3

    clients = {name: boto3.client(service, region_name="us-east-1") for name, service in {
        "budgets": "budgets", "ssm": "ssm", "route53": "route53",
        "eb": "elasticbeanstalk"}.items()}
    config = {"account": os.environ["ACCOUNT_ID"], "hostname": os.environ["HOSTNAME"],
              "zoneId": os.environ["HOSTED_ZONE_ID"],
              "expectedIpParameter": os.environ["EXPECTED_IP_PARAMETER"]}
    result = evaluate(event if isinstance(event, dict) else {}, clients, config)
    print(json.dumps(result, sort_keys=True))
    return result
