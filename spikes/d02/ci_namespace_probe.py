"""Prove the real deadline stops detached and orphaned namespace workloads."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from ci_budget import namespace_command, run_command


def probe(ci=False):
    with tempfile.TemporaryDirectory(prefix='d02-containment-') as directory:
        root = Path(directory)
        heartbeat = 'import pathlib,sys,time\np=pathlib.Path(sys.argv[1])\nwhile True:\n p.open("a").write("x");time.sleep(.02)'
        orphan = 'import os\nif os.fork():os._exit(0)\n' + heartbeat
        workload = '''import os,sys,subprocess,time,json,pathlib
root=pathlib.Path(sys.argv[1])
if sys.argv[4]=='ci': subprocess.run(['sudo','-n','true'],check=True)
(root/'identity').write_text(json.dumps({'uid':os.getuid(),'gid':os.getgid(),'cwd':os.getcwd(),'home':os.environ.get('HOME'),'path':os.environ.get('PATH'),'marker':os.environ['D02_CONTAINMENT_MARKER']}))
subprocess.Popen([sys.executable,'-c',sys.argv[2],str(root/'detached')],start_new_session=True)
subprocess.Popen([sys.executable,'-c',sys.argv[3],str(root/'orphan')],start_new_session=True)
time.sleep(10)
'''
        os.environ['D02_CONTAINMENT_MARKER'] = 'preserved'
        command = namespace_command([sys.executable, '-c', workload, directory,
                                     heartbeat, orphan, 'ci' if ci else 'local'], ci=ci)
        started = time.monotonic()
        code = run_command(time.time() + 2, command)
        assert code == 124, f'Expected timeout, got {code}'
        identity = json.loads((root / 'identity').read_text())
        assert identity == {'uid': os.getuid(), 'gid': os.getgid(),
                            'cwd': os.getcwd(), 'home': os.environ.get('HOME'),
                            'path': os.environ.get('PATH'), 'marker': 'preserved'}, identity
        files = [root / 'detached', root / 'orphan']
        sizes = [p.stat().st_size for p in files]
        assert min(sizes) > 2, 'Both actual workloads must have started'
        time.sleep(.2)
        sizes = [p.stat().st_size for p in files]
        time.sleep(.2)
        assert sizes == [p.stat().st_size for p in files], 'Detached workload survived'
        markers = {str(p).encode() for p in files}
        survivors = []
        for process in Path('/proc').iterdir():
            if not process.name.isdigit():
                continue
            try:
                arguments = (process / 'cmdline').read_bytes().split(b'\0')
                if markers.intersection(arguments):
                    survivors.append(process.name)
            except (FileNotFoundError, ProcessLookupError):
                pass
        assert not survivors, f'Workload processes survived: {survivors}'
        print(json.dumps({'passed': True, 'ci_sudo_prefix': ci,
                          'uid_gid_cwd_environment_preserved': True,
                          'detached_and_orphan_heartbeats_stopped': True,
                          'no_workload_processes_remaining': True,
                          'elapsed_seconds': time.monotonic() - started}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ci', action='store_true')
    probe(parser.parse_args().ci)
