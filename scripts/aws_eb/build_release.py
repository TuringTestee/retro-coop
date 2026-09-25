#!/usr/bin/env python3
"""Build one clean main revision, push both images, and package their exact digests."""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from package import ROOT


REGION = "us-east-1"
ACCOUNT = "599796577790"
REPO = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/retro-coop"


def run(*args: str, input_text: str | None = None) -> str:
    return subprocess.run(args, cwd=ROOT, input=input_text, text=True, check=True, capture_output=True).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if run("git", "branch", "--show-current") != "main" or run("git", "status", "--porcelain"):
        parser.error("Build from a clean main checkout")
    revision = run("git", "rev-parse", "HEAD")
    if revision != run("git", "rev-parse", "origin/main"):
        parser.error("Local main differs from origin/main")
    identity = json.loads(run("aws", "sts", "get-caller-identity", "--output", "json"))
    if identity.get("Account") != ACCOUNT:
        parser.error("AWS account does not match reviewed deployment")
    repository = json.loads(run("aws", "ecr", "describe-repositories", "--region", REGION, "--repository-names", "retro-coop", "--output", "json"))["repositories"][0]
    if repository["repositoryUri"] != REPO or repository["imageTagMutability"] != "IMMUTABLE":
        parser.error("Expected the dedicated immutable ECR repository")
    password = run("aws", "ecr", "get-login-password", "--region", REGION)
    subprocess.run(["docker", "login", "--username", "AWS", "--password-stdin", REPO.split("/")[0]], input=password, text=True, check=True, stdout=subprocess.DEVNULL)
    references = {}
    for target in ("edge", "coordinator"):
        tag = f"{REPO}:{target}-{revision}"
        subprocess.run(["docker", "build", "--file", "deploy/aws-eb/Dockerfile", "--target", target, "--tag", tag, "."], cwd=ROOT, check=True)
        subprocess.run(["docker", "push", tag], cwd=ROOT, check=True)
        record = json.loads(run("aws", "ecr", "describe-images", "--region", REGION, "--repository-name", "retro-coop", "--image-ids", f"imageTag={target}-{revision}", "--output", "json"))["imageDetails"][0]
        references[target] = f"{REPO}@{record['imageDigest']}"
    with tempfile.TemporaryDirectory(prefix="retro-eb-release-") as directory:
        temporary = Path(directory)
        container = run("docker", "create", references["edge"])
        try:
            subprocess.run(["docker", "cp", f"{container}:/usr/share/nginx/html", str(temporary / "html")], check=True)
        finally:
            subprocess.run(["docker", "rm", "-f", container], check=True, stdout=subprocess.DEVNULL)
        static = temporary / "html"
        assets = {"/" + str(path.relative_to(static)): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in static.rglob("*") if path.is_file()}
        core = [path for path in static.rglob("*.wasm") if path.is_file()]
        if len(core) != 1 or not assets:
            parser.error("The edge image must contain one versioned emulator WASM and static assets")
        manifest = temporary / "assets.json"
        manifest.write_text(json.dumps(assets, sort_keys=True))
        subprocess.run([sys.executable, str(ROOT / "scripts/aws_eb/package.py"),
                        "--edge-image", references["edge"], "--coordinator-image", references["coordinator"],
                        "--source-revision", revision, "--core-sha256", hashlib.sha256(core[0].read_bytes()).hexdigest(),
                        "--asset-manifest", str(manifest), "--output", str(args.output)], check=True)


if __name__ == "__main__":
    main()
