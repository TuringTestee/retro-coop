#!/usr/bin/env python3
"""Check one-machine EB bundle and cloud boundary without making AWS changes."""

import argparse
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from package import ROOT, render


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--compose", type=Path)
args = parser.parse_args()
account = "1" * 12
image = f"{account}.dkr.ecr.us-east-1.amazonaws.com/retro-coop@sha256:"
edge, coordinator, caddy, turn = [image + token * 64 for token in "abcd"]
compose = render(edge, coordinator, caddy, turn)
assert all(value in compose for value in (edge, coordinator, caddy, turn))
for invalid in ["retro-coop:latest", "us-east-1.example/retro-coop@sha256:" + "a" * 64]:
    try:
        render(invalid, coordinator, caddy, turn)
        raise AssertionError("Mutable or foreign image was accepted")
    except ValueError:
        pass
try:
    render(edge.replace(account, "2" * 12), coordinator, caddy, turn)
    raise AssertionError("Images from different accounts were accepted")
except ValueError:
    pass
with tempfile.TemporaryDirectory(prefix="retro-eb-source-") as directory:
    temporary = Path(directory)
    manifest = temporary / "assets.json"
    manifest.write_text(json.dumps({"/assets/game-a.js": "c" * 64}))
    bundle = temporary / "release.zip"
    subprocess.run([sys.executable, str(ROOT / "scripts/aws_eb/package.py"),
                    "--edge-image", edge, "--coordinator-image", coordinator,
                    "--caddy-image", caddy, "--turn-image", turn,
                    "--source-revision", "d" * 40, "--asset-manifest", str(manifest),
                    "--core-sha256", "e" * 64, "--output", str(bundle)], check=True, capture_output=True)
    with zipfile.ZipFile(bundle) as archive:
        assert set(archive.namelist()) == {"docker-compose.yml", "release.json", ".ebextensions/01-environment.config"}
        record = json.loads(archive.read("release.json"))
        assert record["sourceRevision"] == "d" * 40 and record["coreSha256"] == "e" * 64
        assert all(record[name] in archive.read("docker-compose.yml").decode() for name in
                   ("edgeImage", "coordinatorImage", "caddyImage", "turnImage"))
        assert b"TURN_SECRET" in archive.read("docker-compose.yml")
        assert b"TURN_SECRET: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" not in archive.read("docker-compose.yml")
        assert b"ProxyServer: none" in archive.read(".ebextensions/01-environment.config")

nginx = (ROOT / "deploy/aws-eb/nginx.conf").read_text()
caddyfile = (ROOT / "deploy/aws-eb/Caddyfile").read_text()
turn_start = (ROOT / "scripts/aws_eb/run_turn.sh").read_text()
compose = args.compose.read_text() if args.compose else compose
foundation = (ROOT / "deploy/aws-eb/foundation.yaml").read_text()
assert "(?<last_peer_address>" in nginx and "X-Forwarded-For $admission_ip" in nginx
assert "proxy_pass http://127.0.0.1:8787" in nginx and "listen 127.0.0.1:8080" in nginx
assert "header_up X-Forwarded-For {remote_host}" in caddyfile and "reverse_proxy 127.0.0.1:8080" in caddyfile
assert "latest/meta-data/public-ipv4" in turn_start and "latest/meta-data/local-ipv4" in turn_start
assert "network_mode: host" in compose and "COORDINATOR_HOST: 127.0.0.1" in compose
assert "COORDINATOR_TRUSTED_PROXIES: 127.0.0.1" in compose
assert "COORDINATOR_ORIGINS: ${COORDINATOR_ORIGINS:?" in compose
assert "TURN_SECRET: ${TURN_SECRET:?" in compose and "retro_coop_caddy_data" in compose
assert "FromPort: 8787" not in foundation and "FromPort: 22" not in foundation
assert "AWS::EC2::Instance" not in foundation and "AWS::ElasticLoadBalancing" not in foundation
assert "FromPort: 443" in foundation and "FromPort: 3478" in foundation
assert "ScheduleExpression: rate(6 hours)" in foundation and "State: ENABLED" in foundation
assert "Handler: cost_guard.handler" in foundation and "GuardDeliveryAlarm:" in foundation
topic_policy = foundation.split("  GuardTopicPolicy:", 1)[1].split("Outputs:", 1)[0]
assert topic_policy.count("Sid: AllowAccountPublish") == 1
assert topic_policy.count("Sid: AllowCloudWatchPublish") == 1
print("EB source boundary passed (four immutable images, one ARM64 host, loopback web, Caddy peer, bounded TURN, scheduled guard, no SSH).")
