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
assert settings["aws:elasticbeanstalk:healthreporting:system", "SystemType"] == "basic"
assert settings["aws:autoscaling:asg", "MinSize"] == "1"
assert settings["aws:autoscaling:asg", "MaxSize"] == "1"
assert settings["aws:autoscaling:launchconfiguration", "InstanceType"] == "t4g.micro"
assert settings["aws:autoscaling:launchconfiguration", "DisableIMDSv1"] == "true"
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

website.instance_and_eip = lambda _outputs, _resources: ("i-reviewed", ip)
load_state = {"availableKiB": 200000, "includeProof": True, "commands": []}


def instance_aws(*args):
    if args[:2] == ("ssm", "send-command"):
        load_state["commands"] = json.loads(args[-1])["commands"]
        return {"Command": {"CommandId": "cmd-1"}}
    if args[:2] == ("ssm", "get-command-invocation"):
        listeners = "127.0.0.1:8787\n127.0.0.1:8080\n0.0.0.0:80\n0.0.0.0:443\n10.0.0.5:3478\n"
        names = "retro-coop-coordinator\nretro-coop-edge\nretro-coop-caddy\nretro-coop-turn\n"
        proof = "MEMORY_PROOF:" + json.dumps({"rooms": 20, "romBytes": 20 * (16 + 16384),
                                                "availableKiB": load_state["availableKiB"]}) + "\n"
        output = listeners + names + (proof if load_state["includeProof"] else "AvailableKiB:200000\n")
        return {"Status": "Success", "StandardOutputContent": output}
    raise AssertionError(f"Unexpected live boundary read: {args}")


website.aws = instance_aws
assert website.verify_live_boundary({}, {}, load_test=True) == ip
assert any("memory_probe.mjs" in command and "docker restart" in command for command in load_state["commands"])
load_state["availableKiB"] = 120000
try:
    website.verify_live_boundary({}, {}, load_test=True)
    raise AssertionError("Public DNS gate accepted insufficient loaded memory headroom")
except ValueError:
    pass
load_state["includeProof"] = False
assert website.verify_live_boundary({}, {}, load_test=False) == ip
assert all("memory_probe.mjs" not in command for command in load_state["commands"])

website.identity = lambda: None
for args in (Namespace(confirm="another-site.example", hosted_zone_id="Z1", bucket=None),
             Namespace(confirm=website.HOST, hosted_zone_id="Z1", bucket="foreign-bucket")):
    try:
        website.teardown(args)
        raise AssertionError("Teardown accepted a foreign hostname or bucket")
    except ValueError:
        pass
print("EB operator source passed (single ARM micro, exact public ports, managed TURN, guard DNS gate, teardown scope).")
