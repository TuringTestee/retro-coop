#!/usr/bin/env python3
"""Prove monthly threshold and exact one-machine shutdown without AWS calls."""

import os

os.environ["ACCOUNT_ID"] = "1" * 12

from cost_guard import ACCOUNT, APP, BUDGET, ENV, HOST, GuardError, evaluate


CONFIG = {"account": ACCOUNT, "hostname": HOST, "zoneId": "ZTEST",
          "expectedIpParameter": "/retro-coop/website/expected-ip"}
IP = "54.1.2.3"
ARN = f"arn:aws:elasticbeanstalk:us-east-1:{ACCOUNT}:environment/{APP}/{ENV}"


class Budget:
    def __init__(self, actual="40", forecast="80"):
        self.actual, self.forecast = actual, forecast

    def describe_budget(self, **kwargs):
        assert kwargs == {"AccountId": ACCOUNT, "BudgetName": BUDGET}
        spend = {"ActualSpend": {"Amount": self.actual, "Unit": "USD"}}
        if self.forecast is not None:
            spend["ForecastedSpend"] = {"Amount": self.forecast, "Unit": "USD"}
        return {"Budget": {"BudgetName": BUDGET, "BudgetType": "COST", "TimeUnit": "MONTHLY",
                           "BudgetLimit": {"Amount": "100", "Unit": "USD"}, "CalculatedSpend": spend}}


class Parameter:
    def __init__(self, value=IP):
        self.value = value

    def get_parameter(self, **kwargs):
        assert kwargs["Name"] == CONFIG["expectedIpParameter"]
        return {"Parameter": {"Value": self.value}}


class Route:
    def __init__(self, ip=IP):
        self.ip = ip
        self.changes = []

    def list_resource_record_sets(self, **kwargs):
        assert kwargs["HostedZoneId"] == "ZTEST"
        if not self.ip:
            return {"ResourceRecordSets": []}
        return {"ResourceRecordSets": [{"Name": HOST + ".", "Type": "A", "TTL": 60,
                                        "ResourceRecords": [{"Value": self.ip}]}]}

    def change_resource_record_sets(self, **kwargs):
        self.changes.append(kwargs)


class Beanstalk:
    def __init__(self, status="Ready", arn=ARN):
        self.status, self.arn = status, arn
        self.terminated = []

    def describe_environments(self, **kwargs):
        assert kwargs["ApplicationName"] == APP and kwargs["EnvironmentNames"] == [ENV]
        return {"Environments": [{"EnvironmentArn": self.arn, "Status": self.status}] if self.status else []}

    def terminate_environment(self, **kwargs):
        self.terminated.append(kwargs)


def clients(actual="40", forecast="80", ip=IP, status="Ready", expected=IP):
    return {"budgets": Budget(actual, forecast), "ssm": Parameter(expected), "route53": Route(ip),
            "eb": Beanstalk(status)}


healthy = clients()
assert evaluate({}, healthy, CONFIG)["actions"] == []
assert not healthy["route53"].changes and not healthy["eb"].terminated

forecast = clients(forecast="100.01")
result = evaluate({"dryRun": True}, forecast, CONFIG)
assert result["wouldStop"] and result["actions"] == ["delete_exact_website_a_record", "terminate_named_eb_environment_and_instance"]
assert not forecast["route53"].changes and not forecast["eb"].terminated

live = clients(actual="100", forecast="101")
assert evaluate({}, live, CONFIG)["wouldStop"]
assert live["route53"].changes[0]["ChangeBatch"]["Changes"][0]["Action"] == "DELETE"
assert live["eb"].terminated == [{"ApplicationName": APP, "EnvironmentName": ENV}]

stopped = clients(actual="100", forecast="101", ip=None, status=None)
assert evaluate({}, stopped, CONFIG)["actions"] == []
assert not stopped["route53"].changes and not stopped["eb"].terminated

unpublished = clients(actual="100", forecast="101", ip=None, expected="UNCONFIGURED")
assert evaluate({}, unpublished, CONFIG)["actions"] == ["terminate_named_eb_environment_and_instance"]
assert not unpublished["route53"].changes and len(unpublished["eb"].terminated) == 1

for broken in [clients(actual="1", forecast=None), clients(actual="100", forecast="101", ip="54.9.8.7")]:
    try:
        evaluate({}, broken, CONFIG)
        raise AssertionError("Missing forecast or wrong DNS target was accepted")
    except GuardError:
        pass
    assert not broken["route53"].changes and not broken["eb"].terminated

foreign = clients(actual="100", forecast="101")
foreign["eb"].arn = "arn:aws:elasticbeanstalk:us-east-1:111111111111:environment/another/foreign"
try:
    evaluate({}, foreign, CONFIG)
    raise AssertionError("Foreign EB environment was accepted")
except GuardError:
    pass
assert not foreign["route53"].changes and not foreign["eb"].terminated
print("Cost guard passed (monthly actual/forecast, dry run, exact A record, one-machine shutdown, idempotence and wrong resources).")
