#!/usr/bin/env python3
"""Record diagnostic host pressure, disk headroom, elapsed time and child rusage.

Host memory includes background services; ru_maxrss is the largest individual
child, NOT aggregate build memory. Warm repeats are a no-op lower bound, not an
Actions-cache restore or a changed-code PR simulation. JSON survives failure.
"""

import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time


def memory():
    fields = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        fields[key] = int(value.split()[0]) * 1024
    return {
        'used_bytes': fields['MemTotal'] - fields['MemAvailable'],
        'available_bytes': fields['MemAvailable'],
        'swap_used_bytes': fields['SwapTotal'] - fields['SwapFree'],
    }


def sizes():
    paths = [Path('target'), Path.home() / '.cargo/registry', Path.home() / '.cargo/git']
    result = {}
    for path in paths:
        if path.exists():
            output = subprocess.check_output(['du', '-s', '-B1', str(path)], text=True)
            result[str(path)] = int(output.split()[0])
    return result


def main():
    prefix = Path(sys.argv[1])
    command = sys.argv[2:]
    if not command:
        raise SystemExit('A command is required')
    prefix.parent.mkdir(parents=True, exist_ok=True)
    before = memory()
    disk_before = shutil.disk_usage('.')
    sizes_before = sizes()
    minimum_free = disk_before.free
    peak_used = before['used_bytes']
    peak_swap = before['swap_used_bytes']
    started = time.monotonic()
    with prefix.with_suffix('.samples.jsonl').open('w') as samples:
        process = subprocess.Popen(command)
        while True:
            current = memory()
            free = shutil.disk_usage('.').free
            minimum_free = min(minimum_free, free)
            peak_used = max(peak_used, current['used_bytes'])
            peak_swap = max(peak_swap, current['swap_used_bytes'])
            samples.write(json.dumps({'seconds': time.monotonic() - started,
                                      'disk_free_bytes': free, **current}) + '\n')
            samples.flush()
            status = process.poll()
            if status is not None:
                break
            time.sleep(1)
    elapsed = time.monotonic() - started
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = {
        'command': command, 'exit_code': status, 'elapsed_seconds': elapsed,
        'logical_cpus': os.cpu_count(), 'memory_before': before,
        'host_peak_used_bytes': peak_used,
        'host_peak_used_increase_bytes': peak_used - before['used_bytes'],
        'host_peak_swap_used_bytes': peak_swap,
        'largest_child_maxrss_kib_not_aggregate': usage.ru_maxrss,
        'disk_total_bytes': disk_before.total,
        'disk_free_before_bytes': disk_before.free,
        'disk_minimum_free_bytes': minimum_free,
        'disk_free_after_bytes': shutil.disk_usage('.').free,
        'directory_sizes_before': sizes_before, 'directory_sizes_after': sizes(),
        'cache_context': os.environ.get('PROBE_CACHE_CONTEXT', 'No Actions cache restored or saved'),
        'limitations': 'Host memory/disk include background activity; sampled every 1s. '
                       'See cache_context for restore mode. Warm is identical-source repeat. '
                       'Child maxrss is not summed simultaneous memory.',
    }
    prefix.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)
    return status if status >= 0 else 128 - status


if __name__ == '__main__':
    sys.exit(main())
