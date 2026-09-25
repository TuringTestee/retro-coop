#!/usr/bin/env python3
"""Exercise the EB operator's scoping and failure gates without contacting AWS."""

from argparse import Namespace

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

website.identity = lambda: None
try:
    website.teardown(Namespace(confirm="another-site.example", hosted_zone_id="Z1"))
    raise AssertionError("Teardown accepted a foreign hostname")
except ValueError:
    pass
assert len(calls) == 1
print("EB operator source passed (single instance, exact groups and secret, alert recipient, teardown scope).")
