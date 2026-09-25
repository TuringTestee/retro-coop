#!/usr/bin/env python3
"""Prove the scheduled guard's monthly threshold and exact-resource shutdown logic."""

from cost_guard import ACCOUNT, APP, BUDGET, ENV, HOST, GuardError, evaluate


CONFIG = {"account": ACCOUNT, "hostname": HOST, "zoneId": "ZTEST",
          "relayInstanceId": "i-0123456789abcdef0",
          "expectedAlbParameter": "/retro-coop/website/expected-alb-dns"}
ALB = "retro-coop-alb.us-east-1.elb.amazonaws.com"
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
    def get_parameter(self, **kwargs):
        assert kwargs["Name"] == CONFIG["expectedAlbParameter"]
        return {"Parameter": {"Value": ALB}}


class Route:
    def __init__(self, dns=ALB):
        self.dns = dns
        self.changes = []

    def list_resource_record_sets(self, **kwargs):
        assert kwargs["HostedZoneId"] == "ZTEST"
        if not self.dns:
            return {"ResourceRecordSets": []}
        record = {"Name": HOST + ".", "Type": "A", "AliasTarget": {"DNSName": self.dns + ".", "HostedZoneId": "ZALB", "EvaluateTargetHealth": True}}
        return {"ResourceRecordSets": [record]}

    def change_resource_record_sets(self, **kwargs):
        self.changes.append(kwargs)


class Beanstalk:
    def __init__(self, status="Ready"):
        self.status = status
        self.terminated = []

    def describe_environments(self, **kwargs):
        assert kwargs["ApplicationName"] == APP and kwargs["EnvironmentNames"] == [ENV]
        return {"Environments": [{"EnvironmentArn": ARN, "Status": self.status}] if self.status else []}

    def terminate_environment(self, **kwargs):
        self.terminated.append(kwargs)


class Relay:
    def __init__(self, state="running", tags=None):
        self.state = state
        self.tags = tags if tags is not None else [{"Key": "Project", "Value": "retro-coop"}]
        self.terminated = []

    def describe_instances(self, **kwargs):
        assert kwargs["InstanceIds"] == [CONFIG["relayInstanceId"]]
        return {"Reservations": [{"Instances": [{"InstanceId": CONFIG["relayInstanceId"],
                                               "State": {"Name": self.state}, "Tags": self.tags}]}]}

    def terminate_instances(self, **kwargs):
        self.terminated.append(kwargs)


def clients(actual="40", forecast="80", dns=ALB, status="Ready", relay_state="running"):
    return {"budgets": Budget(actual, forecast), "ssm": Parameter(), "route53": Route(dns),
            "eb": Beanstalk(status), "ec2": Relay(relay_state)}


healthy = clients()
result = evaluate({"dryRun": False}, healthy, CONFIG)
assert not result["wouldStop"] and result["actions"] == []
assert not healthy["route53"].changes and not healthy["eb"].terminated and not healthy["ec2"].terminated

forecast = clients(forecast="100.01")
result = evaluate({"dryRun": True}, forecast, CONFIG)
assert result["wouldStop"] and result["actions"] == ["delete_exact_website_alias", "terminate_named_eb_environment", "terminate_named_relay"]
assert not forecast["route53"].changes and not forecast["eb"].terminated and not forecast["ec2"].terminated

live = clients(actual="100", forecast="101")
result = evaluate({"dryRun": False}, live, CONFIG)
assert result["wouldStop"] and len(live["route53"].changes) == 1
assert live["route53"].changes[0]["ChangeBatch"]["Changes"][0]["Action"] == "DELETE"
assert live["eb"].terminated == [{"ApplicationName": APP, "EnvironmentName": ENV}]
assert live["ec2"].terminated == [{"InstanceIds": [CONFIG["relayInstanceId"]]}]

stopped = clients(actual="100", forecast="101", dns=None, status=None, relay_state="terminated")
assert evaluate({"dryRun": False}, stopped, CONFIG)["actions"] == []
assert not stopped["route53"].changes and not stopped["eb"].terminated and not stopped["ec2"].terminated

for broken in [clients(actual="1", forecast=None), clients(actual="100", forecast="101", dns="another.elb.amazonaws.com")]:
    try:
        evaluate({"dryRun": False}, broken, CONFIG)
        raise AssertionError("Missing forecast or wrong DNS target was accepted")
    except GuardError:
        pass
    assert not broken["route53"].changes and not broken["eb"].terminated and not broken["ec2"].terminated

wrong_relay = clients(actual="100", forecast="101")
wrong_relay["ec2"].tags = [{"Key": "Project", "Value": "another-project"}]
try:
    evaluate({"dryRun": False}, wrong_relay, CONFIG)
    raise AssertionError("Foreign relay was accepted")
except GuardError:
    pass
assert not wrong_relay["route53"].changes
print("Cost guard passed (monthly actual/forecast, dry run, exact shutdown, idempotence, missing data and wrong resources).")
