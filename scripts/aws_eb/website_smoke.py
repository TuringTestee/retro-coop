#!/usr/bin/env python3
"""Exercise the one-machine EB operator's scoping and public DNS gates without AWS."""

from argparse import Namespace
import json
from pathlib import Path

import website


outputs = {"EbProfileName": "retro-eb-profile", "AppSecurityGroupId": "sg-app",
           "TurnSecretArn": "arn:turn-secret"}
settings = {(row["Namespace"], row["OptionName"]): row["Value"] for row in website.options(
    outputs, Namespace(service_role="retro-eb-service", vpc_id="vpc-1", subnet="subnet-a"))}
assert settings["aws:elasticbeanstalk:environment", "EnvironmentType"] == "SingleInstance"
assert settings["aws:autoscaling:asg", "MinSize"] == "1"
assert settings["aws:autoscaling:asg", "MaxSize"] == "1"
assert settings["aws:autoscaling:launchconfiguration", "InstanceType"] == "t4g.micro"
assert settings["aws:autoscaling:launchconfiguration", "SecurityGroups"] == "sg-app"
assert settings["aws:elasticbeanstalk:application:environmentsecrets", "TURN_SECRET"] == "arn:turn-secret"
assert settings["aws:elasticbeanstalk:application:environment", "COORDINATOR_ORIGINS"] == "https://retro-coop.1001.page"
assert settings["aws:elasticbeanstalk:application:environment", "TURN_URLS"] == "turn:retro-coop.1001.page:3478?transport=udp"
assert "8787" not in str(settings) and "LoadBalancer" not in str(settings)

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

ip = "54.1.2.3"
record = website.a_record(ip)
assert website.address(record) == ip
try:
    website.address({"Name": website.HOST + ".", "Type": "A", "AliasTarget": {"DNSName": "foreign"}})
    raise AssertionError("Foreign DNS alias was accepted")
except ValueError:
    pass

settings_guard = {"GuardScheduleName": "retro-coop-cost-guard-6h", "GuardScheduleGroupName": "retro-coop-cost-guard",
                  "GuardFunctionArn": "arn:guard", "GuardAlertTopicArn": "arn:alerts",
                  "ExpectedIpParameterName": "/retro-coop/website/expected-ip"}
notifications = [{"NotificationType": mode, "ComparisonOperator": "GREATER_THAN",
                  "Threshold": threshold, "ThresholdType": "PERCENTAGE"}
                 for mode, threshold in (("ACTUAL", 50), ("ACTUAL", 100), ("FORECASTED", 100))]
state = {"confirmed": True, "scheduleDryRun": False, "ip": "UNCONFIGURED", "invocations": 0,
         "result": {"dryRun": True, "wouldStop": False, "actions": [],
                    "actualUsd": "40", "forecastUsd": "80"}, "brokenAlarm": None}


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
        assert args[-2:] == ("--group-name", "retro-coop-cost-guard")
        return {"State": "ENABLED", "ScheduleExpression": "rate(6 hours)",
                "Target": {"Arn": "arn:guard", "Input": json.dumps({"dryRun": state["scheduleDryRun"]})}}
    if key == ("sns", "list-subscriptions-by-topic"):
        return {"Subscriptions": [{"Endpoint": "bill@example.test", "Protocol": "email",
                                   "SubscriptionArn": "arn:subscription" if state["confirmed"] else "PendingConfirmation"}]}
    if key == ("cloudwatch", "describe-alarms"):
        name = args[-1]
        metrics = {"retro-coop-cost-guard-errors": ("AWS/Lambda", "Errors", "FunctionName"),
                   "retro-coop-cost-guard-delivery-errors": ("AWS/Scheduler", "TargetErrorCount", "ScheduleGroup"),
                   "retro-coop-cost-guard-dropped-invocations": ("AWS/Scheduler", "InvocationDroppedCount", "ScheduleGroup")}
        namespace, metric, dimension = metrics[name]
        if name == state["brokenAlarm"]:
            metric = "WrongMetric"
        return {"MetricAlarms": [{"ActionsEnabled": True, "AlarmActions": ["arn:alerts"],
                                  "Namespace": namespace, "MetricName": metric,
                                  "Dimensions": [{"Name": dimension, "Value": "retro-coop-cost-guard"}],
                                  "ComparisonOperator": "GreaterThanThreshold", "Threshold": 0}]}
    if key == ("ssm", "get-parameter"):
        return {"Parameter": {"Value": state["ip"]}}
    if key == ("lambda", "invoke"):
        state["invocations"] += 1
        Path(args[-1]).write_text(json.dumps(state["result"]))
        return {"StatusCode": 200}
    raise AssertionError(f"Unexpected AWS read: {args}")


def guard_command(*args):
    if args[:2] != ("ssm", "put-parameter"):
        raise AssertionError(f"Unexpected AWS change: {args}")
    state["ip"] = args[args.index("--value") + 1]


website.aws = guard_aws
website.command = guard_command
website.stack_parameters = lambda: {"AlertEmail": "bill@example.test"}
result, previous = website.verify_guard(settings_guard, ip, None)
assert result == state["result"] and previous == "UNCONFIGURED"
assert state["ip"] == ip and state["invocations"] == 1
state["confirmed"] = False
try:
    website.verify_guard(settings_guard, ip, ip)
    raise AssertionError("Public DNS gate accepted unconfirmed alert subscription")
except ValueError:
    pass
assert state["invocations"] == 1
state["confirmed"] = True
state["scheduleDryRun"] = True
try:
    website.verify_guard(settings_guard, ip, ip)
    raise AssertionError("Public DNS gate accepted a schedule that only dry runs")
except ValueError:
    pass
assert state["invocations"] == 1
state["scheduleDryRun"] = False
state["brokenAlarm"] = "retro-coop-cost-guard-delivery-errors"
try:
    website.verify_guard(settings_guard, ip, ip)
    raise AssertionError("Public DNS gate accepted a broken Scheduler delivery alarm")
except ValueError:
    pass
assert state["invocations"] == 1
state["brokenAlarm"] = None
state["result"] = {**state["result"], "wouldStop": True,
                   "actions": ["delete_exact_website_a_record"], "forecastUsd": "100"}
try:
    website.verify_guard(settings_guard, ip, ip)
    raise AssertionError("Public DNS gate accepted a guard above shutdown threshold")
except ValueError:
    pass
assert state["invocations"] == 2

website.identity = lambda: None
for args in (Namespace(confirm="another-site.example", hosted_zone_id="Z1", bucket=None),
             Namespace(confirm=website.HOST, hosted_zone_id="Z1", bucket="foreign-bucket")):
    try:
        website.teardown(args)
        raise AssertionError("Teardown accepted a foreign hostname or bucket")
    except ValueError:
        pass
print("EB operator source passed (single ARM micro, exact public ports, managed TURN, guard DNS gate, teardown scope).")
