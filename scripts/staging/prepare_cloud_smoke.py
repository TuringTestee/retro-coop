#!/usr/bin/env python3
"""Exercise the staging cloud setup command with isolated Git and cloud CLI mocks."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("prepare_cloud.sh")
PROJECT = "bship-164753-06152350"
MOCK = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with Path(os.environ['STAGING_MOCK_LOG']).open('a') as file:
    file.write(json.dumps(args) + '\n')
kind = ' '.join(args[:3])
if kind == os.environ.get('STAGING_MOCK_FAIL'):
    sys.exit(42)
if kind == 'container clusters describe':
    print('RUNNING')
elif kind in ('artifacts repositories list', 'compute addresses list'):
    pass
elif kind == 'artifacts docker images':
    image = args[4]
    digest = 'a' * 64 if image.endswith('/edge') else 'b' * 64
    tags = [] if os.environ.get('STAGING_MOCK_MISSING_TAG') else [os.environ['STAGING_MOCK_REVISION']]
    print(json.dumps([{'version': 'sha256:' + digest, 'tags': tags}]))
elif kind == 'compute addresses describe':
    print('8.8.8.8')
'''


def run(root, environment):
    return subprocess.run(
        ["sh", "scripts/staging/prepare_cloud.sh", PROJECT],
        cwd=root, env=environment, capture_output=True, text=True,
    )


with tempfile.TemporaryDirectory(prefix="retro-cloud-setup-") as temp:
    root = Path(temp) / "checkout"
    (root / "scripts/staging").mkdir(parents=True)
    shutil.copyfile(SCRIPT, root / "scripts/staging/prepare_cloud.sh")
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    for key, value in (("user.name", "Staging smoke"), ("user.email", "staging@example.invalid")):
        subprocess.run(["git", "config", key, value], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "candidate"], cwd=root, check=True)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    subprocess.run(["git", "update-ref", "refs/remotes/origin/main", revision], cwd=root, check=True)
    bin_dir = Path(temp) / "bin"
    bin_dir.mkdir()
    mock = bin_dir / "gcloud"
    mock.write_text(MOCK)
    mock.chmod(0o755)
    log = Path(temp) / "calls.jsonl"
    environment = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "STAGING_MOCK_LOG": str(log), "STAGING_MOCK_REVISION": revision}

    (root / "untracked.txt").write_text("not in the reviewed revision")
    dirty = run(root, environment)
    assert dirty.returncode != 0 and "uncommitted changes" in dirty.stderr
    assert not log.exists(), "Cloud CLI ran from a dirty checkout"
    (root / "untracked.txt").unlink()

    bad_inventory = run(root, {**environment, "STAGING_MOCK_FAIL": "artifacts repositories list"})
    assert bad_inventory.returncode != 0 and "Could not check image repository" in bad_inventory.stderr
    assert not any("create" in json.loads(line) for line in log.read_text().splitlines())

    log.write_text("")
    missing_tag = run(root, {**environment, "STAGING_MOCK_MISSING_TAG": "1"})
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert missing_tag.returncode != 0 and "exactly one immutable digest" in missing_tag.stderr
    assert [call[:3] for call in calls].count(["artifacts", "repositories", "create"]) == 1
    assert not any(call[:3] == ["compute", "addresses", "create"] for call in calls)
    assert "teardown.sh" in missing_tag.stderr

    log.write_text("")
    success = run(root, environment)
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert success.returncode == 0, success.stderr
    lines = success.stdout.splitlines()
    assert f"EDGE_IMAGE=us-central1-docker.pkg.dev/{PROJECT}/retro-coop-staging/edge@sha256:{'a' * 64}" in lines, lines
    assert f"COORDINATOR_IMAGE=us-central1-docker.pkg.dev/{PROJECT}/retro-coop-staging/coordinator@sha256:{'b' * 64}" in lines, lines
    assert "STAGING_IP=8.8.8.8" in lines
    assert any(call[:3] == ["compute", "addresses", "create"] for call in calls)
    assert any(call[:2] == ["builds", "submit"] and f"_SOURCE_REVISION={revision}" in " ".join(call) for call in calls)

print("Staging cloud preparation passed (clean revision, fail-closed queries, exact digests and named address).")
