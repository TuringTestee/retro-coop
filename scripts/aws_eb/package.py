#!/usr/bin/env python3
"""Create the small Elastic Beanstalk Compose source bundle from immutable images."""

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "deploy/aws-eb"
IMAGE = re.compile(r"^(?P<account>[0-9]{12})\.dkr\.ecr\.us-east-1\.amazonaws\.com/retro-coop@sha256:[a-f0-9]{64}$")
SHA = re.compile(r"^[a-f0-9]{64}$")
REVISION = re.compile(r"^[a-f0-9]{40}$")


def render(edge: str, coordinator: str, caddy: str, turn: str, local: bool = False) -> str:
    images = (edge, coordinator, caddy, turn)
    if not local:
        matches = [IMAGE.fullmatch(image) for image in images]
        if any(match is None for match in matches) or len({match.group("account") for match in matches}) != 1:
            raise ValueError("All images must be immutable digests in one account, region and repository")
    if len(set(images)) != len(images):
        raise ValueError("Each service must use a distinct image")
    template = (SOURCE / "docker-compose.yml").read_text()
    for name, image in zip(("EDGE", "COORDINATOR", "CADDY", "TURN"), images):
        template = template.replace(f"__{name}_IMAGE__", image)
    return template


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edge-image", required=True)
    parser.add_argument("--coordinator-image", required=True)
    parser.add_argument("--caddy-image", required=True)
    parser.add_argument("--turn-image", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--asset-manifest", required=True, type=Path)
    parser.add_argument("--core-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not REVISION.fullmatch(args.source_revision) or not SHA.fullmatch(args.core_sha256):
        parser.error("Source revision and core SHA-256 must be full lowercase hashes")
    try:
        compose = render(args.edge_image, args.coordinator_image, args.caddy_image, args.turn_image)
        assets = json.loads(args.asset_manifest.read_text())
    except (ValueError, OSError, json.JSONDecodeError) as error:
        parser.error(str(error))
    if not isinstance(assets, dict) or not assets or any(
        not isinstance(path, str) or not path.startswith("/") or not SHA.fullmatch(digest)
        for path, digest in assets.items()
    ):
        parser.error("Asset manifest must map absolute asset paths to SHA-256 digests")
    record = {
        "sourceRevision": args.source_revision,
        "edgeImage": args.edge_image,
        "coordinatorImage": args.coordinator_image,
        "caddyImage": args.caddy_image,
        "turnImage": args.turn_image,
        "coreSha256": args.core_sha256,
        "clientAssets": assets,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("docker-compose.yml", compose)
        bundle.writestr("release.json", json.dumps(record, sort_keys=True, indent=2) + "\n")
        bundle.write(SOURCE / ".ebextensions/01-environment.config", ".ebextensions/01-environment.config")
    print(json.dumps({"bundle": str(args.output), "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(), "sourceRevision": args.source_revision}))


if __name__ == "__main__":
    main()
