"""Bind a probe result to sidecars from its unique isolated network run."""
import json
import sys
from pathlib import Path

directory = Path(sys.argv[1])
marker = json.loads((directory/'run-id.local.json').read_text())
pointer_path = directory/'result-pointer.json'
if pointer_path.exists():
    pointer = json.loads(pointer_path.read_text())
    result_path = Path(pointer['output'])
    result = json.loads(result_path.read_text())
    if not (pointer['run_id'] == result['run_id'] == marker['run_id'] == directory.name):
        raise ValueError('Network run identity mismatch; refusing mixed evidence')
    bundle = {'run_id': marker['run_id']}
    for key, filename in [('netem_before','netem-before.local.json'),('netem_after','netem-after.local.json'),
                          ('route','route.local.json'),('udp_headers','udp-headers.local.json')]:
        bundle[key] = json.loads((directory/filename).read_text())
    result['network_evidence'] = bundle
    result_path.write_text(json.dumps(result, indent=2)+'\n')
