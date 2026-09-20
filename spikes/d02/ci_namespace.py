"""Keep a user-owned PID 1 alive so namespace teardown kills every descendant."""
import os
import subprocess
import sys

if os.getpid() != 1:
    raise SystemExit('CI supervisor requires its own PID namespace')
if os.getuid() != int(sys.argv[1]) or os.getgid() != int(sys.argv[2]):
    raise SystemExit('CI namespace changed the workload user')
# Never exec the command: PID 1 remains unprivileged even while a child uses sudo.
# Linux kills every process in this namespace when PID 1 exits or receives SIGKILL.
# sudo may replace HOME/PATH even with -E; restore the invoking workload values.
os.environ['HOME'] = sys.argv[3]
os.environ['PATH'] = sys.argv[4]
result = subprocess.run(sys.argv[5:])
raise SystemExit(result.returncode if result.returncode >= 0 else 128 - result.returncode)
