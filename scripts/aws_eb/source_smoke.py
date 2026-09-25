#!/usr/bin/env python3
"""Check the release bundle and cloud boundary without making AWS changes."""

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
image = "599796577790.dkr.ecr.us-east-1.amazonaws.com/retro-coop@sha256:"
edge, coordinator = image + "a" * 64, image + "b" * 64
assert edge in render(edge, coordinator) and coordinator in render(edge, coordinator)
for invalid in ["retro-coop:latest", "us-east-1.example/retro-coop@sha256:" + "a" * 64]:
    try:
        render(invalid, coordinator)
        raise AssertionError("Mutable or foreign image was accepted")
    except ValueError:
        pass
with tempfile.TemporaryDirectory(prefix="retro-eb-source-") as directory:
    temporary = Path(directory)
    manifest = temporary / "assets.json"
    manifest.write_text(json.dumps({"/assets/game-a.js": "c" * 64}))
    bundle = temporary / "release.zip"
    subprocess.run([sys.executable, str(ROOT / "scripts/aws_eb/package.py"),
                    "--edge-image", edge, "--coordinator-image", coordinator,
                    "--source-revision", "d" * 40, "--asset-manifest", str(manifest),
                    "--core-sha256", "e" * 64, "--output", str(bundle)], check=True, capture_output=True)
    with zipfile.ZipFile(bundle) as archive:
        assert set(archive.namelist()) == {"docker-compose.yml", "release.json", ".ebextensions/01-environment.config", ".ebextensions/02-http-redirect.config"}
        record = json.loads(archive.read("release.json"))
        assert record["sourceRevision"] == "d" * 40 and record["coreSha256"] == "e" * 64
        assert b"TURN_SECRET" in archive.read("docker-compose.yml")
        assert b"TURN_SECRET: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" not in archive.read("docker-compose.yml")
        assert edge.encode() in archive.read("docker-compose.yml")
        assert b"HealthCheckPath: /healthz" in archive.read(".ebextensions/01-environment.config")
        assert b"StatusCode: HTTP_301" in archive.read(".ebextensions/02-http-redirect.config")

nginx = (ROOT / "deploy/aws-eb/nginx.conf").read_text()
compose = args.compose.read_text() if args.compose else render(edge, coordinator)
foundation = (ROOT / "deploy/aws-eb/foundation.yaml").read_text()
assert "(?<last_alb_address>" in nginx and "X-Forwarded-For $admission_ip" in nginx
assert "proxy_pass http://127.0.0.1:8787" in nginx and "listen 8080" in nginx
assert "network_mode: host" in compose and "COORDINATOR_HOST: 127.0.0.1" in compose
assert "COORDINATOR_TRUSTED_PROXIES: 127.0.0.1" in compose
assert "COORDINATOR_ORIGINS: ${COORDINATOR_ORIGINS:?" in compose
assert "TURN_SECRET: ${TURN_SECRET:?" in compose
assert "SourceSecurityGroupId: !Ref AlbSecurityGroup" in foundation
assert "FromPort: 8787" not in foundation and "FromPort: 22" not in foundation
assert "SecretsManager::Secret" in foundation and "HttpTokens: required" in foundation
assert "ScheduleExpression: rate(6 hours)" in foundation and "State: ENABLED" in foundation
assert "Handler: cost_guard.handler" in foundation and "GuardErrorAlarm:" in foundation
print("EB source boundary passed (immutable bundle, same-host loopback, final ALB address, scoped ingress, managed secret, scheduled guard, no SSH).")
