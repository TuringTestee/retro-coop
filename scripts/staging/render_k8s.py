#!/usr/bin/env python3
"""Render the isolated GKE staging resources without contacting a cluster."""

import argparse
import ipaddress
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[2] / "deploy/staging/k8s/base"
IMAGE = re.compile(r"^(?P<name>[a-z0-9.-]+/[a-z0-9._/-]+)@sha256:(?P<digest>[a-f0-9]{64})$")


def image(value):
    match = IMAGE.fullmatch(value)
    if not match:
        raise argparse.ArgumentTypeError("Image must be a registry path pinned by sha256 digest")
    return match.groupdict()


def public_ip(value):
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as error:
        raise argparse.ArgumentTypeError("Use one public IPv4 address") from error
    if not address.is_global:
        raise argparse.ArgumentTypeError("The load balancer IP must be public")
    return str(address)


def source_range(value):
    try:
        network = ipaddress.IPv4Network(value, strict=True)
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as error:
        raise argparse.ArgumentTypeError("Use a canonical IPv4 CIDR") from error
    if network.prefixlen != 0 and not network.network_address.is_global:
        raise argparse.ArgumentTypeError("Tester ranges must be public IPv4 CIDRs")
    return str(network)


def render(args):
    if not args.allow:
        raise ValueError("At least one tester source range is required")
    if "0.0.0.0/0" in args.allow and (len(args.allow) != 1 or not args.acme_bootstrap):
        raise ValueError("Open access is allowed only with --acme-bootstrap for certificate issuance")
    if args.acme_bootstrap and args.allow != ["0.0.0.0/0"]:
        raise ValueError("The ACME bootstrap flag requires exactly --allow 0.0.0.0/0")

    with tempfile.TemporaryDirectory(prefix="retro-staging-render-") as temporary:
        root = Path(temporary)
        shutil.copytree(BASE, root / "base")
        overlay = root / "overlay"
        overlay.mkdir()
        (overlay / "kustomization.yaml").write_text(
            "apiVersion: kustomize.config.k8s.io/v1beta1\n"
            "kind: Kustomization\n"
            "resources:\n  - ../base\n"
            "images:\n"
            f"  - name: retro-coop-staging-edge\n    newName: {args.edge_image['name']}\n    digest: sha256:{args.edge_image['digest']}\n"
            f"  - name: retro-coop-staging-coordinator\n    newName: {args.coordinator_image['name']}\n    digest: sha256:{args.coordinator_image['digest']}\n"
            "configMapGenerator:\n"
            "  - name: retro-coop-staging-config\n"
            f"    literals:\n      - COORDINATOR_ORIGINS=https://{args.public_ip}\n"
            "generatorOptions:\n  disableNameSuffixHash: true\n"
            "patches:\n"
            "  - target:\n      kind: Service\n      name: retro-coop-staging\n"
            "    patch: |-\n"
            "      - op: replace\n        path: /spec/loadBalancerIP\n"
            f"        value: {json.dumps(args.public_ip)}\n"
            "      - op: replace\n        path: /spec/loadBalancerSourceRanges\n"
            f"        value: {json.dumps(args.allow)}\n"
        )
        return subprocess.check_output(["kubectl", "kustomize", str(overlay)], text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-ip", required=True, type=public_ip)
    parser.add_argument("--edge-image", required=True, type=image)
    parser.add_argument("--coordinator-image", required=True, type=image)
    parser.add_argument("--allow", action="append", type=source_range)
    parser.add_argument("--acme-bootstrap", action="store_true")
    args = parser.parse_args()
    try:
        print(render(args), end="")
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
