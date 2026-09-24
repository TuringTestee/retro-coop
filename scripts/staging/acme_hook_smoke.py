#!/usr/bin/env python3
"""Exercise the ACME hook's boundaries without contacting GKE or Let's Encrypt."""

import os
import subprocess
import tempfile
from pathlib import Path

hook = Path(__file__).with_name("acme_hook.sh")
with tempfile.TemporaryDirectory(prefix="retro-acme-hook-") as temporary:
    root = Path(temporary)
    kubectl = root / "kubectl"
    kubectl.write_text(
        "#!/usr/bin/env python3\n"
        "import os, pathlib, sys\n"
        "if 'get' in sys.argv:\n"
        " print(os.environ.get('STAGING_HOOK_PODS', 'retro-coop-staging-abc')); sys.exit(0)\n"
        "pathlib.Path(os.environ['STAGING_HOOK_LOG']).write_text(' '.join(sys.argv[1:]))\n"
        "if '-i' in sys.argv:\n"
        " pathlib.Path(os.environ['STAGING_HOOK_BODY']).write_bytes(sys.stdin.buffer.read())\n"
    )
    kubectl.chmod(0o755)
    curl = root / "curl"
    curl.write_text("#!/bin/sh\nprintf '%s' \"$CERTBOT_VALIDATION\"\n")
    curl.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": str(root) + os.pathsep + os.environ["PATH"],
        "RETRO_STAGING_PUBLIC_IP": "34.100.1.2",
        "CERTBOT_IDENTIFIER": "34.100.1.2",
        "CERTBOT_TOKEN": "sample_token-1",
        "CERTBOT_VALIDATION": "sample_token-1.proof",
        "STAGING_HOOK_LOG": str(root / "invocation"),
        "STAGING_HOOK_BODY": str(root / "body"),
    }
    subprocess.run(["sh", str(hook), "auth"], env=environment, check=True)
    if (root / "body").read_text() != environment["CERTBOT_VALIDATION"]:
        raise AssertionError("The challenge body changed")
    if "pod/retro-coop-staging-abc -c edge" not in (root / "invocation").read_text():
        raise AssertionError("The hook wrote outside the staging edge")
    subprocess.run(["sh", str(hook), "cleanup"], env=environment, check=True)
    if "rm -f /var/www/acme/.well-known/acme-challenge/sample_token-1" not in (root / "invocation").read_text():
        raise AssertionError("The challenge file was not removed")
    for broken in [
        {**environment, "CERTBOT_IDENTIFIER": "34.100.1.3"},
        {**environment, "CERTBOT_TOKEN": "../private"},
        {**environment, "RETRO_STAGING_PUBLIC_IP": ""},
    ]:
        if subprocess.run(["sh", str(hook), "auth"], env=broken, capture_output=True).returncode == 0:
            raise AssertionError("An invalid challenge was accepted")
    for pods in ["", "retro-coop-staging-a retro-coop-staging-b"]:
        broken = {**environment, "STAGING_HOOK_PODS": pods}
        if subprocess.run(["sh", str(hook), "auth"], env=broken, capture_output=True).returncode == 0:
            raise AssertionError("An absent or ambiguous staging Pod was accepted")
print("ACME hook passed (write, reachability, cleanup and invalid input).")
