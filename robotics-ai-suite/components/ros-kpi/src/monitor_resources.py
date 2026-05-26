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
import json
import threading
from typing import Optional, Set
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


def _read_cpu_thermal_sysfs() -> dict:
    """
    Read CPU package temperature and throttle state from local sysfs.

    Temperature source: the ``x86_pkg_temp`` thermal zone in
    ``/sys/class/thermal/thermal_zone*/``.

    Throttle detection: compares ``scaling_cur_freq`` against
    ``cpuinfo_max_freq`` for CPU 0 via cpufreq sysfs; throttling is
    assumed when the current frequency falls below 95 % of the maximum.

    Returns a dict with:
        temp_c     - CPU package temperature in °C (float), or None
        throttled  - True when throttling detected, False when not, or None
    """
    temp_c: Optional[float] = None
    throttled: Optional[bool] = None

    for zone_dir in sorted(glob.glob('/sys/class/thermal/thermal_zone*')):
        try:
            zone_type = open(f'{zone_dir}/type').read().strip()
            if zone_type == 'x86_pkg_temp':
                raw = int(open(f'{zone_dir}/temp').read().strip())
                temp_c = round(raw / 1000.0, 1)
                break
        except (OSError, ValueError):
            continue

    try:
        cur  = int(open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq').read().strip())
        mxf  = int(open('/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq').read().strip())
        throttled = cur < mxf * 0.95
    except (OSError, ValueError):
        throttled = None

    return {'temp_c': temp_c, 'throttled': throttled}


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
      Line 1 – version string  e.g. "2.0"
      Line 2 – CliArgs JSON object
      Line 3+ – one AppDataState JSON object per iteration

    Key schema details:
      ``dev_stats.eng_usage``    – dict {engine: [ratio, …]} (0.0–1.0, NOT %)
      ``dev_stats.freqs``        – [[{act_freq: Hz, throttle_reasons: {status: bool}}, …], …]
      ``dev_stats.power``        – [{gpu_cur_power: W, pkg_cur_power: W}, …]
      ``dev_stats.temps``        – [[{name: str, temp: °C}, …], …]  (dGPU only)
      ``dev_stats.mem_info``     – [{smem_used: bytes, vram_used: bytes, …}, …]
      ``clis_stats``             – [{pid, comm, eng_usage: {engine: [ratio,…]}, …}, …]

    Returns a normalised dict (same schema as the rest of the GPU monitoring
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

    # ── Engine utilisation (ratios → %) ────────────────────────────────────────
    eng_usage_raw = dev_stats.get('eng_usage', {})
    engines_out = {}
    render_busy = 0.0
    for eng_name, usage_list in eng_usage_raw.items():
        last_val = _last(usage_list)
        if last_val is None:
            continue
        busy_pct = round(float(last_val) * 100.0, 1)
        engines_out[eng_name] = {'busy': busy_pct, 'sema': 0.0, 'wait': 0.0}
        if _ENGINE_CLASS_RE['Render/3D'].search(eng_name):
            render_busy = busy_pct

    if not render_busy and engines_out:
        render_busy = max(v['busy'] for v in engines_out.values())

    # ── Frequencies (Hz → MHz) + throttle ─────────────────────────────────────
    last_freqs = _last(dev_stats.get('freqs', []))      # Vec<DrmDeviceFreqs>
    act_freq_mhz = 0
    throttled = False
    if last_freqs and isinstance(last_freqs, list) and last_freqs:
        gt0 = last_freqs[0]
        act_freq_mhz = int(gt0.get('act_freq', 0) / 1_000_000)
        throttled = bool(gt0.get('throttle_reasons', {}).get('status', False))

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
            busy = float(last_val) * 100.0
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
        'throttled':    throttled,
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
                print('[GPU] No Intel GPU sysfs found on remote — GPU monitoring skipped.')
                return
        except Exception:
            print('[GPU] Could not reach remote for GPU check — skipping.')
            return

    # Probe: try qmassa first; fall back to sysfs if unavailable.
    use_qmassa = False
    if not remote_ip:
        probe = _try_qmassa_local(interval=max(interval, 1.0))
        if probe:
            use_qmassa = True
            drv = probe.get('drv_name', 'xe')
            print(f'[GPU] Using qmassa ({drv} driver, engines/power/per-PID)  '
                  f'interval={interval}s')
        else:
            qmassa_bin = _find_local_qmassa()
            if qmassa_bin:
                print(f'[GPU] qmassa found at {qmassa_bin} but probe failed '
                      f'(check video/render/power group membership).')
            else:
                print('[GPU] qmassa not found — falling back to sysfs monitoring.')
                print('[GPU] Install:  make install-qmassa')

    if not use_qmassa:
        print(f'[GPU] Monitoring Intel GPU via sysfs (interval={interval}s)...')

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
                f"freq={stats['act_freq_mhz']}/{stats.get('max_freq_mhz', 0)} MHz"
                f"{'  ⚠THROTTLE' if stats.get('throttled') else ''}")

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
                print(_fmt_rich(stats) if src == 'qmassa' else _fmt_sysfs(stats))
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
        print('[GPU] GPU monitor stopped.')


# ── Intel PMT Telemetry (NPU power / temp / memory bandwidth) ────────────────
# Adapted from Intel internal tooling (edge-metric-profiler).
# Reads /sys/class/intel_pmt/telem* binary files exposed by the Intel PMT
# driver (CONFIG_INTEL_PMT_TELEMETRY).  Local access only; no root required
# for the sysfs reads, but the device files may need group membership.

_PMT_ROOT = '/sys/class/intel_pmt'

_PMT_GUID_REGS = {
    '0x130670b2': ('MTL', {  # Meteor Lake
        'VPU_ENERGY':       0x628,
        'SOC_TEMPERATURES': 0x98,
        'VPU_WORKPOINT':    0x68,
        'VPU_MEMORY_BW':    0x0,
    }),
    '0x1306a0b3': ('ARL', {  # Arrow Lake
        'VPU_ENERGY':       0x628,
        'SOC_TEMPERATURES': 0x98,
        'VPU_WORKPOINT':    0x68,
        'VPU_MEMORY_BW':    0x0,
    }),
    '0x1306a0b2': ('ARL', {  # Arrow Lake-H (same regs)
        'VPU_ENERGY':       0x628,
        'SOC_TEMPERATURES': 0x98,
        'VPU_WORKPOINT':    0x68,
        'VPU_MEMORY_BW':    0x0,
    }),
    '0x1306a0b4': ('ARL', {  # Arrow Lake-S (same regs)
        'VPU_ENERGY':       0x628,
        'SOC_TEMPERATURES': 0x98,
        'VPU_WORKPOINT':    0x68,
        'VPU_MEMORY_BW':    0x0,
    }),
    '0x3072005':  ('LNL', {  # Lunar Lake
        'VPU_ENERGY':       0x5d0,
        'SOC_TEMPERATURES': 0x70,
        'VPU_WORKPOINT':    0x18,
        'VPU_MEMORY_BW':    0xc18,
    }),
    '0x3086000':  ('PTL', {  # Panther Lake
        'VPU_ENERGY':       0x670,
        'SOC_TEMPERATURES': 0x78,
        'VPU_WORKPOINT':    0x18,
        'VPU_MEMORY_BW':    0xc18,
    }),
    '0x308d000':  ('WCL', {  # Wildcat Lake — energy needs ×33 correction
        'VPU_ENERGY':       0x670,
        'SOC_TEMPERATURES': 0x78,
        'VPU_WORKPOINT':    0x18,
        'VPU_MEMORY_BW':    0xc18,
    }),
}


class _PmtTelemetry:
    """
    Lightweight reader for the Intel PMT telemetry binary sysfs interface.
    Supports MTL, ARL, LNL, PTL, WCL.  Raises RuntimeError on any init failure
    so callers can gracefully skip PMT metrics when unavailable.
    """

    def __init__(self) -> None:
        if not os.path.isdir(_PMT_ROOT):
            raise RuntimeError(f'PMT sysfs not found at {_PMT_ROOT}')

        self._buf: bytes = b''
        self._regs: dict = {}
        self._telem_path: str = ''
        self._cpu_gen: str = ''
        self._wcl_correction: bool = False

        for entry in os.listdir(_PMT_ROOT):
            if not entry.startswith('telem'):
                continue
            telem_dir = os.path.join(_PMT_ROOT, entry)
            guid_path  = os.path.join(telem_dir, 'guid')
            telem_path = os.path.join(telem_dir, 'telem')
            if not (os.path.exists(guid_path) and os.path.exists(telem_path)):
                continue
            try:
                guid = open(guid_path).read().strip()
            except OSError:
                continue
            if guid in _PMT_GUID_REGS:
                gen, regs = _PMT_GUID_REGS[guid]
                self._cpu_gen        = gen
                self._regs           = regs
                self._telem_path     = telem_path
                self._wcl_correction = gen == 'WCL'
                break

        if not self._telem_path:
            raise RuntimeError('No PMT telemetry device with known GUID found')

    # ── low-level ─────────────────────────────────────────────────────────────

    def update_buffer(self) -> None:
        with open(self._telem_path, 'rb') as fh:
            self._buf = fh.read()

    def _read_bits(self, offset: int, msb: int, lsb: int) -> int:
        """Extract bit-field [msb:lsb] from a 64-bit LE word at *offset*."""
        word = int.from_bytes(self._buf[offset:offset + 8], byteorder='little')
        msb_mask = 0xFFFFFFFFFFFFFFFF & ((2 ** (msb + 1)) - 1)
        lsb_mask = 0xFFFFFFFFFFFFFFFF & ((2 ** lsb) - 1)
        return (word & (msb_mask & ~lsb_mask)) >> lsb

    # ── public metrics ────────────────────────────────────────────────────────

    def get_npu_temperature(self) -> int:
        """NPU junction temperature in °C (bits 47:40 of SOC_TEMPERATURES)."""
        return self._read_bits(self._regs['SOC_TEMPERATURES'], 47, 40)

    def get_npu_energy(self) -> float:
        """Cumulative NPU energy in joules (U32.18.14 fixed-point)."""
        raw = self._read_bits(self._regs['VPU_ENERGY'], 63, 0)
        energy = (raw >> 14) + (raw & 0x3FFF) / (1 << 14)
        if self._wcl_correction:
            energy *= 33   # 3-tile → 1-tile normalisation
        return energy

    def get_noc_bandwidth_mbps(self) -> float:
        """Cumulative NPU NoC bandwidth sample (arbitrary units → MB/s proxy)."""
        val = self._read_bits(self._regs['VPU_MEMORY_BW'], 31, 0)
        return val / 1e3

    @property
    def cpu_gen(self) -> str:
        return self._cpu_gen


# Module-level PMT singleton — lazily initialised, None if unavailable.
_PMT_STATE: dict = {'instance': None, 'unavailable': False}


def _get_pmt() -> Optional['_PmtTelemetry']:
    if _PMT_STATE['unavailable']:
        return None
    if _PMT_STATE['instance'] is None:
        try:
            _PMT_STATE['instance'] = _PmtTelemetry()
        except Exception:
            _PMT_STATE['unavailable'] = True
            return None
    return _PMT_STATE['instance']


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
        busy_pct          - NPU compute utilisation %
        cur_freq_mhz      - current clock frequency
        max_freq_mhz      - maximum clock frequency
        memory_used_mb    - memory utilisation (bytes → MB)
        throttled         - True when cur_freq_mhz < max_freq_mhz * 0.95
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

    # ── PMT pre-sample (local only; ignored on SSH path) ─────────────────────
    pmt = None if remote_ip else _get_pmt()
    pmt_e0 = 0.0
    pmt_bw0 = 0.0
    if pmt:
        try:
            pmt.update_buffer()
            pmt_e0  = pmt.get_npu_energy()
            pmt_bw0 = pmt.get_noc_bandwidth_mbps()
        except Exception:
            pmt = None

    t0 = time.monotonic()
    s0 = _read_all()
    time.sleep(1.0)
    t1 = time.monotonic()
    s1 = _read_all()

    # ── PMT post-sample ───────────────────────────────────────────────────────
    pmt_power_w = None
    pmt_temp_c  = None
    pmt_bw_mbps = None
    if pmt:
        try:
            pmt.update_buffer()
            elapsed_s   = t1 - t0
            pmt_power_w = round((pmt.get_npu_energy() - pmt_e0) / max(elapsed_s, 1e-6), 3)
            pmt_temp_c  = pmt.get_npu_temperature()
            bw1         = pmt.get_noc_bandwidth_mbps()
            pmt_bw_mbps = round(max(0.0, bw1 - pmt_bw0) / max(elapsed_s, 1.0), 2)
        except Exception:
            pass

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
    # Throttle detection: current frequency dropped below 95 % of maximum.
    throttled = bool(0 < cur_freq < max_freq * 0.95 and max_freq > 0)
    result = {
        'busy_pct':       busy_pct,
        'cur_freq_mhz':   cur_freq,
        'max_freq_mhz':   max_freq,
        'memory_used_mb': round(mem_bytes / (1024 * 1024), 1),
        'throttled':      throttled,
    }
    if pmt_power_w is not None:
        result['power_w']  = pmt_power_w
    if pmt_temp_c is not None:
        result['temp_c']   = pmt_temp_c
    if pmt_bw_mbps is not None:
        result['bw_mbps']  = pmt_bw_mbps
    if pmt:
        result['pmt_gen'] = pmt.cpu_gen
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
                pwr_str  = (f"  ⚡{stats['power_w']:.2f}W"
                            if 'power_w' in stats else '')
                temp_str = (f"  🌡{stats['temp_c']}°C"
                            if 'temp_c' in stats else '')
                bw_str   = (f"  bw={stats['bw_mbps']:.1f} MB/s"
                            if 'bw_mbps' in stats else '')
                throttle_str = '  ⚠THROTTLE' if stats.get('throttled') else ''
                print(f"[NPU] busy={stats['busy_pct']:5.1f}%  "
                      f"freq={stats['cur_freq_mhz']}/{stats['max_freq_mhz']} MHz  "
                      f"mem={stats['memory_used_mb']:.1f} MB"
                      f"{pwr_str}{temp_str}{bw_str}{throttle_str}")
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
    parser.add_argument('--check-hw', action='store_true',
                        help='Probe local GPU and NPU monitoring availability then exit')

    args = parser.parse_args()

    if args.check_hw:
        driver = _detect_gpu_driver()
        gpu_avail, gpu_tool, gpu_reason = probe_gpu_available()
        npu_avail, npu_reason = probe_npu_available()
        print('\u2554' + '\u2550' * 64 + '\u2557')
        print('\u2551' + '  Hardware Monitoring Probe'.ljust(64) + '\u2551')
        print('\u255a' + '\u2550' * 64 + '\u255d')
        print()
        print(f'[GPU] Kernel driver : {driver}')
        if gpu_avail:
            print(f'[GPU] Status        : \u2705 AVAILABLE  (tool: {gpu_tool})')
        else:
            print('[GPU] Status        : \u274c UNAVAILABLE')
        print(f'[GPU] Detail        : {gpu_reason}')
        print()
        print(f'[NPU] Sysfs path    : {_NPU_SYSFS}')
        if npu_avail:
            print('[NPU] Status        : \u2705 AVAILABLE')
        else:
            print('[NPU] Status        : \u274c UNAVAILABLE')
        print(f'[NPU] Detail        : {npu_reason}')
        print()
        print('Auto-monitoring summary:')
        print(f'  GPU will be monitored : {"yes" if gpu_avail else "no"}')
        print(f'  NPU will be monitored : {"yes" if npu_avail else "no"}')
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
