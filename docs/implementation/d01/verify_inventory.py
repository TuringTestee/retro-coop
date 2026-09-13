#!/usr/bin/env python3
"""Check D01 evidence against exact local upstream checkouts; does not run ROMs."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

inventory = json.loads(Path(__file__).with_name('inventory.json').read_text())
root = Path(sys.argv[1])
checkouts = {name: root / ('d01-' + name) for name in
             ('tetanes', 'jsnes', 'binjnes', 'accuracycoin')}
checked_files = 0
for source in inventory['sources']:
    checkout = checkouts[source['id']]
    actual_pin = subprocess.check_output(
        ['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
    assert actual_pin == source['revision'], source['id']
    for file in source['files']:
        assert hashlib.sha256((checkout / file['path']).read_bytes()).hexdigest() == file['sha256'], file['path']
        checked_files += 1

mapper_source = (checkouts['tetanes'] / 'tetanes-core/src/mapper.rs').read_text()
registration = mapper_source.split('    cart:\n', 1)[1].split('\nimpl Default for Mapper', 1)[0]
actual_rows = []
for match in re.finditer(r'\b(\w+)\([^\n]+?\) = \d+ in (\w+) \{([^}]+)\}', registration):
    family, module, body = match.groups()
    ids = []
    for arm in re.finditer(r'(\d+(?: \| \d+)*)(?: if [^=]+)? =>', body):
        ids.extend(map(int, arm[1].split(' | ')))
    actual_rows.append((family, ids, f'tetanes-core/src/mapper/{module}.rs'))
rows = inventory['selected_hardware']
assert actual_rows == [(r['family'], r['mapper_ids'], r['source_path']) for r in rows]
assert all((checkouts['tetanes'] / r['source_path']).is_file() for r in rows)
selected = sorted({n for r in rows for n in r['mapper_ids']})
assert selected == inventory['unknown_mapper_policy']['implemented_ids']
assert all(r['regions'] == ['NTSC', 'PAL', 'Dendy'] for r in rows)
assert all(r['local_play'] == r['netplay'] == 'untested' for r in rows)

js_source = (checkouts['jsnes'] / 'src/mappers/index.js').read_text()
js_ids = list(map(int, re.findall(r'^  (\d+): Mapper', js_source, re.M)))
bin_source = (checkouts['binjnes'] / 'src/emulator.c').read_text()
start = bin_source.index('  case 0:', bin_source.index('case 3: ci->system'))
end = bin_source.index('  case 232:', start) + len('  case 232:')
bin_ids = sorted(set(map(int, re.findall(r'^  case (\d+):', bin_source[start:end], re.M))))
assert [c['mapper_ids'] for c in inventory['candidates']] == [selected, js_ids, bin_ids]

fixture = inventory['fixtures'][0]
rom = (checkouts[fixture['source']] / fixture['path']).read_bytes()
assert rom[:4] == b'NES\x1a'
assert ((rom[6] >> 4) | (rom[7] & 0xf0)) == fixture['mapper'] == 0
assert rom[:16].hex() == fixture['header_hex']
assert len(rom) == fixture['bytes'] == 16 + rom[4] * 16384 + rom[5] * 8192
assert hashlib.sha256(rom).hexdigest() == fixture['sha256']
assert fixture['redistributed'] is False
assert fixture['local_play'] == fixture['netplay'] == 'untested'
print(f'PASS: 4 exact source pins; {checked_files} file hashes; {len(rows)} dispatch rows; '
      f'{len(selected)}/{len(js_ids)}/{len(bin_ids)} candidate mapper IDs; '
      f'{len(rom)}-byte fixture header/hash; all qualification statuses untested.')
