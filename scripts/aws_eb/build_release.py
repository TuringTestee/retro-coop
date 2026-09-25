#!/usr/bin/env python3
"""Publish exact native ARM64 CI images from reviewed main without local Docker."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from package import ROOT


REGION = os.environ.get("AWS_REGION", "us-east-1")
REPOSITORY = "retro-coop"
ARTIFACT = "aws-eb-arm64-images"
TARGETS = ("edge", "coordinator", "caddy", "turn")


def run(*args: str, input_text: str | None = None) -> str:
    return subprocess.run(args, cwd=ROOT, input=input_text, text=True, check=True, capture_output=True).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--crane", required=True, type=Path, help="Pinned crane v0.20.6 executable")
    parser.add_argument("--ci-run-id", type=int, help="Exact successful main CI run that supplied the image artifact")
    parser.add_argument("--artifact-dir", type=Path, help="Checked image artifact from this main workflow run")
    args = parser.parse_args()
    if args.ci_run_id and args.artifact_dir:
        parser.error("Choose a prior CI run or this run's downloaded artifact")
    changes = run("git", "status", "--porcelain", "--untracked-files=no") if args.artifact_dir else \
        run("git", "status", "--porcelain")
    if run("git", "branch", "--show-current") != "main" or changes:
        parser.error("Build from a clean main checkout")
    revision = run("git", "rev-parse", "HEAD")
    if revision != run("git", "rev-parse", "origin/main"):
        parser.error("Local main differs from origin/main")
    if run(str(args.crane), "version") not in ("v0.20.6", "0.20.6"):
        parser.error("Use the reviewed crane v0.20.6 binary")
    identity = json.loads(run("aws", "sts", "get-caller-identity", "--output", "json"))
    account = identity.get("Account", "")
    if not re.fullmatch(r"[0-9]{12}", account):
        parser.error("AWS did not return a valid account identity")
    repository_uri = f"{account}.dkr.ecr.{REGION}.amazonaws.com/{REPOSITORY}"
    repository = json.loads(run("aws", "ecr", "describe-repositories", "--region", REGION,
                                "--repository-names", REPOSITORY, "--output", "json"))["repositories"][0]
    if repository["repositoryUri"] != repository_uri or repository["imageTagMutability"] != "IMMUTABLE":
        parser.error("Expected the dedicated immutable ECR repository")
    if args.artifact_dir:
        if os.environ.get("GITHUB_EVENT_NAME") != "push" or os.environ.get("GITHUB_REF") != "refs/heads/main" or \
                os.environ.get("GITHUB_SHA") != revision or not os.environ.get("GITHUB_RUN_ID"):
            parser.error("The artifact directory must belong to this exact main push")
        run_id = os.environ["GITHUB_RUN_ID"]
    elif args.ci_run_id:
        inspected = json.loads(run("gh", "run", "view", str(args.ci_run_id), "--repo", "TuringTestee/retro-coop",
                                   "--json", "databaseId,headSha,headBranch,conclusion,event,workflowName"))
        candidates = [inspected]
    else:
        candidates = json.loads(run("gh", "run", "list", "--repo", "TuringTestee/retro-coop", "--commit", revision,
                                    "--branch", "main", "--workflow", "CI", "--event", "push", "--status", "success",
                                    "--json", "databaseId,headSha,headBranch,conclusion,event,workflowName", "--limit", "20"))
    if not args.artifact_dir:
        candidates = [row for row in candidates if row["headSha"] == revision and row["headBranch"] == "main" and
                      row["workflowName"] == "CI" and row["event"] == "push" and row["conclusion"] == "success"]
        if len(candidates) != 1 and args.ci_run_id:
            parser.error("The selected CI run is not a successful push to this exact main commit")
        if not candidates:
            parser.error("No successful native ARM64 CI run exists for this exact main commit")
        run_id = str(candidates[0]["databaseId"])
    with tempfile.TemporaryDirectory(prefix="retro-eb-release-") as directory:
        temporary = Path(directory)
        # Keep the short-lived ECR token out of the operator's normal Docker config.
        docker_config = temporary / "docker-config"
        docker_config.mkdir(mode=0o700)
        os.environ["DOCKER_CONFIG"] = str(docker_config)
        password = run("aws", "ecr", "get-login-password", "--region", REGION)
        run(str(args.crane), "auth", "login", repository_uri.split("/")[0], "-u", "AWS", "--password-stdin", input_text=password)
        if not args.artifact_dir:
            run("gh", "run", "download", run_id, "--repo", "TuringTestee/retro-coop",
                "--name", ARTIFACT, "--dir", str(temporary))
        images_dir = args.artifact_dir or temporary
        checksums = (images_dir / "SHA256SUMS").read_text().splitlines()
        expected = {f"{target}.tar" for target in TARGETS}
        found = set()
        for line in checksums:
            digest, filename = line.split("  ", 1)
            if filename not in expected or filename in found or len(digest) != 64:
                parser.error("The native ARM64 artifact has an unexpected checksum manifest")
            found.add(filename)
            hasher = hashlib.sha256()
            with (images_dir / filename).open("rb") as image:
                for chunk in iter(lambda: image.read(1024 * 1024), b""):
                    hasher.update(chunk)
            if hasher.hexdigest() != digest:
                parser.error(f"CI image artifact {filename} differs from its checksum")
        if found != expected:
            parser.error("The native ARM64 artifact lacks one or more images")
        references = {}
        for target in TARGETS:
            tag = f"{repository_uri}:{target}-{revision}"
            existing = json.loads(run("aws", "ecr", "list-images", "--region", REGION,
                                      "--repository-name", REPOSITORY, "--filter", "tagStatus=TAGGED", "--output", "json"))
            if not any(row.get("imageTag") == f"{target}-{revision}" for row in existing["imageIds"]):
                run(str(args.crane), "push", str(images_dir / f"{target}.tar"), tag)
            config = json.loads(run(str(args.crane), "config", tag))
            if config.get("architecture") != "arm64" or config.get("os") != "linux":
                parser.error(f"Published {target} image is not native linux/arm64")
            digest = run(str(args.crane), "digest", tag)
            references[target] = f"{repository_uri}@{digest}"
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
                          "bundle": str(args.output)}))


if __name__ == "__main__":
    main()
