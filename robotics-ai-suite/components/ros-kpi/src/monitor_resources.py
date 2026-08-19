#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Monitor system-wide resource utilization using a psutil-based sampler
(_psutil_probe.py). Samples CPU, memory, and I/O statistics for ALL
processes (not just ROS2-related ones) and writes them to a JSON log,
along with a `# ROS2_PIDS:`-style PID snapshot so downstream consumers can
attribute samples to ROS2 processes post-hoc.
"""

import subprocess
import argparse
import glob
import os
import re
import signal
import sys
import time
import json
import threading
from typing import Optional, Set
from datetime import datetime
from collections import defaultdict

from log_config import get_logger

logger = get_logger(__name__)

# Process name/command-line substrings used to classify a process as "ROS2-related".
# Shared between get_ros2_pids() (live filtering for --list) and downstream report
# post-processing (e.g. visualize_resources.py) that attributes system-wide resource
# samples back to ROS2 vs. the rest of the system.
ROS2_PROCESS_PATTERNS = ['ros2', '_node', 'ros_', 'gazebo', 'rviz']


def is_ros2_process(command_line: str) -> bool:
    """Return True if `command_line` (ps/cmdline Command field) looks ROS2-related."""
    lowered = command_line.lower()
    return any(pattern in lowered for pattern in ROS2_PROCESS_PATTERNS)


# Matches the node-name remap argument ROS2 appends to a node's real argv,
# e.g. '... --ros-args -r __node:=controller_server -r ...' -> 'controller_server'.
_NODE_REMAP_RE = re.compile(r'__node:=(\S+)')


def extract_node_name(command_line: str) -> Optional[str]:
    """
    Best-effort extraction of a ROS2 node name from a process's full command
    line. Returns None if no ``__node:=`` remap argument is present -- many
    nodes (e.g. nav2's controller_server) are launched without one, so
    callers should fall back to the bare executable name in that case.
    """
    match = _NODE_REMAP_RE.search(command_line)
    return match.group(1) if match else None


def get_descendant_pids(root_pid: int, remote_ip: str = None, remote_user: str = 'ubuntu') -> Set[int]:
    """
    Return {root_pid} plus every transitive child of root_pid, by walking the
    system process tree (`ps -eo pid,ppid`).

    This is a far more robust way to identify "every process belonging to
    this ROS2/simulation stack" than name/arg substring matching: every node
    launched via `ros2 launch` is a descendant of that one launch process,
    regardless of whether its own executable name or command-line args
    happen to contain a recognizable ROS2 substring (many don't -- e.g.
    nav2's controller_server is often launched without any --ros-args
    remapping at all, so it matches none of ROS2_PROCESS_PATTERNS).
    """
    if remote_ip:
        ps_cmd = ['ssh', '-T', '-o', 'StrictHostKeyChecking=no',
                  '-o', 'BatchMode=yes',
                  f'{remote_user}@{remote_ip}', 'ps -eo pid,ppid --no-headers']
    else:
        ps_cmd = ['ps', '-eo', 'pid,ppid', '--no-headers']

    try:
        output = subprocess.check_output(
            ps_cmd,
            universal_newlines=True,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Getting process tree: {e}")
        return {root_pid}

    children_of = defaultdict(list)
    all_pids = set()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        all_pids.add(pid)
        children_of[ppid].append(pid)

    if root_pid not in all_pids:
        return {root_pid}  # already exited; nothing to expand

    descendants = {root_pid}
    frontier = [root_pid]
    while frontier:
        pid = frontier.pop()
        for child in children_of.get(pid, []):
            if child not in descendants:
                descendants.add(child)
                frontier.append(child)
    return descendants


def get_ros2_pids(remote_ip: str = None, remote_user: str = 'ubuntu',
                  root_pid: Optional[int] = None) -> Set[int]:
    """Get all process IDs related to ROS2.

    Args:
        remote_ip: IP address of the remote system (None = local)
        remote_user: SSH username for the remote system
        root_pid: PID of the top-level launch process (e.g. `ros2 launch`).
            When given, classification is done by process-tree ancestry
            (get_descendant_pids()) instead of the less reliable name/arg
            substring matching below.

    Known limitation: PIDs are not stable identifiers across a long-running
    session -- the OS can recycle a PID after its original process exits
    (e.g. a crashed/respawned node), so a PID observed late in a run is not
    guaranteed to refer to the same process as when `ros2_pids` was captured.
    """
    if root_pid:
        return get_descendant_pids(root_pid, remote_ip=remote_ip, remote_user=remote_user)

    pids = set()
    try:
        # Find processes with 'ros2' or common ROS2 node patterns in their command line
        if remote_ip:
            ps_cmd = ['ssh', '-T', '-o', 'StrictHostKeyChecking=no',
                      '-o', 'BatchMode=yes',
                      f'{remote_user}@{remote_ip}', 'ps aux']
        else:
            ps_cmd = ['ps', 'aux']
        ps_output = subprocess.check_output(
            ps_cmd,
            universal_newlines=True,
            stdin=subprocess.DEVNULL,
        )

        for line in ps_output.split('\n')[1:]:  # Skip header
            if is_ros2_process(line):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        pids.add(int(parts[1]))
                    except ValueError:
                        continue
    except subprocess.CalledProcessError as e:
        logger.error(f"Getting ROS2 processes: {e}")

    return pids


def get_ros2_pid_node_map(remote_ip: str = None, remote_user: str = 'ubuntu',
                          root_pid: Optional[int] = None) -> dict:
    """
    Return {pid: node_name} for every ROS2-related process, from a single
    `ps -eo pid,ppid,args` snapshot (covers both process-tree ancestry, when
    root_pid is given, and node-name extraction -- no extra subprocess calls
    beyond what get_ros2_pids()/get_descendant_pids() already need).

    Node name resolution per PID:
      1. the `__node:=<name>` remap arg in its command line (extract_node_name())
      2. fall back to the bare executable name (argv[0]'s basename) when no
         remap arg is present -- e.g. nav2's controller_server is often
         launched without one.

    Args:
        remote_ip: IP address of the remote system (None = local)
        remote_user: SSH username for the remote system
        root_pid: PID of the top-level launch process. When given, the
            candidate PID set is every transitive descendant of root_pid
            (process-tree ancestry, like get_descendant_pids()). Falls back
            to is_ros2_process() name/arg substring matching when omitted.

    Known limitation: same PID-reuse caveat as get_ros2_pids() -- the
    resulting {pid: node_name} map is a point-in-time snapshot, so a PID
    that gets recycled by the OS after its original node exits (e.g. a
    crashed/respawned node) will be reported under whatever node name owned
    that PID at snapshot time, not necessarily the node currently running
    under it.
    """
    if remote_ip:
        ps_cmd = ['ssh', '-T', '-o', 'StrictHostKeyChecking=no',
                  '-o', 'BatchMode=yes',
                  f'{remote_user}@{remote_ip}', 'ps -eo pid,ppid,args --no-headers']
    else:
        ps_cmd = ['ps', '-eo', 'pid,ppid,args', '--no-headers']

    try:
        output = subprocess.check_output(
            ps_cmd,
            universal_newlines=True,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Getting process list for node-name attribution: {e}")
        return {}

    cmdline_of = {}
    children_of = defaultdict(list)
    all_pids = set()
    for line in output.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        all_pids.add(pid)
        children_of[ppid].append(pid)
        cmdline_of[pid] = parts[2]

    if root_pid:
        target_pids = {root_pid} if root_pid in all_pids else set()
        frontier = list(target_pids)
        while frontier:
            pid = frontier.pop()
            for child in children_of.get(pid, []):
                if child not in target_pids:
                    target_pids.add(child)
                    frontier.append(child)
        if not target_pids:
            target_pids = {root_pid}
    else:
        target_pids = {pid for pid, cmdline in cmdline_of.items() if is_ros2_process(cmdline)}

    node_map = {}
    for pid in target_pids:
        cmdline = cmdline_of.get(pid, '')
        node_name = extract_node_name(cmdline) or (cmdline.split()[0].rsplit('/', 1)[-1] if cmdline else str(pid))
        node_map[pid] = node_name
    return node_map


def monitor_ros2_resources(interval: int = 1, count: int = 0,
                         show_cpu: bool = True,
                         show_memory: bool = False,
                         show_io: bool = False,
                         show_threads: bool = False,
                         show_ctx: bool = False,
                         log_file: str = None,
                         remote_ip: str = None,
                         remote_user: str = 'ubuntu',
                         root_pid: Optional[int] = None,
                         remote_probe_path: str = '~/ros-kpi/src/_psutil_probe.py'):
    """
    Monitor system-wide resource utilization.

    Uses _psutil_probe.py (a minimal psutil-based sampler) rather than
    pidstat -- pidstat's text output has no structured/JSON mode, and every
    downstream consumer had grown its own fragile positional-column parser
    (thread-vs-PID-mode heuristics, 12h/24h timestamp regex, ANSI
    stripping...) independently. Samples ALL processes system-wide, not just
    ones that looked ROS2-related at a single point-in-time `ps aux` snapshot.
    This avoids missing samples on short runs (nothing to filter against yet)
    and on process-name churn (node restarts). Downstream consumers classify
    each entry as ROS2-related or not via is_ros2_process()/ros2_pids, post-hoc,
    using the full log.

    ``log_file`` is written as a single well-formed JSON document (not
    JSON-lines / not a text log):
    ``{"num_cpus": N, "ros2_pids": [...], "started_at": "...",
    "ended_at": "...", "samples": [{"ts": "...", "processes": [...]}, ...]}``.
    Rewritten atomically (write-to-temp + rename) after every sample so it's
    both always valid JSON and safe for live pollers (e.g.
    prometheus_exporter.py) to re-read mid-run, not only after it ends.
    ``ended_at`` stays null until the run actually finishes.

    A second, ROS2-filtered sidecar document is also written alongside
    ``log_file`` -- same shape and same PID/ROS2 attribution, but each
    sample's ``processes`` list is restricted to PIDs in ``ros2_pids``. Its
    path is derived automatically: ``.../resource_usage.json`` ->
    ``.../resource_usage_ros2.json``.

    Args:
        interval: Sampling interval in seconds
        count: Number of samples (0 for infinite)
        show_cpu: Show CPU statistics (always on; kept for CLI/API compatibility)
        show_memory: Show memory statistics
        show_io: Show per-process disk I/O statistics (read/write bytes since
            last tick, via _psutil_probe.py's --disk-io)
        show_threads: Show per-thread statistics
        show_ctx: Show per-process voluntary/involuntary context-switch counts
            since last tick, via _psutil_probe.py's --ctx-switches. A spike in
            involuntary switches is a privilege-free signal of CPU
            oversubscription/contention (relevant on constrained hardware).
        log_file: Path to the JSON output file (optional)
        remote_ip: IP address of the remote system to monitor (None = local)
        remote_user: SSH username for the remote system
        root_pid: PID of the top-level launch process, for process-tree-based
            ROS2 attribution (see get_ros2_pids()). Falls back to name/arg
            substring matching when omitted.
        remote_probe_path: Path to _psutil_probe.py on the remote host (must
            already be deployed there, e.g. via scp). Ignored when local.
    """
    # monitor_stack.py stops this subprocess via process.terminate() (SIGTERM),
    # not Ctrl+C. Python's default SIGTERM disposition terminates immediately
    # and skips `finally` blocks -- converting it to KeyboardInterrupt lets the
    # existing except/finally cleanup below run (writing the final JSON
    # document) on normal benchmark shutdown, not just Ctrl+C.
    def _raise_keyboard_interrupt(_signum, _frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)

    started_at = datetime.now().isoformat()
    num_cpus = 0
    samples: list = []

    # Derive the ROS2-filtered sidecar path from log_file, e.g.
    # ".../resource_usage.json" -> ".../resource_usage_ros2.json".
    ros2_log_file = None
    if log_file:
        base, ext = os.path.splitext(log_file)
        ros2_log_file = f'{base}_ros2{ext or ".json"}'

    if remote_ip:
        logger.info(f"Targeting remote system: {remote_user}@{remote_ip}")

    logger.info("Monitoring all system processes (psutil probe)\n")

    # ROS2 attribution: the probe's own Command field can't be reliably
    # name-matched (it's the bare executable name; most ROS2 node binaries
    # like controller_server/bt_navigator never contain ROS2_PROCESS_PATTERNS
    # in their own name -- that only reliably matches against `ps aux`'s full
    # command line, e.g. the "--ros-args -r __node:=..." remapping argument).
    # Take a ps-aux-based snapshot now (start of run) and union it with a
    # second snapshot taken at the end (see the `finally` block below) since
    # the ROS2 stack is often still launching at this point -- e.g. nav2's
    # controller_server typically spawns after some startup delay.
    start_ros2_pids = get_ros2_pids(remote_ip=remote_ip, remote_user=remote_user, root_pid=root_pid)
    logger.info(f"Found {len(start_ros2_pids)} ROS2-related processes so far (for attribution, not filtering)\n")

    # Per-node attribution: {pid: node_name}, unioned with an end-of-run
    # snapshot below for the same reason as start_ros2_pids above (nodes
    # that spawn after startup would otherwise be missing a node name).
    start_ros2_node_map = get_ros2_pid_node_map(remote_ip=remote_ip, remote_user=remote_user, root_pid=root_pid)

    # Build the psutil probe command. Its stdout is JSON-lines, one object
    # per sample tick -- parsed here and accumulated into `samples`.
    probe_args = ['--interval', str(max(0.1, float(interval))),
                  '--count', str(max(0, count))]
    if show_threads:
        probe_args.append('--threads')
    if not show_memory:
        probe_args.append('--no-memory')
    if show_io:
        probe_args.append('--disk-io')
    if show_ctx:
        probe_args.append('--ctx-switches')

    if remote_ip:
        # Use -T (no TTY) so SSH never touches local terminal settings.
        remote_cmd = f'python3 {remote_probe_path} ' + ' '.join(probe_args)
        cmd = ['ssh', '-T', '-o', 'StrictHostKeyChecking=no',
               '-o', 'BatchMode=yes',
               f'{remote_user}@{remote_ip}', remote_cmd]
    else:
        local_probe = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '_psutil_probe.py')
        cmd = [sys.executable, local_probe] + probe_args

    logger.info(f"Running: {' '.join(cmd)}\n")
    logger.info("Press Ctrl+C to stop\n")

    def _filter_ros2_samples(ros2_pids: set) -> list:
        """Return `samples` with each sample's processes[] filtered to ROS2 PIDs."""
        filtered = []
        for sample in samples:
            procs = [p for p in sample.get('processes', []) if p.get('pid') in ros2_pids]
            filtered.append({**sample, 'processes': procs})
        return filtered

    def _write_json_atomic(path: str, document: dict):
        """Write-to-temp + rename so readers never observe a partial file."""
        tmp_path = f'{path}.tmp'
        try:
            with open(tmp_path, 'w') as f:
                json.dump(document, f, indent=2, default=str)
            os.replace(tmp_path, path)
        except IOError as e:
            logger.error(f"Writing {path}: {e}")

    def _write_documents(ended_at=None):
        """
        (Re)write both the system-wide log_file and the ROS2-filtered
        ros2_log_file as single, always well-formed JSON documents. Called
        after every sample -- not just at shutdown -- so live consumers that
        re-read the whole file on a poll loop (e.g. prometheus_exporter.py)
        see fresh data during a run, not only after it ends.
        """
        if not log_file:
            return
        document = {
            'num_cpus':      num_cpus,
            'ros2_pids':     sorted(start_ros2_pids),
            'ros2_node_map': {str(pid): start_ros2_node_map[pid] for pid in sorted(start_ros2_node_map)},
            'started_at':    started_at,
            'ended_at':      ended_at,
            'samples':       samples,
        }
        _write_json_atomic(log_file, document)

        ros2_document = {**document, 'samples': _filter_ros2_samples(start_ros2_pids)}
        _write_json_atomic(ros2_log_file, ros2_document)

    process = None
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Redirect stderr to stdout to capture all output
            universal_newlines=True,
            bufsize=1  # Line buffered
        )

        for line in process.stdout:
            print(line, end='')
            line = line.strip()
            if not line.startswith('{'):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get('event') == 'start':
                num_cpus = rec.get('num_cpus', 0) or num_cpus
            elif rec.get('event') not in ('stop', 'error'):
                samples.append(rec)
                _write_documents()

        process.wait()

    except KeyboardInterrupt:
        logger.info("\n\nMonitoring stopped by user.")
        if process is not None:
            process.terminate()
    except subprocess.CalledProcessError as e:
        logger.error(f"Running psutil probe: {e}")
    except FileNotFoundError:
        logger.error("_psutil_probe.py not found (local) or python3/probe missing on remote host!")
        if remote_ip:
            logger.error(f"Make sure {remote_probe_path} is deployed on {remote_user}@{remote_ip} "
                          "(e.g. via scp) and psutil is installed there.")
    finally:
        # Take a second ROS2 PID snapshot at the end of the run and union it
        # with the start-of-run snapshot -- the stack is often still
        # launching at the start (e.g. nav2's controller_server spawns after
        # some startup delay), so relying on only the first snapshot
        # systematically misses processes that start later in the run.
        end_ros2_pids = get_ros2_pids(remote_ip=remote_ip, remote_user=remote_user, root_pid=root_pid)
        start_ros2_pids |= end_ros2_pids

        end_ros2_node_map = get_ros2_pid_node_map(remote_ip=remote_ip, remote_user=remote_user, root_pid=root_pid)
        start_ros2_node_map.update(end_ros2_node_map)

        _write_documents(ended_at=datetime.now().isoformat())


def continuous_monitor(interval: float = 2):
    """
    Continuously monitor ROS2 processes, refreshing the PID list periodically.

    Uses a single long-lived _psutil_probe.py subprocess (system-wide sampler,
    same one monitor_ros2_resources() uses) rather than pidstat -- pidstat has
    no JSON output and required re-invoking it per-iteration with a fresh PID
    list, which also meant every sample was pidstat's own average over its
    own sampling window rather than a live per-tick reading. Re-using the
    same probe process across ticks also means %CPU is computed as a proper
    delta since the previous tick (a fresh subprocess/Process object always
    reports 0.0 on its first sample).
    """
    logger.info("Starting continuous ROS2 monitoring (refreshing process list every ~10 seconds)...")
    logger.info("Press Ctrl+C to stop\n")

    interval = max(0.1, float(interval))
    # Refresh the ROS2 PID list roughly every 10 seconds' worth of ticks.
    refresh_every = max(1, round(10 / interval))

    local_probe = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_psutil_probe.py')
    cmd = [sys.executable, local_probe, '--interval', str(interval), '--count', '0']

    process = None
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )

        ros2_pids: Set[int] = set()
        tick = 0
        for line in process.stdout:
            line = line.strip()
            if not line.startswith('{'):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get('event') in ('start', 'stop', 'error'):
                continue

            if tick % refresh_every == 0:
                ros2_pids = get_ros2_pids()

            if not ros2_pids:
                logger.info("No ROS2 processes found. Waiting...")
                tick += 1
                continue

            procs = [p for p in rec.get('processes', []) if p.get('pid') in ros2_pids]
            if procs:
                logger.info(f"{'PID':<8} {'CPU%':<8} {'RSS(KB)':<10} {'MEM%':<8} {'COMMAND'}")
                logger.info("-" * 80)
                for p in sorted(procs, key=lambda p: -p.get('cpu_pct', 0)):
                    logger.info(f"{p['pid']:<8} {p.get('cpu_pct', 0):<8.1f} "
                                f"{p.get('rss_kb', 0):<10.0f} {p.get('mem_pct', 0):<8.1f} "
                                f"{p.get('cmdline') or p.get('name', '')}")
                logger.info("")
            tick += 1

        process.wait()

    except KeyboardInterrupt:
        logger.info("\n\nMonitoring stopped by user.")
        if process is not None:
            process.terminate()
    except FileNotFoundError:
        logger.error("_psutil_probe.py not found!")


def list_ros2_processes(remote_ip: str = None, remote_user: str = 'ubuntu'):
    """List all currently running ROS2 processes.

    Args:
        remote_ip: IP address of the remote system (None = local)
        remote_user: SSH username for the remote system
    """
    if remote_ip:
        logger.info(f"Scanning for ROS2 processes on {remote_user}@{remote_ip}...\n")
    else:
        logger.info("Scanning for ROS2 processes...\n")

    try:
        if remote_ip:
            ps_cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
                      f'{remote_user}@{remote_ip}', 'ps aux']
        else:
            ps_cmd = ['ps', 'aux']
        ps_output = subprocess.check_output(
            ps_cmd,
            universal_newlines=True
        )

        logger.info(f"{'PID':<8} {'CPU%':<8} {'MEM%':<8} {'COMMAND'}")
        logger.info("-" * 80)

        count = 0
        for line in ps_output.split('\n')[1:]:  # Skip header
            if any(pattern in line.lower() for pattern in ['ros2', '_node', 'ros_', 'gazebo', 'rviz']):
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    pid = parts[1]
                    cpu = parts[2]
                    mem = parts[3]
                    cmd = parts[10]  # Show full command
                    logger.info(f"{pid:<8} {cpu:<8} {mem:<8} {cmd}")
                    count += 1

        logger.info(f"\nFound {count} ROS2-related processes")

    except subprocess.CalledProcessError as e:
        logger.error(f"Listing processes: {e}")


# Candidate paths for a locally installed qmassa binary (xe driver support)
_QMASSA_CANDIDATES = [
    '/usr/bin/qmassa',
    '/usr/local/bin/qmassa',
    os.path.expanduser('~/.cargo/bin/qmassa'),
    os.path.expanduser('~/.local/bin/qmassa'),
]

# sysfs DRM card paths to probe for hwmon temperature data
_DRM_CARDS_TEMP = ['/sys/class/drm/card0', '/sys/class/drm/card1']

# Engine-class patterns (display name → regex on JSON key).
# Covers both i915 names ("Render/3D 0", "Video 0", …) and xe names (rcs, bcs, ccs, vcs, vecs).
import re as _re  # noqa: E402

_ENGINE_CLASS_RE = {
    'Render/3D': _re.compile(r'render|3d|^rcs\d*$',                        _re.I),
    'Blitter':   _re.compile(r'blitter|blt|^bcs\d*$',                      _re.I),
    'Compute':   _re.compile(r'^compute$|^ccs\d*$',                        _re.I),
    'Video':     _re.compile(r'^video$|^vcs\d*$',                          _re.I),
    'VE':        _re.compile(r'videoenhance|video_enhance|ve\b|^vecs\d*$', _re.I),
}


def _find_local_qmassa() -> Optional[str]:
    """Return the path to a locally installed qmassa binary, or None."""
    for p in _QMASSA_CANDIDATES:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    try:
        r = subprocess.run(['which', 'qmassa'],
                           capture_output=True, text=True, timeout=3)
        path = r.stdout.strip()
        if path and os.path.isfile(path):
            return path
    except Exception:
        pass
    return None


def _detect_gpu_driver() -> str:
    """
    Return the active Intel GPU kernel driver name ('xe', 'i915', or 'unknown')
    by reading the driver symlink from DRM sysfs.
    """
    for drv_link in glob.glob('/sys/class/drm/card*/device/driver'):
        try:
            drv = os.path.basename(os.readlink(drv_link))
            if drv in ('xe', 'i915'):
                return drv
        except OSError:
            continue
    return 'unknown'


def probe_gpu_available() -> tuple:
    """
    Probe local Intel GPU monitoring availability without collecting any data.

    Returns ``(available, tool, reason)`` where:
      - ``available`` – True if a usable monitoring tool was found
      - ``tool``      – 'qmassa' or '' when unavailable
      - ``reason``    – human-readable string suitable for log output
    """
    driver = _detect_gpu_driver()
    if driver in ('xe', 'i915'):
        qmassa = _find_local_qmassa()
        if qmassa:
            return True, 'qmassa', f'{driver} driver detected, qmassa at {qmassa}'
        return (False, '',
                f'{driver} driver detected but qmassa not found '
                '(install: make install-qmassa)')
    return False, '', 'no Intel GPU driver found in DRM sysfs'


def probe_npu_available() -> tuple:
    """
    Probe local Intel NPU monitoring availability via sysfs.

    Returns ``(available, reason)`` where:
      - ``available`` – True if the NPU sysfs is present and readable
      - ``reason``    – human-readable string suitable for log output
    """
    busy_file = f'{_NPU_SYSFS}/npu_busy_time_us'
    if not os.path.exists(busy_file):
        return False, f'NPU sysfs not found ({busy_file})'
    try:
        open(busy_file).read()
        return True, f'Intel NPU sysfs accessible at {_NPU_SYSFS}'
    except OSError as exc:
        return False, f'NPU sysfs exists but not readable: {exc}'


def _read_gpu_temp_sysfs(remote_ip: str = None,
                         remote_user: str = 'ubuntu') -> Optional[float]:
    """
    Read Intel GPU temperature (°C) from hwmon sysfs (local or remote).
    Returns None if unavailable.
    """
    if remote_ip:
        cmd = (
            'for f in '
            '/sys/class/drm/card0/device/hwmon/hwmon*/temp*_input '
            '/sys/class/drm/card1/device/hwmon/hwmon*/temp*_input; '
            'do [ -f "$f" ] && cat "$f" && break; done 2>/dev/null'
        )
        try:
            r = _ssh(remote_ip, remote_user, cmd, timeout=6)
            out = r.stdout.strip()
            if out:
                return int(out) / 1000.0
        except Exception:
            pass
        return None
    # local path
    for card in _DRM_CARDS_TEMP:
        for m in sorted(glob.glob(f'{card}/device/hwmon/hwmon*/temp*_input')):
            try:
                return int(open(m).read().strip()) / 1000.0
            except Exception:
                continue
    return None


def _ssh(remote_ip: str, remote_user: str, cmd: str,
         timeout: int = 12) -> subprocess.CompletedProcess:
    """Run a command on the remote via SSH (BatchMode, no tty)."""
    return subprocess.run(
        ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
         '-o', 'StrictHostKeyChecking=no',
         f'{remote_user}@{remote_ip}', cmd],
        capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
    )


def _try_qmassa_local(interval: float = 2.0) -> dict:
    """
    Run qmassa headlessly (-x, -n 2) and parse the JSON output file.

    Requires qmassa installed (``cargo install --locked qmassa``) and the
    running user in the ``video``, ``render``, and ``power`` groups (or root).

    JSON file format (from qmassa app_data.rs):
      Line 1 - version string  e.g. "2.0"
      Line 2 - CliArgs JSON object
      Line 3+ - one AppDataState JSON object per iteration

    Key schema details:
      ``dev_stats.eng_usage``    - dict {engine: [ratio, …]} (0.0-1.0, NOT %)
      ``dev_stats.freqs``        - [[{act_freq: Hz, throttle_reasons: {status: bool}}, …], …]
      ``dev_stats.power``        - [{gpu_cur_power: W, pkg_cur_power: W}, …]
      ``dev_stats.temps``        - [[{name: str, temp: °C}, …], …]  (dGPU only)
      ``dev_stats.mem_info``     - [{smem_used: bytes, vram_used: bytes, …}, …]
      ``clis_stats``             - [{pid, comm, eng_usage: {engine: [ratio,…]}, …}, …]

    Returns a normalized dict (same schema as the rest of the GPU monitoring
    pipeline), or {} on any error (binary missing, permission denied, parse failure …).
    """
    import tempfile

    qmassa_bin = _find_local_qmassa()
    if not qmassa_bin:
        return {}

    interval_ms = max(500, int(interval * 1000))
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tf:
            tmp_path = tf.name

        subprocess.run(
            [qmassa_bin, '-x', '-n', '2', '-m', str(interval_ms), '-t', tmp_path],
            capture_output=True, text=True,
            timeout=interval_ms // 1000 * 3 + 15,
        )

        with open(tmp_path) as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip()]
    except Exception:
        return {}
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # Need at least: version + args + 1 state line
    if len(lines) < 3:
        return {}

    try:
        state = json.loads(lines[-1])   # last AppDataState (most recent iteration)
    except json.JSONDecodeError:
        return {}

    devs = state.get('devs_state', [])
    if not devs:
        return {}
    dev = devs[0]
    dev_stats = dev.get('dev_stats', {})

    def _last(lst):
        return lst[-1] if lst else None

    # ── Engine utilization (ratios → %) ────────────────────────────────────────
    eng_usage_raw = dev_stats.get('eng_usage', {})
    engines_out = {}
    render_busy = 0.0
    for eng_name, usage_list in eng_usage_raw.items():
        last_val = _last(usage_list)
        if last_val is None:
            continue
        busy_pct = round(float(last_val), 1)   # qmassa eng_usage is already in %
        engines_out[eng_name] = {'busy': busy_pct, 'sema': 0.0, 'wait': 0.0}
        if _ENGINE_CLASS_RE['Render/3D'].search(eng_name):
            render_busy = busy_pct

    if not render_busy and engines_out:
        render_busy = max(v['busy'] for v in engines_out.values())

    # ── Frequencies (Hz → MHz) ──────────────────────────────────────────────────
    last_freqs = _last(dev_stats.get('freqs', []))      # Vec<DrmDeviceFreqs>
    act_freq_mhz = 0
    if last_freqs and isinstance(last_freqs, list) and last_freqs:
        gt0 = last_freqs[0]
        act_freq_mhz = int(gt0.get('act_freq', 0) / 1_000_000)

    # ── Power (already in watts) ───────────────────────────────────────────────
    last_power = _last(dev_stats.get('power', []))
    power_gpu_w = 0.0
    power_pkg_w = 0.0
    if isinstance(last_power, dict):
        power_gpu_w = round(float(last_power.get('gpu_cur_power', 0)), 2)
        power_pkg_w = round(float(last_power.get('pkg_cur_power', 0)), 2)

    # ── Temperature (dGPU only, °C already) ───────────────────────────────────
    last_temps = _last(dev_stats.get('temps', []))      # Vec<DrmDeviceTemperature>
    temp_c = None
    if last_temps and isinstance(last_temps, list) and last_temps:
        temp_c = round(float(last_temps[0].get('temp', 0)), 1)

    # ── Memory ────────────────────────────────────────────────────────────────
    last_mem = _last(dev_stats.get('mem_info', []))
    vram_used_mb = 0.0
    smem_used_mb = 0.0
    if isinstance(last_mem, dict):
        vram_used_mb = round(last_mem.get('vram_used', 0) / (1024 * 1024), 1)
        smem_used_mb = round(last_mem.get('smem_used', 0) / (1024 * 1024), 1)

    # ── Per-PID DRM clients ────────────────────────────────────────────────────
    clients = []
    for cst in dev.get('clis_stats', []):
        pid = cst.get('pid', 0)
        name = (cst.get('comm') or '?')[:28]
        cli_engs = {k: 0.0 for k in _ENGINE_CLASS_RE}
        total_busy = 0.0
        for eng_name, usage_list in cst.get('eng_usage', {}).items():
            last_val = _last(usage_list)
            if last_val is None:
                continue
            busy = float(last_val)   # qmassa eng_usage is already in %
            for cls_name, pat in _ENGINE_CLASS_RE.items():
                if pat.search(eng_name):
                    cli_engs[cls_name] = cli_engs.get(cls_name, 0.0) + busy
                    total_busy += busy
                    break
        clients.append({'pid': pid, 'name': name,
                        'engines': cli_engs, 'total': round(total_busy, 2)})
    clients.sort(key=lambda x: x['total'], reverse=True)

    result = {
        'source':       'qmassa',
        'busy_pct':     round(render_busy, 1),
        'act_freq_mhz': act_freq_mhz,
        'power_gpu_w':  power_gpu_w,
        'power_pkg_w':  power_pkg_w,
        'engines':      engines_out,
        'clients':      clients,
        'period_ms':    float(interval_ms),
        'drv_name':     dev.get('drv_name', 'xe'),
        'vram_used_mb': vram_used_mb,
        'smem_used_mb': smem_used_mb,
    }
    if temp_c is not None:
        result['temp_c'] = temp_c
    return result


def _read_sysfs_gpu(remote_ip: str = None, remote_user: str = 'ubuntu') -> dict:
    """
    Read Intel GPU metrics from sysfs (no PMU / no root required).

    Returns a dict with keys:
        busy_pct       – estimated GPU busy % derived from RC6 residency delta
        act_freq_mhz   – actual (measured) GT frequency
        cur_freq_mhz   – current requested GT frequency
        max_freq_mhz   – maximum configured GT frequency
        rc6_ms_per_s   – raw RC6 idle ms in the last second (for debugging)
        gt_count        – number of GTs found
    Returns an empty dict on any failure.
    """
    _CARD = '/sys/class/drm/card1'

    def _ssh_read(paths: list) -> dict:
        """Read multiple sysfs files in one SSH call, return {path: value}."""
        remote_cmd = ' && '.join(f'echo {p}=$(cat {p} 2>/dev/null)' for p in paths)
        try:
            r = _ssh(remote_ip, remote_user, remote_cmd, timeout=8)
            out = {}
            for line in r.stdout.splitlines():
                if '=' in line:
                    k, _, v = line.partition('=')
                    out[k.strip()] = v.strip()
            return out
        except Exception:
            return {}

    def _local_read(paths: list) -> dict:
        out = {}
        for p in paths:
            try:
                out[p] = open(p).read().strip()
            except Exception:
                out[p] = ''
        return out

    _read = _ssh_read if remote_ip else _local_read

    # Discover GT count
    if remote_ip:
        try:
            r = _ssh(remote_ip, remote_user,
                     f'ls {_CARD}/gt/ 2>/dev/null | grep -c "^gt[0-9]"', timeout=8)
            gt_count = int(r.stdout.strip() or '1')
        except Exception:
            gt_count = 1
    else:
        import glob  # noqa: E402
        gt_count = len(glob.glob(f'{_CARD}/gt/gt*'))
        if gt_count == 0:
            gt_count = 1

    rc6_paths = [f'{_CARD}/gt/gt{i}/rc6_residency_ms' for i in range(gt_count)]
    freq_paths = [
        f'{_CARD}/gt_act_freq_mhz',
        f'{_CARD}/gt_cur_freq_mhz',
        f'{_CARD}/gt_max_freq_mhz',
    ]

    # First RC6 sample
    t0 = time.monotonic()
    s0 = _read(rc6_paths + freq_paths)
    time.sleep(1.0)
    t1 = time.monotonic()
    s1 = _read(rc6_paths)

    elapsed_ms = (t1 - t0) * 1000.0
    if elapsed_ms < 1:
        return {}

    # Average RC6 idle across all GTs
    rc6_idle_ms = 0.0
    for p in rc6_paths:
        try:
            rc6_idle_ms += float(s1.get(p, '0') or '0') - float(s0.get(p, '0') or '0')
        except ValueError:
            pass
    rc6_idle_ms /= max(gt_count, 1)
    rc6_idle_ms = max(0.0, min(rc6_idle_ms, elapsed_ms))

    busy_pct = round((1.0 - rc6_idle_ms / elapsed_ms) * 100.0, 1)

    def _int(k):
        try:
            return int(s0.get(k, '0') or '0')
        except ValueError:
            return 0

    return {
        'busy_pct':     busy_pct,
        'act_freq_mhz': _int(f'{_CARD}/gt_act_freq_mhz'),
        'cur_freq_mhz': _int(f'{_CARD}/gt_cur_freq_mhz'),
        'max_freq_mhz': _int(f'{_CARD}/gt_max_freq_mhz'),
        'rc6_ms_per_s': round(rc6_idle_ms, 1),
        'gt_count':     gt_count,
    }


def monitor_gpu(interval: float = 2.0,
                gpu_log: str = None,
                remote_ip: str = None,
                remote_user: str = 'ubuntu',
                stop_event: threading.Event = None):
    """
    Poll Intel GPU metrics at `interval` seconds and write JSON-lines to
    `gpu_log`.  Uses qmassa locally (rich data: per-engine busy%,
    power, VRAM, per-PID); falls back to sysfs RC6 residency for remote
    sessions or when qmassa is unavailable.
    Runs until stop_event is set or KeyboardInterrupt.
    """
    log_fp = None
    if gpu_log:
        log_fp = open(gpu_log, 'a')
        log_fp.write(json.dumps({'event': 'start',
                                  'ts': datetime.now().isoformat()}) + '\n')
        log_fp.flush()

    if stop_event is None:
        stop_event = threading.Event()

    # Quick sanity check — skip if no DRI device present
    if remote_ip:
        try:
            r = _ssh(remote_ip, remote_user,
                     'ls /sys/class/drm/card* 2>/dev/null | grep -qE "card[0-9]" && echo ok || echo missing',
                     timeout=8)
            if 'missing' in r.stdout:
                logger.info('[GPU] No Intel GPU sysfs found on remote — GPU monitoring skipped.')
                return
        except Exception:
            logger.info('[GPU] Could not reach remote for GPU check — skipping.')
            return

    # Probe: try qmassa first; fall back to sysfs if unavailable.
    use_qmassa = False
    if not remote_ip:
        probe = _try_qmassa_local(interval=max(interval, 1.0))
        if probe:
            use_qmassa = True
            drv = probe.get('drv_name', 'xe')
            logger.info(f'[GPU] Using qmassa ({drv} driver, engines/power/per-PID)  '
                  f'interval={interval}s')
        else:
            qmassa_bin = _find_local_qmassa()
            if qmassa_bin:
                logger.info(f'[GPU] qmassa found at {qmassa_bin} but probe failed '
                      f'(check video/render/power group membership).')
            else:
                logger.info('[GPU] qmassa not found — falling back to sysfs monitoring.')
                logger.info('[GPU] Install:  make install-qmassa')

    if not use_qmassa:
        logger.info(f'[GPU] Monitoring Intel GPU via sysfs (interval={interval}s)...')

    def _fmt_rich(stats: dict) -> str:
        engs     = stats.get('engines', {})
        render_b = stats.get('busy_pct', 0.0)
        src      = stats.get('source', '')
        pwr      = f"  ⚡{stats['power_gpu_w']:.1f}W" if stats.get('power_gpu_w') else ''
        temp     = (f"  🌡{stats['temp_c']:.0f}°C"
                    if stats.get('temp_c') is not None else '')
        # Build per-engine summary  e.g.  Render/3D:28.1%  Compute:12.0%
        eng_parts = []
        for cls, pat in _ENGINE_CLASS_RE.items():
            for k, v in engs.items():
                if pat.search(k) and isinstance(v, dict):
                    eng_parts.append(f'{cls}:{v.get("busy", 0.0):.1f}%')
                    break
        eng_str = '  ' + '  '.join(eng_parts) if eng_parts else ''
        clients = stats.get('clients', [])
        pid_str = ''
        if clients:
            top = clients[0]
            pid_str = f'  top-pid={top["pid"]}({top["name"]}):{top["total"]:.1f}%'
        rc6_str = ''
        return (f"[GPU/{src}] busy={render_b:5.1f}%  "
                f"freq={stats.get('act_freq_mhz', 0)} MHz"
                f"{rc6_str}{pwr}{temp}{eng_str}{pid_str}")

    def _fmt_sysfs(stats: dict) -> str:
        return (f"[GPU] busy={stats['busy_pct']:5.1f}%  "
                f"freq={stats['act_freq_mhz']}/{stats.get('max_freq_mhz', 0)} MHz")

    try:
        while not stop_event.is_set():
            t0 = time.monotonic()
            if use_qmassa:
                stats = _try_qmassa_local(interval=interval)
                if not stats:
                    stats = _read_sysfs_gpu()
            else:
                stats = _read_sysfs_gpu(remote_ip=remote_ip, remote_user=remote_user)

            if stats:
                ts = datetime.now().isoformat()
                # Attach temperature from hwmon sysfs when not already present
                # (qmassa populates temp_c for dGPUs; sysfs path always supplements)
                if stats.get('temp_c') is None:
                    temp_c = _read_gpu_temp_sysfs(
                        remote_ip=remote_ip, remote_user=remote_user)
                    if temp_c is not None:
                        stats['temp_c'] = round(temp_c, 1)
                # Supplement frequency from sysfs when qmassa on i915 reports 0
                # (i915 fdinfo does not expose GT frequency; xe driver does)
                if stats.get('act_freq_mhz', 0) == 0 and stats.get('drv_name') == 'i915':
                    try:
                        import glob as _glob  # noqa: E402
                        _cards = sorted(_glob.glob('/sys/class/drm/card[0-9]'))
                        _card = _cards[-1] if _cards else '/sys/class/drm/card0'
                        with open(f'{_card}/gt_act_freq_mhz') as _f:
                            _act = int(_f.read().strip())
                        if _act > 0:
                            stats['act_freq_mhz'] = _act
                            try:
                                with open(f'{_card}/gt_max_freq_mhz') as _f:
                                    stats['max_freq_mhz'] = int(_f.read().strip())
                            except (OSError, ValueError):
                                pass
                    except (OSError, ValueError):
                        pass
                record = {'ts': ts, **stats}
                line = json.dumps(record)
                src = stats.get('source', '')
                logger.info(_fmt_rich(stats) if src == 'qmassa' else _fmt_sysfs(stats))
                if log_fp:
                    log_fp.write(line + '\n')
                    log_fp.flush()

            # qmassa already consumed ~interval seconds internally;
            # sysfs consumes 1 s.  Sleep the remainder to avoid drift.
            elapsed = time.monotonic() - t0
            remaining = interval - elapsed
            if remaining > 0.05:
                stop_event.wait(timeout=remaining)
    except KeyboardInterrupt:
        pass
    finally:
        if log_fp:
            log_fp.write(json.dumps({'event': 'stop',
                                      'ts': datetime.now().isoformat()}) + '\n')
            log_fp.close()
        logger.info('[GPU] GPU monitor stopped.')


# ── Intel NPU monitoring (sysfs / SSH) ───────────────────────────────────────
_NPU_SYSFS = '/sys/class/accel/accel0/device'
_NPU_SYSFS_FILES = [
    'npu_busy_time_us',
    'npu_current_frequency_mhz',
    'npu_max_frequency_mhz',
    'npu_memory_utilization',
]


def _read_sysfs_npu(remote_ip: str = None, remote_user: str = 'ubuntu') -> dict:
    """
    Read Intel NPU metrics from sysfs (local or remote via SSH).

    Busy % is derived by sampling ``npu_busy_time_us`` twice and computing:
        busy% = delta_busy_us / (delta_wall_us) * 100

    Returns a dict with:
        busy_pct          - NPU compute utilization %
        cur_freq_mhz      - current clock frequency
        max_freq_mhz      - maximum clock frequency
        memory_used_mb    - memory utilization (bytes → MB)
    Returns an empty dict on any failure.
    """

    def _read_all() -> dict:
        if remote_ip:
            cmd = ' && '.join(f'echo {f}=$(cat {_NPU_SYSFS}/{f} 2>/dev/null)' for f in _NPU_SYSFS_FILES)
            try:
                r = _ssh(remote_ip, remote_user, cmd, timeout=8)
                out = {}
                for line in r.stdout.splitlines():
                    if '=' in line:
                        k, _, v = line.partition('=')
                        out[k.strip()] = v.strip()
                return out
            except Exception:
                return {}
        else:
            out = {}
            for f in _NPU_SYSFS_FILES:
                try:
                    out[f] = open(f'{_NPU_SYSFS}/{f}').read().strip()
                except Exception:
                    out[f] = ''
            return out

    def _int(d, key, default=0):
        try:
            return int(d.get(key, default) or default)
        except (ValueError, TypeError):
            return default

    t0 = time.monotonic()
    s0 = _read_all()
    time.sleep(1.0)
    t1 = time.monotonic()
    s1 = _read_all()

    if not s0 or not s1:
        return {}

    elapsed_us = (t1 - t0) * 1_000_000.0
    busy0 = _int(s0, 'npu_busy_time_us')
    busy1 = _int(s1, 'npu_busy_time_us')
    delta_busy = max(0, busy1 - busy0)
    busy_pct = round(min(delta_busy / elapsed_us * 100.0, 100.0), 1) if elapsed_us > 0 else 0.0

    mem_bytes = _int(s1, 'npu_memory_utilization')
    cur_freq = _int(s1, 'npu_current_frequency_mhz')
    max_freq = _int(s1, 'npu_max_frequency_mhz')
    result = {
        'busy_pct':       busy_pct,
        'cur_freq_mhz':   cur_freq,
        'max_freq_mhz':   max_freq,
        'memory_used_mb': round(mem_bytes / (1024 * 1024), 1),
    }
    return result


def monitor_npu(interval: float = 2.0,
                npu_log: str = None,
                remote_ip: str = None,
                remote_user: str = 'ubuntu',
                stop_event: threading.Event = None):
    """
    Poll Intel NPU metrics at ``interval`` seconds and write JSON-lines to
    ``npu_log``.  Reads sysfs (local or remote); no special capabilities
    required.  Runs until stop_event is set or KeyboardInterrupt.
    """
    log_fp = None
    if npu_log:
        log_fp = open(npu_log, 'a')
        log_fp.write(json.dumps({'event': 'start',
                                  'ts': datetime.now().isoformat()}) + '\n')
        log_fp.flush()

    if stop_event is None:
        stop_event = threading.Event()

    # Quick sanity check — skip if no NPU accel device present
    if remote_ip:
        try:
            r = _ssh(remote_ip, remote_user,
                     f'test -d {_NPU_SYSFS} && echo ok || echo missing', timeout=8)
            if 'missing' in r.stdout:
                logger.info('[NPU] No Intel NPU sysfs found on remote — NPU monitoring skipped.')
                return
        except Exception:
            logger.info('[NPU] Could not reach remote for NPU check — skipping.')
            return
    else:
        if not os.path.isdir(_NPU_SYSFS):
            logger.info('[NPU] No Intel NPU sysfs found locally — NPU monitoring skipped.')
            return

    logger.info(f'[NPU] Monitoring Intel NPU via sysfs (interval={interval}s)...')

    try:
        while not stop_event.is_set():
            t0 = time.monotonic()
            stats = _read_sysfs_npu(remote_ip=remote_ip, remote_user=remote_user)
            if stats:
                ts = datetime.now().isoformat()
                record = {'ts': ts, **stats}
                pwr_str  = (f"  ⚡{stats['power_w']:.2f}W"
                            if 'power_w' in stats else '')
                temp_str = (f"  🌡{stats['temp_c']}°C"
                            if 'temp_c' in stats else '')
                bw_str   = (f"  bw={stats['bw_mbps']:.1f} MB/s"
                            if 'bw_mbps' in stats else '')
                logger.info(f"[NPU] busy={stats['busy_pct']:5.1f}%  "
                      f"freq={stats['cur_freq_mhz']}/{stats['max_freq_mhz']} MHz  "
                      f"mem={stats['memory_used_mb']:.1f} MB"
                      f"{pwr_str}{temp_str}{bw_str}")
                if log_fp:
                    log_fp.write(json.dumps(record) + '\n')
                    log_fp.flush()

            # _read_sysfs_npu already sleeps ~1s for delta sampling.
            # Sleep the remainder of the interval.
            elapsed = time.monotonic() - t0
            remaining = interval - elapsed
            if remaining > 0.05:
                stop_event.wait(timeout=remaining)
    except KeyboardInterrupt:
        pass
    finally:
        if log_fp:
            log_fp.write(json.dumps({'event': 'stop',
                                      'ts': datetime.now().isoformat()}) + '\n')
            log_fp.close()
        logger.info('[NPU] NPU monitor stopped.')


def main():
    parser = argparse.ArgumentParser(
        description='Monitor ROS2 processes resource utilization using a psutil-based sampler',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all ROS2 processes
  %(prog)s --list

  # Monitor CPU usage (default)
  %(prog)s

  # Monitor CPU and memory usage with logging
  %(prog)s --memory --log ros2_monitor.json

  # Monitor with 2 second interval
  %(prog)s --interval 2

  # Monitor for 10 samples then stop
  %(prog)s --count 10

  # Monitor I/O statistics
  %(prog)s --io

  # Monitor context-switch counts (contention diagnostics)
  %(prog)s --ctx-switches

  # Monitor with thread details
  %(prog)s --threads

  # Continuous monitoring (auto-refresh process list)
  %(prog)s --continuous
        """
    )

    parser.add_argument('-l', '--list', action='store_true',
                        help='List all ROS2 processes and exit')
    parser.add_argument('-i', '--interval', type=float, default=1,
                        help='Sampling interval in seconds (default: 1)')
    parser.add_argument('-c', '--count', type=int, default=0,
                        help='Number of samples (default: 0 = infinite)')
    parser.add_argument('-m', '--memory', action='store_true',
                        help='Show memory statistics')
    parser.add_argument('-d', '--io', action='store_true',
                        help='Show per-process disk I/O statistics (read/write bytes since last tick)')
    parser.add_argument('-x', '--ctx-switches', action='store_true',
                        help='Show per-process voluntary/involuntary context-switch counts since '
                             'last tick (involuntary spikes indicate CPU contention)')
    parser.add_argument('-t', '--threads', action='store_true',
                        help='Show per-thread statistics')
    parser.add_argument('--continuous', action='store_true',
                        help='Continuously monitor with auto-refresh of process list')
    parser.add_argument('--log', type=str, default=None,
                        help='Path to log file (will append if exists)')
    parser.add_argument('--gpu', action='store_true',
                        help='Also collect Intel GPU metrics via sysfs (writes gpu_usage.log alongside --log)')
    parser.add_argument('--gpu-log', type=str, default=None,
                        help='Explicit path for GPU JSON-lines log (auto-derived from --log if omitted)')
    parser.add_argument('--npu', action='store_true',
                        help='Also collect Intel NPU metrics via sysfs (writes npu_usage.log alongside --log)')
    parser.add_argument('--npu-log', type=str, default=None,
                        help='Explicit path for NPU JSON-lines log (auto-derived from --log if omitted)')
    parser.add_argument('--remote-ip', type=str, default=None,
                        help='IP address of the remote system running the ROS2 pipeline')
    parser.add_argument('--remote-user', type=str, default='ubuntu',
                        help='SSH username for the remote system (default: ubuntu)')
    parser.add_argument('--remote-probe-path', type=str, default='~/ros-kpi/src/_psutil_probe.py',
                        help='Path to _psutil_probe.py on the remote host (must already be '
                             'deployed there, e.g. via scp). Ignored when --remote-ip is not set.')
    parser.add_argument('--root-pid', type=int, default=None,
                        help='PID of the top-level launch process (e.g. `ros2 launch`). '
                             'Used to classify ROS2 processes by process-tree ancestry '
                             'for resource attribution, instead of name/arg matching.')
    parser.add_argument('--check-hw', action='store_true',
                        help='Probe local GPU and NPU monitoring availability then exit')

    args = parser.parse_args()

    if args.check_hw:
        driver = _detect_gpu_driver()
        gpu_avail, gpu_tool, gpu_reason = probe_gpu_available()
        npu_avail, npu_reason = probe_npu_available()
        logger.info('\u2554' + '\u2550' * 64 + '\u2557')
        logger.info('\u2551' + '  Hardware Monitoring Probe'.ljust(64) + '\u2551')
        logger.info('\u255a' + '\u2550' * 64 + '\u255d\n')
        logger.info(f'[GPU] Kernel driver : {driver}')
        if gpu_avail:
            logger.info(f'[GPU] Status        : \u2705 AVAILABLE  (tool: {gpu_tool})')
        else:
            logger.info('[GPU] Status        : \u274c UNAVAILABLE')
        logger.info(f'[GPU] Detail        : {gpu_reason}\n')
        logger.info(f'[NPU] Sysfs path    : {_NPU_SYSFS}')
        if npu_avail:
            logger.info('[NPU] Status        : \u2705 AVAILABLE')
        else:
            logger.info('[NPU] Status        : \u274c UNAVAILABLE')
        logger.info(f'[NPU] Detail        : {npu_reason}\n')
        logger.info('Auto-monitoring summary:')
        logger.info(f'  GPU will be monitored   : {"yes" if gpu_avail else "no"}')
        logger.info(f'  NPU will be monitored   : {"yes" if npu_avail else "no"}')
        import sys as _sys
        _sys.exit(0 if (gpu_avail or npu_avail) else 1)

    if args.list:
        list_ros2_processes(remote_ip=args.remote_ip, remote_user=args.remote_user)
        return

    if args.continuous:
        continuous_monitor(args.interval)
        return

    # Default to showing CPU if nothing else specified
    show_cpu = True

    _gpu_stop = None
    if args.gpu:
        gpu_log = args.gpu_log
        if gpu_log is None and args.log:
            gpu_log = os.path.join(os.path.dirname(os.path.abspath(args.log)), 'gpu_usage.log')
        if gpu_log is None:
            gpu_log = 'gpu_usage.log'
        _gpu_stop = threading.Event()
        _gpu_thread = threading.Thread(
            target=monitor_gpu,
            args=(args.interval, gpu_log, args.remote_ip, args.remote_user, _gpu_stop),
            daemon=True,
        )
        _gpu_thread.start()

    _npu_stop = None
    if args.npu:
        npu_log = args.npu_log
        if npu_log is None and args.log:
            npu_log = os.path.join(os.path.dirname(os.path.abspath(args.log)), 'npu_usage.log')
        if npu_log is None:
            npu_log = 'npu_usage.log'
        _npu_stop = threading.Event()
        _npu_thread = threading.Thread(
            target=monitor_npu,
            args=(args.interval, npu_log, args.remote_ip, args.remote_user, _npu_stop),
            daemon=True,
        )
        _npu_thread.start()

    try:
        monitor_ros2_resources(
            interval=args.interval,
            count=args.count,
            show_cpu=show_cpu,
            show_memory=args.memory,
            show_io=args.io,
            show_threads=args.threads,
            show_ctx=args.ctx_switches,
            log_file=args.log,
            remote_ip=args.remote_ip,
            remote_user=args.remote_user,
            root_pid=args.root_pid,
            remote_probe_path=args.remote_probe_path,
        )
    finally:
        if _gpu_stop is not None:
            _gpu_stop.set()
        if _npu_stop is not None:
            _npu_stop.set()


if __name__ == '__main__':
    main()
