#!/usr/bin/env python3
"""Write the short-lived coturn configuration without printing its secret."""

import argparse
import ipaddress
import os
import re
from pathlib import Path


def ipv4(value, public):
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as error:
        raise argparse.ArgumentTypeError("Expected one IPv4 address") from error
    if public and not address.is_global:
        raise argparse.ArgumentTypeError("TURN external address must be public")
    if not public and (not address.is_private or address.is_multicast or address.is_unspecified):
        raise argparse.ArgumentTypeError("TURN internal address must be private")
    return str(address)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-ip", required=True, type=lambda value: ipv4(value, True))
    parser.add_argument("--private-ip", required=True, type=lambda value: ipv4(value, False))
    parser.add_argument("--secret-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--runtime-dir", type=Path, default=Path("/run/retro-coop-turn"))
    parser.add_argument("--listen-port", type=int, default=3478)
    args = parser.parse_args()
    if args.secret_file.stat().st_mode & 0o077:
        parser.error("Secret file must be readable only by its owner")
    secret = args.secret_file.read_text()
    if not re.fullmatch(r"[a-z0-9]{64}", secret):
        parser.error("Secret must contain 64 lowercase alphanumeric characters")
    if not args.runtime_dir.is_absolute() or "\n" in str(args.runtime_dir):
        parser.error("Runtime directory must be an absolute path")
    if not 1024 <= args.listen_port <= 65535:
        parser.error("TURN listener port must be unprivileged")
    configuration = f"""listening-ip={args.private_ip}
relay-ip={args.private_ip}
external-ip={args.public_ip}/{args.private_ip}
listening-port={args.listen_port}
min-port=49160
max-port=49175
realm=retro-coop.atobot.cloud
use-auth-secret
static-auth-secret={secret}
user-quota=4
total-quota=16
relay-threads=1
max-bps=100000
bps-capacity=1600000
no-multicast-peers
denied-peer-ip=0.0.0.0-0.255.255.255
denied-peer-ip=10.0.0.0-10.255.255.255
denied-peer-ip=127.0.0.0-127.255.255.255
denied-peer-ip=169.254.0.0-169.254.255.255
denied-peer-ip=172.16.0.0-172.31.255.255
denied-peer-ip=192.168.0.0-192.168.255.255
no-cli
no-tls
no-dtls
no-tcp-relay
no-software-attribute
pidfile={args.runtime_dir}/turn.pid
log-file=stdout
"""
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as target:
        target.write(configuration)


if __name__ == "__main__":
    main()
