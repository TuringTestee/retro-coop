#!/usr/bin/env python3
"""Exercise the relay's create and teardown commands against disposable CLI mocks."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
workload = (root / 'deploy/staging/k8s/base/workload.yaml').read_text()
assert 'activeDeadlineSeconds: 21600' in workload, 'The GKE trial must stop with the TURN VM'
edge = (root / 'deploy/staging/nginx.conf').read_text()
assert 'limit_conn staging_connections 6;' in edge and 'limit_rate 256k;' in edge
relay = (root / 'scripts/staging/configure_turn.sh').read_text()
assert 'tbf rate 3mbit' in relay
with tempfile.TemporaryDirectory(prefix="retro-turn-operator-") as temporary:
    directory = Path(temporary)
    state = directory / "state.json"
    state.write_text(json.dumps({"namespace": True}))
    log = directory / "calls.jsonl"
    gcloud = directory / "gcloud"
    gcloud.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
path=Path(os.environ['STAGING_MOCK_STATE'])
state=json.loads(path.read_text())
args=sys.argv[1:]
with Path(os.environ['STAGING_MOCK_LOG']).open('a') as log: log.write(json.dumps(['gcloud',*args])+'\\n')
kind=' '.join(args[:3])
if os.environ.get('STAGING_MOCK_FAIL_QUERY')==kind: sys.exit(42)
if kind.startswith('compute networks subnets'): resource='subnet'
elif kind.startswith('compute networks'): resource='network'
elif kind.startswith('compute instances'): resource='vm'
elif kind.startswith('compute firewall-rules'): resource='firewall_'+(next((a.split('=',2)[2] for a in args if a.startswith('--filter=name=')),args[3] if len(args)>3 else ''))
elif kind.startswith('compute addresses'): resource='address'
elif kind.startswith('artifacts repositories'): resource='repository'
else: resource=None
if resource:
  action='list' if 'list' in args[:4] else 'create' if 'create' in args[:4] else 'delete' if 'delete' in args[:4] else 'describe'
  if action=='list' and state.get(resource):
    print('projects/bship-164753-06152350/locations/us-central1/repositories/retro-coop-staging' if resource=='repository' and os.environ.get('STAGING_MOCK_QUALIFIED_REPO') else 'retro-coop-staging' if resource in ('network','subnet','address','repository') else 'retro-coop-staging-turn' if resource=='vm' else resource.removeprefix('firewall_'))
  elif action=='create': state[resource]=True
  elif action=='delete': state[resource]=False
  elif action=='describe' and resource=='vm':
    form=next((a for a in args if a.startswith('--format=')), '')
    print('10.76.0.2' if 'networkIP' in form else '34.100.1.2' if 'natIP' in form else '2026-09-24T20:00:00Z')
path.write_text(json.dumps(state))
''')
    gcloud.chmod(0o755)
    kubectl = directory / "kubectl"
    kubectl.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
path=Path(os.environ['STAGING_MOCK_STATE']);state=json.loads(path.read_text());args=sys.argv[1:]
with Path(os.environ['STAGING_MOCK_LOG']).open('a') as log: log.write(json.dumps(['kubectl',*args])+'\\n')
if args[:2]==['delete','namespace']: state['namespace']=False
if args[:2]==['get','namespace'] and state.get('namespace'): print('namespace/retro-coop-staging')
path.write_text(json.dumps(state))
''')
    kubectl.chmod(0o755)
    environment = {**os.environ, "PATH": str(directory) + os.pathsep + os.environ["PATH"],
                   "STAGING_MOCK_STATE": str(state), "STAGING_MOCK_LOG": str(log)}
    provision = ["sh", str(root / "scripts/staging/provision_turn.sh"), "bship-164753-06152350", "us-central1-a",
                 "8.8.8.8/32", "1.1.1.1/32", "9.9.9.9/32"]
    rejected = subprocess.run([*provision[:4], "0.0.0.0/0", *provision[5:]], cwd=root, env=environment, capture_output=True)
    assert rejected.returncode != 0 and not log.exists(), "Unsafe address reached gcloud"
    subprocess.run(provision, cwd=root, env=environment, check=True, capture_output=True)
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    instance = next(call for call in calls if call[:4] == ['gcloud','compute','instances','create'])
    for required in ['--max-run-duration=6h','--instance-termination-action=DELETE','--no-service-account','--no-scopes']:
        assert required in instance, f"VM is missing {required}"
    relay_firewall = next(call for call in calls if call[:4] == ['gcloud','compute','firewall-rules','create'] and call[4]=='retro-coop-staging-turn')
    assert '--source-ranges=8.8.8.8/32,1.1.1.1/32' in relay_firewall
    assert '--allow=udp:3478,tcp:3478,udp:49160-49175' in relay_firewall
    hosted = json.loads(state.read_text())
    hosted.update(address=True, repository=True)
    state.write_text(json.dumps(hosted))
    subprocess.run(["sh", str(root / "scripts/staging/teardown.sh"), "bship-164753-06152350"], cwd=root, env=environment, check=True, capture_output=True)
    remainder = json.loads(state.read_text())
    assert not any(remainder.values()), f"Trial resources remain: {remainder}"
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert ['kubectl','delete','namespace','retro-coop-staging','--ignore-not-found=true','--wait=true','--timeout=10m'] in calls
    namespace_delete = next(i for i, call in enumerate(calls) if call[:3] == ['kubectl','delete','namespace'])
    address_delete = next(i for i, call in enumerate(calls) if call[:4] == ['gcloud','compute','addresses','delete'])
    assert namespace_delete < address_delete, 'The load balancer must be removed before its IP'
    scenario = os.environ.get('STAGING_SMOKE_CASE', 'all')
    if scenario != 'query':
        state.write_text(json.dumps({'repository': True}))
        qualified = {**environment, 'STAGING_MOCK_QUALIFIED_REPO': '1'}
        subprocess.run(["sh", str(root / "scripts/staging/teardown.sh"), "bship-164753-06152350"], cwd=root, env=qualified, check=True, capture_output=True)
        assert not json.loads(state.read_text()).get('repository'), 'Qualified repository name survived teardown'
    if scenario != 'qualified':
        state.write_text(json.dumps({}))
        failed = {**environment, 'STAGING_MOCK_FAIL_QUERY': 'compute networks list'}
        teardown_result = subprocess.run(["sh", str(root / "scripts/staging/teardown.sh"), "bship-164753-06152350"], cwd=root, env=failed, capture_output=True, text=True)
        assert teardown_result.returncode != 0 and 'removed' not in teardown_result.stdout, 'Failed inventory query was reported as successful teardown'
        repository_query_failed = {**environment, 'STAGING_MOCK_FAIL_QUERY': 'artifacts repositories list'}
        repository_result = subprocess.run(["sh", str(root / "scripts/staging/teardown.sh"), "bship-164753-06152350"], cwd=root, env=repository_query_failed, capture_output=True, text=True)
        assert repository_result.returncode != 0 and 'removed' not in repository_result.stdout, 'Failed repository query was reported as successful teardown'
        start = len(log.read_text().splitlines())
        provision_result = subprocess.run(provision, cwd=root, env=failed, capture_output=True, text=True)
        later = [json.loads(line) for line in log.read_text().splitlines()[start:]]
        assert provision_result.returncode != 0 and not any('create' in call[:4] for call in later), 'Failed inventory query reached resource creation'
print("TURN operator commands passed (narrow firewall, six-hour VM deletion and isolated teardown).")
