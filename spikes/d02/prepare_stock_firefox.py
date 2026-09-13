"""Install the pinned official Linux Firefox in a new directory after verifying its archive."""

import argparse
import hashlib
import json
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

VERSION = "146.0.1"
URL = f"https://archive.mozilla.org/pub/firefox/releases/{VERSION}/linux-x86_64/en-US/firefox-{VERSION}.tar.xz"
ARCHIVE_SHA256 = "36a4dc0e3be8af2d49d8388021abf790976d2398162b9d13a6d758cc8c37f8dd"
ARCHIVE_BYTES = 79925480


def install(output, archive=None):
    output = output.resolve()
    if output.exists():
        raise ValueError("Output already exists; use its verified binary or choose a new directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".retro-firefox-", dir=output.parent) as temporary:
        stage = Path(temporary)
        if archive is None:
            archive = stage / "firefox.tar.xz"
            started = time.monotonic()
            size = 0
            with urllib.request.urlopen(URL, timeout=30) as response, archive.open("wb") as target:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > ARCHIVE_BYTES or time.monotonic() - started > 120:
                        raise ValueError("Firefox download exceeded its size or time bound")
                    target.write(chunk)
        with archive.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        if archive.stat().st_size != ARCHIVE_BYTES or digest != ARCHIVE_SHA256:
            raise ValueError("Firefox archive does not match the pinned official SHA-256 and length")
        tree = stage / "installation"
        tree.mkdir()
        with tarfile.open(archive) as package:
            package.extractall(tree, filter="data")
        binary = tree / "firefox/firefox"
        if not binary.is_file():
            raise ValueError("Verified Firefox archive lacks the expected executable")
        # Test installations must not silently change browser version after launch.
        distribution = tree / "firefox/distribution"
        distribution.mkdir(exist_ok=True)
        (distribution / "policies.json").write_text(
            json.dumps({"policies": {"DisableAppUpdate": True}}, indent=2) + "\n"
        )
        metadata = {
            "browser": "Mozilla Firefox",
            "version": VERSION,
            "platform": "linux-x86_64",
            "source": URL,
            "checksum_source": f"https://archive.mozilla.org/pub/firefox/releases/{VERSION}/SHA256SUMS",
            "archive_sha256": digest,
            "archive_bytes": ARCHIVE_BYTES,
            "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "application_updates": "disabled by installation-local enterprise policy",
        }
        (tree / "browser-build.json").write_text(json.dumps(metadata, indent=2) + "\n")
        if output.exists():
            raise ValueError("Output was created during installation; refusing to replace it")
        tree.rename(output)
    return output / "firefox/firefox"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New installation directory")
    parser.add_argument("--archive", type=Path, help="Reuse a local archive; identical integrity checks apply")
    args = parser.parse_args()
    print(install(args.output, args.archive))
