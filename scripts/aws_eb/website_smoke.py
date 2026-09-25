#!/usr/bin/env python3
"""Exercise the EB operator's scoping and failure gates without contacting AWS."""

from argparse import Namespace
import json
from pathlib import Path

import website


outputs = {"EbProfileName": "retro-eb-profile", "AppSecurityGroupId": "sg-app",
           "AlbSecurityGroupId": "sg-alb", "CertificateArn": "arn:certificate",
           "RelayPublicIp": "54.1.2.3", "TurnSecretArn": "arn:turn-secret"}
settings = {(row["Namespace"], row["OptionName"]): row["Value"] for row in website.options(
    outputs, Namespace(service_role="retro-eb-service", vpc_id="vpc-1", subnets="subnet-a,subnet-b"))}
assert settings["aws:autoscaling:asg", "MinSize"] == "1"
assert settings["aws:autoscaling:asg", "MaxSize"] == "1"
assert settings["aws:autoscaling:launchconfiguration", "DisableDefaultEC2SecurityGroup"] == "true"
assert settings["aws:autoscaling:launchconfiguration", "SecurityGroups"] == "sg-app"
assert settings["aws:elbv2:loadbalancer", "SecurityGroups"] == "sg-alb"
assert settings["aws:elasticbeanstalk:application:environmentsecrets", "TURN_SECRET"] == "arn:turn-secret"
assert settings["aws:elasticbeanstalk:application:environment", "COORDINATOR_ORIGINS"] == "https://retro-coop.1001.page"
assert settings["aws:elasticbeanstalk:application:environment", "TURN_URLS"] == "turn:54.1.2.3:3478?transport=udp"
assert "8787" not in str(settings)

calls = []
website.command = lambda *args: calls.append(args)
website.budget("bill@example.test")
assert len(calls) == 1 and calls[0][:2] == ("budgets", "create-budget")
assert '"Threshold": 50' in calls[0][-1] and '"Threshold": 100' in calls[0][-1]
try:
    website.budget("bad-address")
    raise AssertionError("Invalid alert recipient was accepted")
except ValueError:
    pass
assert len(calls) == 1

guard_outputs = {"GuardScheduleName": "retro-coop-cost-guard-6h",
                 "GuardFunctionArn": "arn:guard", "GuardAlertTopicArn": "arn:alerts",
                 "ExpectedAlbParameterName": "/retro-coop/website/expected-alb-dns"}
notifications = [{"NotificationType": mode, "ComparisonOperator": "GREATER_THAN",
                  "Threshold": threshold, "ThresholdType": "PERCENTAGE"}
                 for mode, threshold in (("ACTUAL", 50), ("ACTUAL", 100), ("FORECASTED", 100))]
state = {"confirmed": True, "scheduleDryRun": False, "alb": "UNCONFIGURED", "invocations": 0,
         "result": {"dryRun": True, "wouldStop": False, "actions": [],
                    "actualUsd": "40", "forecastUsd": "80"}}


def guard_aws(*args):
    key = args[:2]
    if key == ("budgets", "describe-budget"):
        return {"Budget": {"BudgetType": "COST", "TimeUnit": "MONTHLY",
                           "BudgetLimit": {"Unit": "USD", "Amount": "100"}}}
    if key == ("budgets", "describe-notifications-for-budget"):
        return {"Notifications": notifications}
    if key == ("budgets", "describe-subscribers-for-notification"):
        return {"Subscribers": [{"SubscriptionType": "EMAIL", "Address": "bill@example.test"}]}
    if key == ("scheduler", "get-schedule"):
        return {"State": "ENABLED", "ScheduleExpression": "rate(6 hours)",
                "Target": {"Arn": "arn:guard", "Input": json.dumps({"dryRun": state["scheduleDryRun"]})}}
    if key == ("sns", "list-subscriptions-by-topic"):
        return {"Subscriptions": [{"Endpoint": "bill@example.test", "Protocol": "email",
                                   "SubscriptionArn": "arn:subscription" if state["confirmed"] else "PendingConfirmation"}]}
    if key == ("cloudwatch", "describe-alarms"):
        return {"MetricAlarms": [{"ActionsEnabled": True, "AlarmActions": ["arn:alerts"],
                                  "Namespace": "AWS/Lambda", "MetricName": "Errors",
                                  "Dimensions": [{"Name": "FunctionName", "Value": "retro-coop-cost-guard"}],
                                  "ComparisonOperator": "GreaterThanThreshold", "Threshold": 0}]}
    if key == ("ssm", "get-parameter"):
        return {"Parameter": {"Value": state["alb"]}}
    if key == ("lambda", "invoke"):
        state["invocations"] += 1
        Path(args[-1]).write_text(json.dumps(state["result"]))
        return {"StatusCode": 200}
    raise AssertionError(f"Unexpected AWS read: {args}")


def guard_command(*args):
    if args[:2] != ("ssm", "put-parameter"):
        raise AssertionError(f"Unexpected AWS change: {args}")
    state["alb"] = args[args.index("--value") + 1]


website.aws = guard_aws
website.command = guard_command
website.stack_parameters = lambda: {"AlertEmail": "bill@example.test"}
assert website.verify_guard(guard_outputs, "retro-alb.example") == state["result"]
assert state["alb"] == "retro-alb.example" and state["invocations"] == 1
state["confirmed"] = False
try:
    website.verify_guard(guard_outputs, "retro-alb.example")
    raise AssertionError("Public DNS gate accepted an unconfirmed operator alert")
except ValueError:
    pass
assert state["invocations"] == 1
state["confirmed"] = True
state["scheduleDryRun"] = True
try:
    website.verify_guard(guard_outputs, "retro-alb.example")
    raise AssertionError("Public DNS gate accepted a schedule that only dry runs")
except ValueError:
    pass
assert state["invocations"] == 1
state["scheduleDryRun"] = False
state["result"] = {**state["result"], "wouldStop": True,
                   "actions": ["delete_exact_website_alias"], "forecastUsd": "100"}
try:
    website.verify_guard(guard_outputs, "retro-alb.example")
    raise AssertionError("Public DNS gate accepted a guard above the shutdown threshold")
except ValueError:
    pass
assert state["invocations"] == 2

website.identity = lambda: None
try:
    website.teardown(Namespace(confirm="another-site.example", hosted_zone_id="Z1", bucket=None))
    raise AssertionError("Teardown accepted a foreign hostname")
except ValueError:
    pass
try:
    website.teardown(Namespace(confirm=website.HOST, hosted_zone_id="Z1", bucket="foreign-bucket"))
    raise AssertionError("Teardown accepted a foreign storage bucket")
except ValueError:
    pass
print("EB operator source passed (single instance, exact groups and secret, guard DNS gate, teardown scope).")
