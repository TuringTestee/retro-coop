"""Record runner capacity and cumulative CPU counters without claiming their cause."""
import json
import os
import platform
import sys
import time
from pathlib import Path


def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


cpu = read('/proc/cpuinfo') or ''
result = {
    'captured_epoch_seconds': time.time(),
    'platform': platform.platform(),
    'logical_cpu_count': os.cpu_count(),
    'affinity': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
    'cpu_models': sorted({line.split(':', 1)[1].strip() for line in cpu.splitlines() if line.startswith('model name')}),
    'memory': {line.split(':', 1)[0]: line.split(':', 1)[1].strip()
               for line in (read('/proc/meminfo') or '').splitlines()
               if line.startswith(('MemTotal:', 'MemAvailable:'))},
    'cgroup_cpu_max': read('/sys/fs/cgroup/cpu.max'),
    'cgroup_cpu_stat': read('/sys/fs/cgroup/cpu.stat'),
    'proc_cpu_stat': (read('/proc/stat') or '').splitlines()[:1],
    'load_average': read('/proc/loadavg'),
}
Path(sys.argv[1]).write_text(json.dumps(result, indent=2) + '\n')
