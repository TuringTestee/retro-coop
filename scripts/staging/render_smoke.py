#!/usr/bin/env python3
"""Check that a staging render is pinned, isolated, and source restricted."""

import subprocess
import sys
from pathlib import Path
import re

render = Path(__file__).with_name("render_k8s.py")
base = [
    sys.executable, str(render),
    "--public-ip", "34.100.1.2",
    "--edge-image", "us-central1-docker.pkg.dev/sample/retro-coop-staging/edge@sha256:" + "a" * 64,
    "--coordinator-image", "us-central1-docker.pkg.dev/sample/retro-coop-staging/coordinator@sha256:" + "b" * 64,
]
manifest = subprocess.check_output([*base, "--allow", "8.8.8.8/32"], text=True)
documents = manifest.split("\n---\n")
for document in documents:
    kind = re.search(r"^kind: (\S+)$", document, re.MULTILINE)
    if kind is None:
        raise AssertionError("Rendered object has no kind")
    if kind.group(1) != "Namespace" and not re.search(
        r"^  namespace: retro-coop-staging$", document, re.MULTILINE
    ):
        raise AssertionError(f"Rendered {kind.group(1)} escaped the staging namespace")
if len(documents) != 5:
    raise AssertionError("Unexpected staging resource count")
for expected in [
    "kind: Namespace",
    "name: retro-coop-staging",
    "services.loadbalancers: \"1\"",
    "loadBalancerClass: networking.gke.io/l4-regional-external",
    "externalTrafficPolicy: Local",
    "loadBalancerIP: 34.100.1.2",
    "- 8.8.8.8/32",
    "COORDINATOR_ORIGINS: https://34.100.1.2",
    "automountServiceAccountToken: false",
    "kind: Job",
    "activeDeadlineSeconds: 21600",
    "backoffLimit: 0",
    "restartPolicy: Never",
    "ttlSecondsAfterFinished: 3600",
    "edge@sha256:" + "a" * 64,
    "coordinator@sha256:" + "b" * 64,
    "secretName: retro-coop-staging-tls",
    "name: retro-coop-staging-turn",
    "runAsUser: 101",
    "runAsGroup: 101",
    "runAsUser: 1000",
    "runAsGroup: 1000",
]:
    if expected not in manifest:
        raise AssertionError(f"Staging render omitted {expected}")
if "192.0.2.1" in manifest or "image: retro-coop-staging-edge\n" in manifest:
    raise AssertionError("Staging render retained a placeholder")

for arguments in [
    ["--allow", "0.0.0.0/0"],
    ["--allow", "8.8.8.8/32", "--acme-bootstrap"],
    ["--allow", "192.0.2.1/32"],
    ["--allow", "8.8.8.0/24"],
    ["--allow", "8.8.8.8/32", "--allow", "1.1.1.1/32", "--allow", "9.9.9.9/32"],
]:
    result = subprocess.run([*base, *arguments], capture_output=True, text=True)
    if result.returncode == 0:
        raise AssertionError(f"Unsafe source range was accepted: {arguments}")
open_manifest = subprocess.check_output(
    [*base, "--allow", "0.0.0.0/0", "--acme-bootstrap"], text=True
)
if "- 0.0.0.0/0" not in open_manifest:
    raise AssertionError("Explicit ACME bootstrap did not render")
if "port: 443" in open_manifest or "port: 443" not in manifest:
    raise AssertionError("ACME bootstrap exposed HTTPS or normal staging omitted it")
print("Staging render passed (pinned images, origin, source range, quota and secrets).")
