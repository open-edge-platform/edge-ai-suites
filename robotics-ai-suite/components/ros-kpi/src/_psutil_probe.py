#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
_psutil_probe.py — Minimal, dependency-light system-wide process sampler.

Prints one JSON object per line (JSON-lines) to stdout, one line per sample
tick, replacing pidstat as the CPU/memory data source for monitor_resources.py.

Designed to be invoked either locally (as a subprocess) or on a remote host
via `ssh ... python3 _psutil_probe.py ...`, with its JSON stdout streamed
and written into resource_usage.json (a single JSON document, rewritten
atomically after every tick) -- mirroring how
monitor_resources.py already treats pidstat's stdout, and how gpu_usage.log/
npu_usage.log are written (JSON-lines, one line per tick).

Only depends on the stdlib and psutil (no other project modules), so it can
be scp'd and run standalone on a remote box without the rest of the repo.

Usage:
  python3 _psutil_probe.py --interval 1 --count 0 [--threads] [--no-memory] [--disk-io] [--ctx-switches]

Output line shapes:
  {"event": "start", "ts": "...", "num_cpus": 20}
  {"ts": "...", "processes": [
      {"pid": 1234, "ppid": 1, "name": "...", "cmdline": "...",
       "cpu_pct": 12.3, "core": 6,
       "rss_kb": 12345, "vsz_kb": 54321, "mem_pct": 0.6,
       "io_read_bytes": 4096, "io_write_bytes": 0,   # only with --disk-io;
                                                       # delta bytes since the
                                                       # previous tick, 0 on
                                                       # first sighting
       "ctx_switches_voluntary": 3, "ctx_switches_involuntary": 1,
                                                       # only with --ctx-switches;
                                                       # delta counts since the
                                                       # previous tick, 0 on
                                                       # first sighting. A spike
                                                       # in *involuntary* switches
                                                       # is a privilege-free signal
                                                       # of CPU oversubscription/
                                                       # contention (the process
                                                       # was preempted, not that it
                                                       # voluntarily yielded).
       "threads": [{"tid": 1235, "cpu_pct": 1.1}, ...]   # only with --threads
      }, ...
  ]}
  {"event": "stop", "ts": "..."}
"""

import argparse
import json
import sys
import time
from datetime import datetime

try:
    import psutil
except ImportError:
    print(json.dumps({"event": "error",
                       "message": "psutil not installed (pip install psutil)"}))
    sys.exit(1)


def _proc_snapshot(proc: "psutil.Process", include_memory: bool,
                    include_threads: bool, include_io: bool, include_ctx: bool,
                    thread_prev: dict, io_prev: dict, ctx_prev: dict, now: float) -> dict:
    """
    Best-effort snapshot of one process. Returns {} if it vanished mid-read.

    thread_prev: shared {(pid, tid): (cpu_time_s, wall_ts)} cache used to turn
    each thread's cumulative user+system CPU time into a %CPU delta, the same
    way psutil's own Process.cpu_percent(None) does at the process level
    (psutil doesn't do this automatically for individual threads).

    io_prev: shared {pid: (read_bytes, write_bytes, wall_ts)} cache, same
    delta-since-last-tick pattern as thread_prev, used to turn psutil's
    cumulative io_counters() into per-tick io_read_bytes/io_write_bytes.

    ctx_prev: shared {pid: (voluntary, involuntary, wall_ts)} cache, same
    delta-since-last-tick pattern, used to turn psutil's cumulative
    num_ctx_switches() into per-tick ctx_switches_voluntary/_involuntary
    counts. No elevated privileges required (unlike e.g. perf counters).
    """
    try:
        with proc.oneshot():
            info = {
                'pid':     proc.pid,
                'ppid':    proc.ppid(),
                'name':    proc.name(),
                'cmdline': ' '.join(proc.cmdline()) or proc.name(),
                'cpu_pct': round(proc.cpu_percent(interval=None), 2),
            }
            try:
                info['core'] = proc.cpu_num()
            except (AttributeError, psutil.Error):
                info['core'] = None
            if include_memory:
                try:
                    mem = proc.memory_info()
                    info['rss_kb']  = round(mem.rss / 1024.0, 1)
                    info['vsz_kb']  = round(mem.vms / 1024.0, 1)
                    info['mem_pct'] = round(proc.memory_percent(), 2)
                except psutil.Error:
                    pass
            if include_io:
                try:
                    io = proc.io_counters()
                    prev = io_prev.get(proc.pid)
                    io_prev[proc.pid] = (io.read_bytes, io.write_bytes, now)
                    if prev is None:
                        info['io_read_bytes'] = 0  # first sighting -- no baseline yet
                        info['io_write_bytes'] = 0
                    else:
                        prev_read, prev_write, _prev_ts = prev
                        info['io_read_bytes'] = max(0, io.read_bytes - prev_read)
                        info['io_write_bytes'] = max(0, io.write_bytes - prev_write)
                except (psutil.Error, NotImplementedError):
                    pass  # e.g. AccessDenied -- some kernels/containers restrict io_counters()
            if include_ctx:
                try:
                    ctx = proc.num_ctx_switches()
                    prev = ctx_prev.get(proc.pid)
                    ctx_prev[proc.pid] = (ctx.voluntary, ctx.involuntary, now)
                    if prev is None:
                        info['ctx_switches_voluntary'] = 0  # first sighting -- no baseline yet
                        info['ctx_switches_involuntary'] = 0
                    else:
                        prev_vol, prev_invol, _prev_ts = prev
                        info['ctx_switches_voluntary'] = max(0, ctx.voluntary - prev_vol)
                        info['ctx_switches_involuntary'] = max(0, ctx.involuntary - prev_invol)
                except (psutil.Error, NotImplementedError):
                    pass  # e.g. AccessDenied on some kernels/containers
            if include_threads:
                threads_out = []
                try:
                    for t in proc.threads():
                        cpu_time = t.user_time + t.system_time
                        key = (proc.pid, t.id)
                        prev = thread_prev.get(key)
                        thread_prev[key] = (cpu_time, now)
                        if prev is None:
                            tid_cpu_pct = 0.0  # first sighting -- no baseline yet
                        else:
                            prev_cpu_time, prev_ts = prev
                            wall_delta = now - prev_ts
                            tid_cpu_pct = (0.0 if wall_delta <= 0 else
                                           max(0.0, (cpu_time - prev_cpu_time) / wall_delta * 100.0))
                        threads_out.append({'tid': t.id, 'cpu_pct': round(tid_cpu_pct, 2)})
                except psutil.Error:
                    pass
                info['threads'] = threads_out
        return info
    except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
        return {}


def run(interval: float, count: int, include_memory: bool, include_threads: bool,
        include_io: bool = False, include_ctx: bool = False):
    num_cpus = psutil.cpu_count(logical=True) or 0
    print(json.dumps({'event': 'start', 'ts': datetime.now().isoformat(),
                       'num_cpus': num_cpus}), flush=True)

    # Track live psutil.Process objects across ticks -- cpu_percent(None)
    # computes a delta since *that same object's* last call, so we must
    # reuse the same Process instance per PID rather than recreating it
    # every tick (a fresh Process object always reports 0.0 on its first call).
    tracked: dict = {}

    def _sync_tracked():
        current_pids = set(psutil.pids())
        for pid in current_pids - tracked.keys():
            try:
                proc = psutil.Process(pid)
                proc.cpu_percent(interval=None)  # prime baseline, discarded
                tracked[pid] = proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        for pid in list(tracked.keys() - current_pids):
            del tracked[pid]

    _sync_tracked()

    thread_prev: dict = {}
    io_prev: dict = {}
    ctx_prev: dict = {}
    tick = 0
    try:
        while count <= 0 or tick < count:
            time.sleep(interval)
            _sync_tracked()
            now = time.monotonic()

            processes = []
            for proc in list(tracked.values()):
                snap = _proc_snapshot(proc, include_memory, include_threads, include_io, include_ctx,
                                       thread_prev, io_prev, ctx_prev, now)
                if snap:
                    processes.append(snap)

            print(json.dumps({'ts': datetime.now().isoformat(), 'processes': processes}),
                  flush=True)
            tick += 1
    except KeyboardInterrupt:
        pass
    finally:
        print(json.dumps({'event': 'stop', 'ts': datetime.now().isoformat()}), flush=True)


def main():
    parser = argparse.ArgumentParser(
        description='Minimal psutil-based system-wide process sampler (JSON-lines output).',
    )
    parser.add_argument('--interval', type=float, default=1.0,
                         help='Sampling interval in seconds (default: 1.0)')
    parser.add_argument('--count', type=int, default=0,
                         help='Number of samples (0 = infinite, default: 0)')
    parser.add_argument('--threads', action='store_true',
                         help='Include per-thread CPU breakdown')
    parser.add_argument('--no-memory', action='store_true',
                         help='Skip memory (RSS/VSZ/%%MEM) collection')
    parser.add_argument('--disk-io', action='store_true',
                         help='Include per-process disk I/O (read/write bytes since last tick)')
    parser.add_argument('--ctx-switches', action='store_true',
                         help='Include per-process voluntary/involuntary context-switch counts '
                              'since last tick (a spike in involuntary switches is a '
                              'privilege-free signal of CPU contention/oversubscription)')
    args = parser.parse_args()

    run(interval=max(0.1, args.interval), count=args.count,
        include_memory=not args.no_memory, include_threads=args.threads,
        include_io=args.disk_io, include_ctx=args.ctx_switches)


if __name__ == '__main__':
    main()
