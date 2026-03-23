#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Monitor ROS2 processes resource utilization using pidstat.
This script filters and displays CPU, memory, and I/O statistics for ROS2-related processes.
"""

import subprocess
import argparse
import glob
import os
import sys
import time
import re
import json
import threading
from typing import List, Optional, Set
from datetime import datetime


def get_ros2_pids(remote_ip: str = None, remote_user: str = 'ubuntu') -> Set[int]:
    """Get all process IDs related to ROS2.

    Args:
        remote_ip: IP address of the remote system (None = local)
        remote_user: SSH username for the remote system
    """
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
            if any(pattern in line.lower() for pattern in ['ros2', '_node', 'ros_', 'gazebo', 'rviz']):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        pids.add(int(parts[1]))
                    except ValueError:
                        continue
    except subprocess.CalledProcessError as e:
        print(f"Error getting ROS2 processes: {e}", file=sys.stderr)
    
    return pids


def monitor_ros2_pidstat(interval: int = 1, count: int = 0,
                         show_cpu: bool = True,
                         show_memory: bool = False,
                         show_io: bool = False,
                         show_threads: bool = False,
                         log_file: str = None,
                         remote_ip: str = None,
                         remote_user: str = 'ubuntu'):
    """
    Monitor ROS2 processes using pidstat.

    Args:
        interval: Sampling interval in seconds
        count: Number of samples (0 for infinite)
        show_cpu: Show CPU statistics
        show_memory: Show memory statistics
        show_io: Show I/O statistics
        show_threads: Show per-thread statistics
        log_file: Path to log file (optional)
        remote_ip: IP address of the remote system to monitor (None = local)
        remote_user: SSH username for the remote system
    """
    
    # Open log file if specified
    log_fp = None
    if log_file:
        try:
            log_fp = open(log_file, 'a')
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_fp.write(f"\n{'='*80}\n")
            log_fp.write(f"Monitoring started at {timestamp}\n")
            log_fp.write(f"{'='*80}\n\n")
            log_fp.flush()
        except IOError as e:
            print(f"Error opening log file: {e}", file=sys.stderr)
            log_file = None
    
    # Countdown before scanning
    if remote_ip:
        print(f"Targeting remote system: {remote_user}@{remote_ip}")
    print("Starting in...")
    for i in range(5, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    print("Scanning for ROS2 processes...")
    ros2_pids = get_ros2_pids(remote_ip=remote_ip, remote_user=remote_user)
    
    if not ros2_pids:
        msg = "No ROS2 processes found!\nMake sure ROS2 nodes are running."
        print(msg)
        if log_fp:
            log_fp.write(msg + "\n")
            log_fp.close()
        return
    
    msg = f"Found {len(ros2_pids)} ROS2-related processes\n"
    print(msg)
    if log_fp:
        log_fp.write(msg + "\n")
        log_fp.flush()
    
    # Build pidstat arguments
    pidstat_args = ['pidstat']
    
    # Add options based on flags
    if show_cpu:
        pidstat_args.append('-u')  # CPU statistics
    if show_memory:
        pidstat_args.append('-r')  # Memory statistics
    if show_io:
        pidstat_args.append('-d')  # I/O statistics
    if show_threads:
        pidstat_args.append('-t')  # Show threads
    
    # Add process filter
    pidstat_args.extend(['-p', ','.join(map(str, ros2_pids))])
    
    # Add human-readable output
    pidstat_args.append('-h')
    
    # Add interval (pidstat only accepts integers)
    interval_int = max(1, int(interval))
    if interval < 1 and interval != int(interval):
        print(f"Warning: pidstat only accepts integer intervals. Rounding {interval}s to {interval_int}s")
        if log_fp:
            log_fp.write(f"Warning: pidstat only accepts integer intervals. Rounding {interval}s to {interval_int}s\n")
            log_fp.flush()
    pidstat_args.append(str(interval_int))
    
    # Add count if specified
    if count > 0:
        pidstat_args.append(str(count))
    
    # Build final command – prefix with ssh when targeting a remote host
    if remote_ip:
        # Use -T (no TTY) so SSH never touches local terminal settings.
        # COLUMNS=250 tells pidstat how wide to format output without needing stty.
        pidstat_cmd = ' '.join(pidstat_args)
        remote_cmd = f'COLUMNS=250 {pidstat_cmd}'
        cmd = ['ssh', '-T', '-o', 'StrictHostKeyChecking=no',
               '-o', 'BatchMode=yes',
               f'{remote_user}@{remote_ip}', remote_cmd]
    else:
        cmd = pidstat_args
    
    cmd_str = f"Running: {' '.join(cmd)}\n"
    print(cmd_str)
    print("Press Ctrl+C to stop\n")
    if log_fp:
        log_fp.write(cmd_str + "\n")
        log_fp.flush()
    
    try:
        # Run pidstat and stream output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Redirect stderr to stdout to capture all output
            universal_newlines=True,
            bufsize=1  # Line buffered
        )
        
        for line in process.stdout:
            print(line, end='')
            if log_fp:
                log_fp.write(line)
                log_fp.flush()
        
        process.wait()
        
    except KeyboardInterrupt:
        msg = "\n\nMonitoring stopped by user."
        print(msg)
        if log_fp:
            log_fp.write(msg + "\n")
        process.terminate()
    except subprocess.CalledProcessError as e:
        print(f"Error running pidstat: {e}", file=sys.stderr)
        print("Make sure pidstat is installed (sudo apt install sysstat)", file=sys.stderr)
    except FileNotFoundError:
        print("Error: pidstat not found!", file=sys.stderr)
        print("Install it with: sudo apt install sysstat", file=sys.stderr)
    finally:
        if log_fp:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_fp.write(f"\nMonitoring ended at {timestamp}\n")
            log_fp.close()


def continuous_monitor(interval: int = 2):
    """Continuously monitor ROS2 processes, refreshing the PID list periodically."""
    print("Starting continuous ROS2 monitoring (refreshing process list every 10 seconds)...")
    print("Press Ctrl+C to stop\n")
    
    try:
        iteration = 0
        while True:
            # Refresh PID list every 5 iterations (10 seconds with 2 sec interval)
            if iteration % 5 == 0:
                ros2_pids = get_ros2_pids()
                if not ros2_pids:
                    print("No ROS2 processes found. Waiting...")
                    time.sleep(interval)
                    iteration += 1
                    continue
            
            # Run pidstat for this iteration
            cmd = ['pidstat', '-u', '-r', '-h', '-p', ','.join(map(str, ros2_pids)), str(interval), '1']
            
            try:
                output = subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.DEVNULL)
                print(output)
            except subprocess.CalledProcessError:
                pass  # Ignore errors, processes might have died
            
            iteration += 1
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")


def list_ros2_processes(remote_ip: str = None, remote_user: str = 'ubuntu'):
    """List all currently running ROS2 processes.

    Args:
        remote_ip: IP address of the remote system (None = local)
        remote_user: SSH username for the remote system
    """
    if remote_ip:
        print(f"Scanning for ROS2 processes on {remote_user}@{remote_ip}...\n")
    else:
        print("Scanning for ROS2 processes...\n")

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
        
        print(f"{'PID':<8} {'CPU%':<8} {'MEM%':<8} {'COMMAND'}")
        print("-" * 80)
        
        count = 0
        for line in ps_output.split('\n')[1:]:  # Skip header
            if any(pattern in line.lower() for pattern in ['ros2', '_node', 'ros_', 'gazebo', 'rviz']):
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    pid = parts[1]
                    cpu = parts[2]
                    mem = parts[3]
                    cmd = parts[10]  # Show full command
                    print(f"{pid:<8} {cpu:<8} {mem:<8} {cmd}")
                    count += 1
        
        print(f"\nFound {count} ROS2-related processes")
        
    except subprocess.CalledProcessError as e:
        print(f"Error listing processes: {e}", file=sys.stderr)


_IGT_BIN = '~/.local/bin/intel_gpu_top'  # default path on the remote machine

# Candidate paths for a locally installed intel_gpu_top binary
_LOCAL_IGT_CANDIDATES = [
    '/usr/bin/intel_gpu_top',
    '/usr/local/bin/intel_gpu_top',
    os.path.expanduser('~/.local/bin/intel_gpu_top'),
]

# sysfs DRM card paths to probe for hwmon temperature data
_DRM_CARDS_TEMP = ['/sys/class/drm/card0', '/sys/class/drm/card1']

# Engine-class patterns (display name → regex on JSON key)
import re as _re
_ENGINE_CLASS_RE = {
    'Render/3D': _re.compile(r'render|3d',                      _re.I),
    'Blitter':   _re.compile(r'blitter|blt',                    _re.I),
    'Video':     _re.compile(r'^video$',                        _re.I),
    'VE':        _re.compile(r'videoenhance|video_enhance|ve\b', _re.I),
}


def _find_local_igt() -> Optional[str]:
    """Return the path to a locally installed intel_gpu_top binary, or None."""
    for p in _LOCAL_IGT_CANDIDATES:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    try:
        r = subprocess.run(['which', 'intel_gpu_top'],
                           capture_output=True, text=True, timeout=3)
        path = r.stdout.strip()
        if path and os.path.isfile(path):
            return path
    except Exception:
        pass
    return None


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


def _parse_igt_clients(sample: dict) -> list:
    """
    Extract per-PID GPU utilisation from intel_gpu_top JSON "clients" field
    (available in intel_gpu_top ≥ 1.27).  Returns a list sorted by total
    GPU busy % descending:
        [{ pid, name, engines: {class: busy%}, total }, …]
    """
    clients_raw = sample.get('clients', {})
    if not clients_raw:
        return []
    items = list(clients_raw.values()) if isinstance(clients_raw, dict) \
            else list(clients_raw)
    result = []
    for c in items:
        if not isinstance(c, dict):
            continue
        pid_raw = c.get('pid') or c.get('id')
        name = (c.get('name') or c.get('comm') or '?')[:28]
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            continue
        pid_engines = {k: 0.0 for k in _ENGINE_CLASS_RE}
        total_busy = 0.0
        eng_data = c.get('engine-classes') or c.get('engines') or {}
        if isinstance(eng_data, dict):
            for key, val in eng_data.items():
                busy = float(val.get('busy', 0)) if isinstance(val, dict) \
                       else float(val) if isinstance(val, (int, float)) else 0.0
                for cls_name, pat in _ENGINE_CLASS_RE.items():
                    if pat.search(key):
                        pid_engines[cls_name] += busy
                        total_busy += busy
                        break
        else:
            total_busy = float(c.get('busy', 0))
            eng_cls = c.get('engine-class', '')
            for cls_name, pat in _ENGINE_CLASS_RE.items():
                if pat.search(eng_cls):
                    pid_engines[cls_name] = total_busy
                    break
        result.append({'pid': pid, 'name': name,
                       'engines': pid_engines, 'total': round(total_busy, 2)})
    result.sort(key=lambda x: x['total'], reverse=True)
    return result

def _ssh(remote_ip: str, remote_user: str, cmd: str,
         timeout: int = 12) -> subprocess.CompletedProcess:
    """Run a command on the remote via SSH (BatchMode, no tty)."""
    return subprocess.run(
        ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
         '-o', 'StrictHostKeyChecking=no',
         f'{remote_user}@{remote_ip}', cmd],
        capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
    )


def _try_intel_gpu_top(remote_ip: str, remote_user: str,
                       interval: float = 2.0) -> dict:
    """
    Run intel_gpu_top -J -s <ms> -n 2 on the remote and return the second
    (i.e. the real measurement) JSON object as a normalised dict.

    Returns an empty dict on ANY error (binary missing, PMU blocked, parse
    failure, SSH timeout …).  The caller should fall back to sysfs in that case.

    Normalised dict keys
    --------------------
    source          – 'intel_gpu_top'
    busy_pct        – Render/3D engine busy % (primary GPU load indicator)
    act_freq_mhz    – actual GT frequency (MHz)
    req_freq_mhz    – requested GT frequency (MHz)
    rc6_pct         – RC6 residency % (longer value = more idle)
    power_gpu_w     – GPU power draw (W) — 0 if RAPL unavailable
    power_pkg_w     – Package power draw (W) — 0 if RAPL unavailable
    engines         – dict { engine_name: {busy, sema, wait} } in percent
    period_ms       – actual measurement window length (ms)
    """
    interval_ms = max(500, int(interval * 1000))
    cmd = f'{_IGT_BIN} -J -s {interval_ms} -n 2 2>/dev/null'
    try:
        r = _ssh(remote_ip, remote_user, cmd, timeout=interval_ms // 1000 + 10)
    except Exception:
        return {}

    # intel_gpu_top -J emits a JSON *array* that it streams open-endedly.
    # With -n 2 the output is:  [\n{sample0},\n{sample1}\n]\n
    # We want sample1 (the real interval measurement).
    raw = r.stdout.strip()
    if not raw or r.returncode != 0:
        return {}
    # Extract all top-level JSON objects from the stream
    samples = []
    depth = 0
    start = None
    for i, ch in enumerate(raw):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    samples.append(json.loads(raw[start:i + 1]))
                except json.JSONDecodeError:
                    pass
    if len(samples) < 2:
        return {}
    s = samples[-1]  # last (actual measurement) sample

    def _fget(obj, *keys, default=0.0):
        for k in keys:
            if isinstance(obj, dict):
                obj = obj.get(k, default)
            else:
                return default
        try:
            return float(obj)
        except (TypeError, ValueError):
            return default

    engines_raw = s.get('engines', {})
    engines_out = {}
    render_busy = 0.0
    for name, data in engines_raw.items():
        if isinstance(data, dict) and 'busy' in data:
            busy = _fget(data, 'busy')
            engines_out[name] = {
                'busy': busy,
                'sema': _fget(data, 'sema'),
                'wait': _fget(data, 'wait'),
            }
            if 'Render' in name or '3D' in name:
                render_busy = busy

    # overall busy = max engine busy if no Render/3D found
    if not render_busy and engines_out:
        render_busy = max(v['busy'] for v in engines_out.values())

    return {
        'source':       'intel_gpu_top',
        'busy_pct':     round(render_busy, 1),
        'act_freq_mhz': int(_fget(s, 'frequency', 'actual')),
        'req_freq_mhz': int(_fget(s, 'frequency', 'requested')),
        'rc6_pct':      round(_fget(s, 'rc6', 'value'), 1),
        'power_gpu_w':  round(_fget(s, 'power', 'GPU'), 2),
        'power_pkg_w':  round(_fget(s, 'power', 'Package'), 2),
        'engines':      engines_out,
        'clients':      _parse_igt_clients(s),
        'period_ms':    round(_fget(s, 'period', 'duration'), 1),
    }


def _try_intel_gpu_top_local(interval: float = 2.0) -> dict:
    """
    Run intel_gpu_top locally (no SSH) and return a normalised dict identical
    in structure to the one returned by _try_intel_gpu_top().
    Returns an empty dict on any error (binary missing, PMU blocked, …).
    """
    igt_bin = _find_local_igt()
    if not igt_bin:
        return {}
    interval_ms = max(500, int(interval * 1000))
    try:
        r = subprocess.run(
            [igt_bin, '-J', '-s', str(interval_ms), '-n', '2'],
            capture_output=True, text=True,
            timeout=interval_ms // 1000 + 12,
        )
        raw = r.stdout.strip()
    except Exception:
        return {}
    if not raw:
        return {}
    # Reuse the same JSON parsing logic as the remote path
    samples = []
    depth = 0
    start = None
    for i, ch in enumerate(raw):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    samples.append(json.loads(raw[start:i + 1]))
                except json.JSONDecodeError:
                    pass
    if len(samples) < 2:
        return {}
    s = samples[-1]

    def _fget(obj, *keys, default=0.0):
        for k in keys:
            if isinstance(obj, dict):
                obj = obj.get(k, default)
            else:
                return default
        try:
            return float(obj)
        except (TypeError, ValueError):
            return default

    engines_raw = s.get('engines', {})
    engines_out = {}
    render_busy = 0.0
    for name, data in engines_raw.items():
        if isinstance(data, dict) and 'busy' in data:
            busy = _fget(data, 'busy')
            engines_out[name] = {
                'busy': busy,
                'sema': _fget(data, 'sema'),
                'wait': _fget(data, 'wait'),
            }
            if 'Render' in name or '3D' in name:
                render_busy = busy
    if not render_busy and engines_out:
        render_busy = max(v['busy'] for v in engines_out.values())

    return {
        'source':       'intel_gpu_top',
        'busy_pct':     round(render_busy, 1),
        'act_freq_mhz': int(_fget(s, 'frequency', 'actual')),
        'req_freq_mhz': int(_fget(s, 'frequency', 'requested')),
        'rc6_pct':      round(_fget(s, 'rc6', 'value'), 1),
        'power_gpu_w':  round(_fget(s, 'power', 'GPU'), 2),
        'power_pkg_w':  round(_fget(s, 'power', 'Package'), 2),
        'engines':      engines_out,
        'clients':      _parse_igt_clients(s),
        'period_ms':    round(_fget(s, 'period', 'duration'), 1),
        'igt_bin':      igt_bin,
    }


def _read_sysfs_gpu(remote_ip: str = None, remote_user: str = 'ubuntu') -> dict:
    """
    Read Intel GPU metrics from sysfs (no PMU / no root required).

    Returns a dict with keys:
        busy_pct       – estimated GPU busy % derived from RC6 residency delta
        act_freq_mhz   – actual (measured) GT frequency
        cur_freq_mhz   – current requested GT frequency
        max_freq_mhz   – maximum configured GT frequency
        throttled       – True when any throttle reason is active
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
        import os, glob
        gt_count = len(glob.glob(f'{_CARD}/gt/gt*'))
        if gt_count == 0:
            gt_count = 1

    rc6_paths = [f'{_CARD}/gt/gt{i}/rc6_residency_ms' for i in range(gt_count)]
    freq_paths = [
        f'{_CARD}/gt_act_freq_mhz',
        f'{_CARD}/gt_cur_freq_mhz',
        f'{_CARD}/gt_max_freq_mhz',
    ]
    throttle_path = f'{_CARD}/gt/gt0/throttle_reason_status'

    # First RC6 sample
    t0 = time.monotonic()
    s0 = _read(rc6_paths + freq_paths + [throttle_path])
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

    throttle_raw = s0.get(throttle_path, '0') or '0'
    try:
        throttled = int(throttle_raw) != 0
    except ValueError:
        throttled = False

    return {
        'busy_pct':     busy_pct,
        'act_freq_mhz': _int(f'{_CARD}/gt_act_freq_mhz'),
        'cur_freq_mhz': _int(f'{_CARD}/gt_cur_freq_mhz'),
        'max_freq_mhz': _int(f'{_CARD}/gt_max_freq_mhz'),
        'throttled':    throttled,
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
    `gpu_log`.  Tries intel_gpu_top -J first (rich data: per-engine busy%,
    power, rc6%); falls back to sysfs RC6 residency if PMU is blocked.
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
                print('[GPU] No Intel GPU sysfs found on remote — GPU monitoring skipped.')
                return
        except Exception:
            print('[GPU] Could not reach remote for GPU check — skipping.')
            return

    # Probe whether intel_gpu_top with PMU works on this machine
    use_igt = False
    if remote_ip:
        probe = _try_intel_gpu_top(remote_ip, remote_user, interval=max(interval, 1.0))
        if probe:
            use_igt = True
            print(f'[GPU] Using intel_gpu_top on remote (engines, power, RC6, per-PID) '
                  f'interval={interval}s')
        else:
            print(f'[GPU] intel_gpu_top unavailable on remote (PMU blocked?) — '
                  f'falling back to sysfs RC6 monitoring.')
            print(f'[GPU] Run on the remote to enable:  '
                  f'sudo setcap cap_perfmon+eip ~/.local/bin/intel_gpu_top')
    else:
        probe = _try_intel_gpu_top_local(interval=max(interval, 1.0))
        if probe:
            use_igt = True
            print(f'[GPU] Using local intel_gpu_top [{probe.get("igt_bin","")}] '
                  f'(engines, power, RC6, per-PID)  interval={interval}s')
        else:
            local_igt = _find_local_igt()
            if local_igt:
                print(f'[GPU] intel_gpu_top found at {local_igt} but PMU is blocked.')
                print(f'[GPU] Enable with:  sudo setcap cap_perfmon+eip {local_igt}')
            else:
                print(f'[GPU] intel_gpu_top not found — falling back to sysfs monitoring.')
                print(f'[GPU] Install:  sudo apt install intel-gpu-tools')

    if not use_igt:
        print(f'[GPU] Monitoring Intel GPU via sysfs (interval={interval}s)...')

    def _fmt_igt(stats: dict) -> str:
        engs     = stats.get('engines', {})
        render_b = stats.get('busy_pct', 0.0)
        pwr      = f"  ⚡{stats['power_gpu_w']:.1f}W" if stats.get('power_gpu_w') else ''
        temp     = (f"  🌡{stats['temp_c']:.0f}°C"
                    if stats.get('temp_c') is not None else '')
        # Build per-engine summary  e.g.  Render/3D:28.1%  Video:0.0%
        eng_parts = []
        for cls, pat in _ENGINE_CLASS_RE.items():
            # Find matching key in engines dict (raw key e.g. "Render/3D 0")
            for k, v in engs.items():
                if pat.search(k) and isinstance(v, dict):
                    eng_parts.append(f'{cls}:{v.get("busy", 0.0):.1f}%')
                    break
        eng_str = '  ' + '  '.join(eng_parts) if eng_parts else ''
        # Top PID if available
        clients = stats.get('clients', [])
        pid_str = ''
        if clients:
            top = clients[0]
            pid_str = f'  top-pid={top["pid"]}({top["name"]}):{top["total"]:.1f}%'
        return (f"[GPU] busy={render_b:5.1f}%  "
                f"freq={stats.get('act_freq_mhz', 0)}/{stats.get('req_freq_mhz', 0)} MHz  "
                f"rc6={stats.get('rc6_pct', 0.0):.1f}%{pwr}{temp}{eng_str}{pid_str}")

    def _fmt_sysfs(stats: dict) -> str:
        return (f"[GPU] busy={stats['busy_pct']:5.1f}%  "
                f"freq={stats['act_freq_mhz']}/{stats.get('max_freq_mhz', 0)} MHz"
                f"{'  ⚠THROTTLE' if stats.get('throttled') else ''}")

    try:
        while not stop_event.is_set():
            t0 = time.monotonic()
            if use_igt:
                if remote_ip:
                    stats = _try_intel_gpu_top(remote_ip, remote_user, interval=interval)
                else:
                    stats = _try_intel_gpu_top_local(interval=interval)
                if not stats:
                    # Transient failure — fall back to sysfs for this sample
                    stats = _read_sysfs_gpu(remote_ip=remote_ip, remote_user=remote_user)
            else:
                stats = _read_sysfs_gpu(remote_ip=remote_ip, remote_user=remote_user)

            if stats:
                ts = datetime.now().isoformat()
                # Attach temperature to every record
                temp_c = _read_gpu_temp_sysfs(
                    remote_ip=remote_ip, remote_user=remote_user)
                if temp_c is not None:
                    stats['temp_c'] = round(temp_c, 1)
                record = {'ts': ts, **stats}
                line = json.dumps(record)
                print(_fmt_igt(stats) if stats.get('source') == 'intel_gpu_top'
                      else _fmt_sysfs(stats))
                if log_fp:
                    log_fp.write(line + '\n')
                    log_fp.flush()

            # intel_gpu_top already consumed ~interval seconds; sysfs consumes 1s.
            # Sleep the remainder so we don't drift shorter than the interval.
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
        print('[GPU] GPU monitor stopped.')



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
        busy_pct          – NPU compute utilisation %
        cur_freq_mhz      – current clock frequency
        max_freq_mhz      – maximum clock frequency
        memory_used_mb    – memory utilisation (bytes → MB)
    Returns an empty dict on any failure.
    """
    paths = [f'{_NPU_SYSFS}/{f}' for f in _NPU_SYSFS_FILES]

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
    return {
        'busy_pct':       busy_pct,
        'cur_freq_mhz':   _int(s1, 'npu_current_frequency_mhz'),
        'max_freq_mhz':   _int(s1, 'npu_max_frequency_mhz'),
        'memory_used_mb': round(mem_bytes / (1024 * 1024), 1),
    }


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
                print('[NPU] No Intel NPU sysfs found on remote — NPU monitoring skipped.')
                return
        except Exception:
            print('[NPU] Could not reach remote for NPU check — skipping.')
            return
    else:
        if not os.path.isdir(_NPU_SYSFS):
            print('[NPU] No Intel NPU sysfs found locally — NPU monitoring skipped.')
            return

    print(f'[NPU] Monitoring Intel NPU via sysfs (interval={interval}s)...')

    try:
        while not stop_event.is_set():
            t0 = time.monotonic()
            stats = _read_sysfs_npu(remote_ip=remote_ip, remote_user=remote_user)
            if stats:
                ts = datetime.now().isoformat()
                record = {'ts': ts, **stats}
                print(f"[NPU] busy={stats['busy_pct']:5.1f}%  "
                      f"freq={stats['cur_freq_mhz']}/{stats['max_freq_mhz']} MHz  "
                      f"mem={stats['memory_used_mb']:.1f} MB")
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
        print('[NPU] NPU monitor stopped.')


def main():
    parser = argparse.ArgumentParser(
        description='Monitor ROS2 processes resource utilization using pidstat',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all ROS2 processes
  %(prog)s --list
  
  # Monitor CPU usage (default)
  %(prog)s
  
  # Monitor CPU and memory usage with logging
  %(prog)s --memory --log ros2_monitor.log
  
  # Monitor with 2 second interval
  %(prog)s --interval 2
  
  # Monitor for 10 samples then stop
  %(prog)s --count 10
  
  # Monitor I/O statistics
  %(prog)s --io
  
  # Monitor with thread details
  %(prog)s --threads
  
  # Continuous monitoring (auto-refresh process list)
  %(prog)s --continuous
        """
    )
    
    parser.add_argument('-l', '--list', action='store_true',
                        help='List all ROS2 processes and exit')
    parser.add_argument('-i', '--interval', type=float, default=1,
                        help='Sampling interval in seconds (default: 1, pidstat requires integers >= 1)')
    parser.add_argument('-c', '--count', type=int, default=0,
                        help='Number of samples (default: 0 = infinite)')
    parser.add_argument('-m', '--memory', action='store_true',
                        help='Show memory statistics')
    parser.add_argument('-d', '--io', action='store_true',
                        help='Show I/O statistics')
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

    args = parser.parse_args()

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
            import os
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
        monitor_ros2_pidstat(
            interval=args.interval,
            count=args.count,
            show_cpu=show_cpu,
            show_memory=args.memory,
            show_io=args.io,
            show_threads=args.threads,
            log_file=args.log,
            remote_ip=args.remote_ip,
            remote_user=args.remote_user,
        )
    finally:
        if _gpu_stop is not None:
            _gpu_stop.set()
        if _npu_stop is not None:
            _npu_stop.set()


if __name__ == '__main__':
    main()
