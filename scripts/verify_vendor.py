"""Verify committed dependency bytes against recorded upstream/patch provenance."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
provenance = json.loads((root / 'vendor/tetanes-core.provenance.json').read_text())
package = root / 'vendor/tetanes-core'
actual = {str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in package.rglob('*') if p.is_file()}
expected = {name: digest for name, digest in provenance['upstream_files'].items()
            if not any(name.startswith(prefix) for prefix in provenance['omitted_prefixes'])}
expected |= provenance['patched_files']
assert actual == expected, 'Vendored core differs from recorded upstream and reviewed patch bytes'
patch = root / 'vendor/tetanes-core.patch'
assert hashlib.sha256(patch.read_bytes()).hexdigest() == provenance['patch_sha256'], 'Patch changed'
for name, source in provenance['supplementary_files'].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == source['sha256'], name
print('PASS: vendored core provenance, exact file inventory and bounded patch bytes')
