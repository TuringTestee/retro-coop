#!/usr/bin/env python3
"""Publish exact native ARM64 CI images from reviewed main without local Docker."""

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from package import ROOT


REGION = "us-east-1"
ACCOUNT = "599796577790"
REPO = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/retro-coop"
ARTIFACT = "aws-eb-arm64-images"
TARGETS = ("edge", "coordinator", "caddy", "turn")


def run(*args: str, input_text: str | None = None) -> str:
    return subprocess.run(args, cwd=ROOT, input=input_text, text=True, check=True, capture_output=True).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--crane", required=True, type=Path, help="Pinned crane v0.20.6 executable")
    args = parser.parse_args()
    if run("git", "branch", "--show-current") != "main" or run("git", "status", "--porcelain"):
        parser.error("Build from a clean main checkout")
    revision = run("git", "rev-parse", "HEAD")
    if revision != run("git", "rev-parse", "origin/main"):
        parser.error("Local main differs from origin/main")
    if "v0.20.6" not in run(str(args.crane), "version"):
        parser.error("Use the reviewed crane v0.20.6 binary")
    identity = json.loads(run("aws", "sts", "get-caller-identity", "--output", "json"))
    if identity.get("Account") != ACCOUNT:
        parser.error("AWS account does not match reviewed deployment")
    repository = json.loads(run("aws", "ecr", "describe-repositories", "--region", REGION,
                                "--repository-names", "retro-coop", "--output", "json"))["repositories"][0]
    if repository["repositoryUri"] != REPO or repository["imageTagMutability"] != "IMMUTABLE":
        parser.error("Expected the dedicated immutable ECR repository")
    runs = json.loads(run("gh", "run", "list", "--repo", "TuringTestee/retro-coop", "--commit", revision,
                          "--branch", "main", "--workflow", "CI", "--event", "push", "--status", "success",
                          "--json", "databaseId,headSha,conclusion,event", "--limit", "20"))
    candidates = [row for row in runs if row["headSha"] == revision and row["event"] == "push" and row["conclusion"] == "success"]
    if not candidates:
        parser.error("No successful native ARM64 CI run exists for this exact main commit")
    run_id = str(candidates[0]["databaseId"])
    password = run("aws", "ecr", "get-login-password", "--region", REGION)
    run(str(args.crane), "auth", "login", REPO.split("/")[0], "-u", "AWS", "--password-stdin", input_text=password)
    with tempfile.TemporaryDirectory(prefix="retro-eb-release-") as directory:
        temporary = Path(directory)
        run("gh", "run", "download", run_id, "--repo", "TuringTestee/retro-coop",
            "--name", ARTIFACT, "--dir", str(temporary))
        checksums = (temporary / "SHA256SUMS").read_text().splitlines()
        expected = {f"{target}.tar" for target in TARGETS}
        found = set()
        for line in checksums:
            digest, filename = line.split("  ", 1)
            if filename not in expected or filename in found or len(digest) != 64:
                parser.error("The native ARM64 artifact has an unexpected checksum manifest")
            found.add(filename)
            if hashlib.sha256((temporary / filename).read_bytes()).hexdigest() != digest:
                parser.error(f"CI image artifact {filename} differs from its checksum")
        if found != expected:
            parser.error("The native ARM64 artifact lacks one or more images")
        references = {}
        for target in TARGETS:
            tag = f"{REPO}:{target}-{revision}"
            existing = json.loads(run("aws", "ecr", "list-images", "--region", REGION,
                                      "--repository-name", "retro-coop", "--filter", "tagStatus=TAGGED", "--output", "json"))
            if not any(row.get("imageTag") == f"{target}-{revision}" for row in existing["imageIds"]):
                run(str(args.crane), "push", str(temporary / f"{target}.tar"), tag)
            config = json.loads(run(str(args.crane), "config", tag))
            if config.get("architecture") != "arm64" or config.get("os") != "linux":
                parser.error(f"Published {target} image is not native linux/arm64")
            digest = run(str(args.crane), "digest", tag)
            references[target] = f"{REPO}@{digest}"
        filesystem = temporary / "edge-filesystem.tar"
        run(str(args.crane), "export", references["edge"], str(filesystem))
        assets = {}
        core = []
        with tarfile.open(filesystem) as archive:
            for member in archive:
                path = member.name.removeprefix("./")
                prefix = "usr/share/nginx/html/"
                if not member.isfile() or not path.startswith(prefix):
                    continue
                relative = path.removeprefix(prefix)
                content = archive.extractfile(member).read()
                digest = hashlib.sha256(content).hexdigest()
                assets["/" + relative] = digest
                if relative.endswith(".wasm"):
                    core.append(digest)
        if len(core) != 1 or not assets:
            parser.error("The edge image must contain one versioned emulator WASM and static assets")
        manifest = temporary / "assets.json"
        manifest.write_text(json.dumps(assets, sort_keys=True))
        subprocess.run([sys.executable, str(ROOT / "scripts/aws_eb/package.py"),
                        "--edge-image", references["edge"], "--coordinator-image", references["coordinator"],
                        "--caddy-image", references["caddy"], "--turn-image", references["turn"],
                        "--source-revision", revision, "--core-sha256", core[0],
                        "--asset-manifest", str(manifest), "--output", str(args.output)], check=True)
        print(json.dumps({"sourceRevision": revision, "ciRunId": run_id,
                          "images": references, "bundle": str(args.output)}))


if __name__ == "__main__":
    main()
