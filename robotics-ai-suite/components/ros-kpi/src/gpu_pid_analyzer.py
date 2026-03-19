#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Intel GPU PID Analyzer
======================
Per-process GPU utilisation with full engine-class breakdown, frequency,
temperature and power using intel_gpu_top -J (igt-gpu-tools).

Reported metrics
----------------
  GPU-level
    • Render/3D busy %    (≈ graphics / compute workload)
    • Blitter busy %      (≈ copy / blit operations)
    • Video busy %        (≈ hardware video decode/encode)
    • VE busy %           (VideoEnhance / ComputeClass)
    • Actual & requested GT frequency (MHz)
    • GPU temperature (°C) – from hwmon sysfs
    • GPU power (W) and SoC package power (W)
    • RC6 residency %

  Per-PID (requires intel_gpu_top ≥ 1.27 with "clients" JSON field)
    • Total GPU busy %
    • Per-engine-class busy % (Render/3D, Blitter, Video, VE)
    • Process name

Prerequisites
-------------
  sudo apt install intel-gpu-tools          # (or igt-gpu-tools)
  sudo setcap cap_perfmon+eip $(which intel_gpu_top)

Usage
-----
  python src/gpu_pid_analyzer.py                  # one-shot snapshot
  python src/gpu_pid_analyzer.py --watch          # refresh every 2 s
  python src/gpu_pid_analyzer.py --duration 60    # run for 60 seconds
  python src/gpu_pid_analyzer.py --interval 1 --duration 120 --csv gpu.csv
  python src/gpu_pid_analyzer.py --remote-ip 10.0.0.5 --remote-user intel
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

_LOCAL_IGT_CANDIDATES = [
    '/usr/bin/intel_gpu_top',
    '/usr/local/bin/intel_gpu_top',
    os.path.expanduser('~/.local/bin/intel_gpu_top'),
]

_REMOTE_IGT_BIN = '~/.local/bin/intel_gpu_top'

# sysfs DRM card paths to try (card0 = integrated fb; card1 = discrete/Xe)
_DRM_CARDS = [
    '/sys/class/drm/card0',
    '/sys/class/drm/card1',
]

# Engine class definitions: display label → regex matched against JSON key
_ENGINE_CLASSES: Dict[str, re.Pattern] = {
    'Render/3D': re.compile(r'render|3d',               re.I),
    'Blitter':   re.compile(r'blitter|blt',             re.I),
    'Video':     re.compile(r'^video$',                 re.I),
    'VE':        re.compile(r'videoenhance|video_enhance|ve\b', re.I),
}

_ENG_COLS: List[str] = list(_ENGINE_CLASSES.keys())   # ordered list

# ──────────────────────────────────────────────────────────────────────────────
# Binary discovery & runner
# ──────────────────────────────────────────────────────────────────────────────

def _find_local_igt() -> Optional[str]:
    """Return the path to a locally installed intel_gpu_top binary, or None."""
    for p in _LOCAL_IGT_CANDIDATES:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    # Fall back to PATH lookup
    try:
        r = subprocess.run(['which', 'intel_gpu_top'],
                           capture_output=True, text=True, timeout=3)
        path = r.stdout.strip()
        if path and os.path.isfile(path):
            return path
    except Exception:
        pass
    return None


def _run_igt_local(igt_bin: str, interval_ms: int) -> str:
    """Run intel_gpu_top locally; return raw stdout."""
    cmd = [igt_bin, '-J', '-s', str(interval_ms), '-n', '2']
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=interval_ms // 1000 + 15)
        return r.stdout
    except Exception:
        return ''


def _ssh_run(remote_ip: str, remote_user: str,
             cmd: str, timeout: int = 20) -> str:
    """Run a shell command over SSH; return stdout or '' on error."""
    try:
        r = subprocess.run(
            ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
             '-o', 'StrictHostKeyChecking=no',
             f'{remote_user}@{remote_ip}', cmd],
            capture_output=True, text=True,
            timeout=timeout, stdin=subprocess.DEVNULL,
        )
        return r.stdout if r.returncode == 0 else ''
    except Exception:
        return ''


def _run_igt_remote(remote_ip: str, remote_user: str, interval_ms: int) -> str:
    """Run intel_gpu_top on a remote host; return raw stdout."""
    cmd = f'{_REMOTE_IGT_BIN} -J -s {interval_ms} -n 2 2>/dev/null'
    return _ssh_run(remote_ip, remote_user, cmd,
                    timeout=interval_ms // 1000 + 15)


# ──────────────────────────────────────────────────────────────────────────────
# JSON parsing
# ──────────────────────────────────────────────────────────────────────────────

def _parse_igt_json(raw: str) -> Optional[dict]:
    """
    Parse intel_gpu_top -J streaming output (open-ended JSON array of objects).
    Returns the last complete JSON object (real-measurement sample), or None.
    """
    samples = []
    depth = 0
    start: Optional[int] = None
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
    # The first sample is a zeroed baseline; the second is the real interval
    return samples[-1] if len(samples) >= 2 else None


# ──────────────────────────────────────────────────────────────────────────────
# Temperature – sysfs hwmon
# ──────────────────────────────────────────────────────────────────────────────

def _read_gpu_temp_local() -> Optional[float]:
    """
    Read Intel GPU temperature (°C) from hwmon sysfs.
    Tries card0 → card1 across all hwmon sub-directories.
    Returns None if unavailable.
    """
    for card in _DRM_CARDS:
        pattern = f'{card}/device/hwmon/hwmon*/temp*_input'
        for m in sorted(glob.glob(pattern)):
            try:
                val = int(open(m).read().strip())
                return val / 1000.0       # millidegrees → °C
            except Exception:
                continue
    return None


def _read_gpu_temp_remote(remote_ip: str, remote_user: str) -> Optional[float]:
    """Read GPU temperature from hwmon sysfs on the remote host via SSH."""
    cmd = (
        'for f in '
        '/sys/class/drm/card0/device/hwmon/hwmon*/temp*_input '
        '/sys/class/drm/card1/device/hwmon/hwmon*/temp*_input; '
        'do [ -f "$f" ] && cat "$f" && break; done 2>/dev/null'
    )
    out = _ssh_run(remote_ip, remote_user, cmd, timeout=6).strip()
    if out:
        try:
            return int(out) / 1000.0
        except ValueError:
            pass
    return None


def read_gpu_temp(remote_ip: str = None,
                  remote_user: str = 'ubuntu') -> Optional[float]:
    """Return GPU temperature in °C (local or remote), or None."""
    if remote_ip:
        return _read_gpu_temp_remote(remote_ip, remote_user)
    return _read_gpu_temp_local()


# ──────────────────────────────────────────────────────────────────────────────
# Engine classification
# ──────────────────────────────────────────────────────────────────────────────

def _classify_engines(engines_raw: dict) -> Dict[str, Dict[str, float]]:
    """
    Map raw engine keys (e.g. "Render/3D 0", "Blitter 0") to canonical class
    labels, summing across multiple instances of the same class.

    Returns { class_label: {busy, sema, wait} } for every entry in _ENGINE_CLASSES.
    """
    out: Dict[str, Dict[str, float]] = {
        k: {'busy': 0.0, 'sema': 0.0, 'wait': 0.0}
        for k in _ENGINE_CLASSES
    }
    for key, data in engines_raw.items():
        if not isinstance(data, dict):
            continue
        busy = float(data.get('busy', 0))
        sema = float(data.get('sema', 0))
        wait = float(data.get('wait', 0))
        for cls_name, pattern in _ENGINE_CLASSES.items():
            if pattern.search(key):
                out[cls_name]['busy'] += busy
                out[cls_name]['sema'] += sema
                out[cls_name]['wait'] += wait
                break
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Per-PID client parsing
# ──────────────────────────────────────────────────────────────────────────────

def _parse_clients(sample: dict) -> List[dict]:
    """
    Extract per-PID GPU utilisation from intel_gpu_top JSON "clients" field.

    intel_gpu_top ≥ 1.27 populates "clients" with per-fd / per-process stats.
    Handles both dict-of-dicts and list-of-dicts layouts across versions.

    Returns a list (sorted by total GPU % descending):
        [{ pid, name, engines: {class: busy%}, total }, …]
    """
    clients_raw = sample.get('clients', {})
    if not clients_raw:
        return []

    # Normalise to list
    items: list = list(clients_raw.values()) if isinstance(clients_raw, dict) \
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

        pid_engines: Dict[str, float] = {k: 0.0 for k in _ENGINE_CLASSES}
        total_busy = 0.0

        eng_data = c.get('engine-classes') or c.get('engines') or {}
        if isinstance(eng_data, dict):
            for key, val in eng_data.items():
                if isinstance(val, dict):
                    busy = float(val.get('busy', 0))
                elif isinstance(val, (int, float)):
                    busy = float(val)
                else:
                    busy = 0.0
                for cls_name, pattern in _ENGINE_CLASSES.items():
                    if pattern.search(key):
                        pid_engines[cls_name] += busy
                        total_busy += busy
                        break
        else:
            # Older format: single "busy" scalar + "engine-class" string
            total_busy = float(c.get('busy', 0))
            eng_class_str = c.get('engine-class', '')
            for cls_name, pattern in _ENGINE_CLASSES.items():
                if pattern.search(eng_class_str):
                    pid_engines[cls_name] = total_busy
                    break

        result.append({
            'pid':     pid,
            'name':    name,
            'engines': pid_engines,
            'total':   round(total_busy, 2),
        })

    result.sort(key=lambda x: x['total'], reverse=True)
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Main probe
# ──────────────────────────────────────────────────────────────────────────────

def collect_snapshot(interval: float = 2.0,
                     remote_ip: str = None,
                     remote_user: str = 'ubuntu') -> dict:
    """
    Collect one GPU snapshot that includes per-PID breakdown, engine-class
    utilisation, frequency, temperature and power.

    Returns a dict with keys:
        ts               – ISO-8601 timestamp
        ok               – True if intel_gpu_top data is available
        source           – 'intel_gpu_top' | 'unavailable'
        freq_actual_mhz  – actual GT frequency (MHz)
        freq_req_mhz     – requested GT frequency (MHz)
        rc6_pct          – RC6 power residency %
        power_gpu_w      – GPU power draw (W); 0 if RAPL unavailable
        power_pkg_w      – SoC package power (W)
        temp_c           – GPU temperature (°C) from hwmon sysfs, or None
        engines          – { class: {busy, sema, wait} } GPU-level totals
        clients          – [ {pid, name, engines, total} ] per-PID breakdown
        period_ms        – actual measurement window (ms)
        igt_bin          – path used to run intel_gpu_top (local only)
    """
    interval_ms = max(500, int(interval * 1000))
    raw = ''
    igt_bin_used = None

    if remote_ip:
        raw = _run_igt_remote(remote_ip, remote_user, interval_ms)
    else:
        igt_bin_used = _find_local_igt()
        if igt_bin_used:
            raw = _run_igt_local(igt_bin_used, interval_ms)

    sample = _parse_igt_json(raw) if raw else None
    temp_c = read_gpu_temp(remote_ip=remote_ip, remote_user=remote_user)

    if not sample:
        return {
            'ts':      datetime.now().isoformat(),
            'ok':      False,
            'source':  'unavailable',
            'temp_c':  temp_c,
        }

    def _f(obj, *keys, default=0.0):
        for k in keys:
            obj = obj.get(k, default) if isinstance(obj, dict) else default
        try:
            return float(obj)
        except (TypeError, ValueError):
            return default

    engines_raw = sample.get('engines', {})

    snap = {
        'ts':              datetime.now().isoformat(),
        'ok':              True,
        'source':          'intel_gpu_top',
        'freq_actual_mhz': int(_f(sample, 'frequency', 'actual')),
        'freq_req_mhz':    int(_f(sample, 'frequency', 'requested')),
        'rc6_pct':         round(_f(sample, 'rc6', 'value'), 1),
        'power_gpu_w':     round(_f(sample, 'power', 'GPU'), 2),
        'power_pkg_w':     round(_f(sample, 'power', 'Package'), 2),
        'temp_c':          temp_c,
        'engines':         _classify_engines(engines_raw),
        'clients':         _parse_clients(sample),
        'period_ms':       round(_f(sample, 'period', 'duration'), 1),
    }
    if igt_bin_used:
        snap['igt_bin'] = igt_bin_used
    return snap


# ──────────────────────────────────────────────────────────────────────────────
# Display
# ──────────────────────────────────────────────────────────────────────────────

def _bar(pct: float, width: int = 12) -> str:
    filled = max(0, min(int(round(pct / 100 * width)), width))
    return '█' * filled + '░' * (width - filled)


def print_snapshot(snap: dict):
    """Pretty-print one snapshot to stdout."""
    ts = snap.get('ts', '')[:19].replace('T', ' ')

    if not snap.get('ok'):
        temp_str = (f'  Temp: {snap["temp_c"]:.0f}°C'
                    if snap.get('temp_c') is not None else '')
        print(f'\n[{ts}]  intel_gpu_top unavailable (PMU blocked / not installed)'
              f'{temp_str}')
        print('  ▶  sudo setcap cap_perfmon+eip $(which intel_gpu_top)')
        return

    freq_a  = snap['freq_actual_mhz']
    freq_r  = snap['freq_req_mhz']
    pwr_g   = snap['power_gpu_w']
    pwr_p   = snap['power_pkg_w']
    rc6     = snap['rc6_pct']
    temp    = snap.get('temp_c')
    period  = snap.get('period_ms', 0)
    bin_str = f'  [{snap["igt_bin"]}]' if snap.get('igt_bin') else ''

    temp_str = f'  Temp: {temp:.0f} °C' if temp is not None else '  Temp: n/a'
    pwr_str  = (f'  GPU: {pwr_g:.1f} W   Pkg: {pwr_p:.1f} W'
                if pwr_g else '  Power: RAPL unavailable')

    print(f'\n╔══ Intel GPU  [{ts}]  period={period:.0f} ms{bin_str}')
    print(f'║')
    print(f'║  Frequency : {freq_a:>5} MHz actual  /  {freq_r:>5} MHz requested')
    print(f'║  RC6       : {rc6:.1f} %  (idle residency – higher = more idle)')
    print(f'║  Power     :{pwr_str}')
    print(f'║  Temp      :{temp_str}')
    print(f'║')
    print(f'║  ── Engine Utilisation ──────────────────────────────────────────')
    print(f'║   {"Engine":<12}  {"Busy":>6}  {"Bar":^14}  {"Sema":>6}  {"Wait":>6}')
    print(f'║   {"─"*12}  {"─"*6}  {"─"*14}  {"─"*6}  {"─"*6}')

    eng = snap.get('engines', {})
    for cls in _ENG_COLS:
        d    = eng.get(cls, {})
        busy = d.get('busy', 0.0)
        sema = d.get('sema', 0.0)
        wait = d.get('wait', 0.0)
        bar  = _bar(busy)
        print(f'║   {cls:<12}  {busy:>5.1f}%  [{bar}]  {sema:>5.1f}%  {wait:>5.1f}%')

    clients = snap.get('clients', [])
    if clients:
        print(f'║')
        print(f'║  ── Per-PID GPU Usage ───────────────────────────────────────────')
        # header
        hdr_eng = '  '.join(f'{c:<9}' for c in _ENG_COLS)
        print(f'║   {"PID":>7}  {"Process":<28}  {"Total":>6}  {hdr_eng}')
        print(f'║   {"─"*7}  {"─"*28}  {"─"*6}  {"─"*(9*len(_ENG_COLS)+2*(len(_ENG_COLS)-1))}')

        shown = 0
        for c in clients:
            if c['total'] < 0.05 and shown > 0:
                continue       # skip idle processes after showing at least one
            eng_vals = '  '.join(
                f'{c["engines"].get(cls, 0.0):>8.1f}%' for cls in _ENG_COLS
            )
            print(f'║   {c["pid"]:>7}  {c["name"]:<28}  {c["total"]:>5.1f}%  {eng_vals}')
            shown += 1
    else:
        print(f'║')
        print(f'║  Per-PID data: requires intel_gpu_top ≥ 1.27 with "clients" support')
        print(f'║  (try: intel_gpu_top --help | grep clients)')

    print(f'╚{"═" * 68}')


# ──────────────────────────────────────────────────────────────────────────────
# CSV helpers
# ──────────────────────────────────────────────────────────────────────────────

def _csv_header() -> str:
    eng_hdrs = ','.join(f'{c}_busy_pct' for c in _ENG_COLS)
    return (f'timestamp,freq_actual_mhz,freq_req_mhz,rc6_pct,'
            f'power_gpu_w,power_pkg_w,temp_c,{eng_hdrs},'
            f'top_pid,top_pid_name,top_pid_total_pct,'
            + ','.join(f'top_pid_{c}_pct' for c in _ENG_COLS))


def _snap_to_csv(snap: dict) -> str:
    if not snap.get('ok'):
        empty = ','.join([''] * (len(_ENG_COLS) + 3 + len(_ENG_COLS)))
        temp  = snap.get('temp_c', '')
        return f'{snap.get("ts","")[:19]},,,,,{temp or ""},{empty}'

    eng = snap.get('engines', {})
    eng_vals = ','.join(
        f'{eng.get(c, {}).get("busy", 0.0):.2f}' for c in _ENG_COLS
    )
    clients = snap.get('clients', [])
    top     = clients[0] if clients else {}
    top_eng = ','.join(
        f'{top.get("engines", {}).get(c, 0.0):.2f}' for c in _ENG_COLS
    )
    temp = snap.get('temp_c', '')
    return (
        f'{snap["ts"][:19]},'
        f'{snap["freq_actual_mhz"]},{snap["freq_req_mhz"]},'
        f'{snap["rc6_pct"]},{snap["power_gpu_w"]},{snap["power_pkg_w"]},'
        f'{temp if temp is not None else ""},'
        f'{eng_vals},'
        f'{top.get("pid", "")},{top.get("name", "")},{top.get("total", "")},'
        f'{top_eng}'
    )


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Intel GPU PID Analyzer – per-process GPU usage with '
                    'engine breakdown, frequency, temperature and power',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--interval', '-i', type=float, default=2.0,
                        metavar='SEC',
                        help='Sampling interval in seconds (default: 2.0)')
    parser.add_argument('--duration', '-d', type=float, default=0,
                        metavar='SEC',
                        help='Total run duration in seconds '
                             '(0 = one snapshot then exit)')
    parser.add_argument('--watch', '-w', action='store_true',
                        help='Keep refreshing until Ctrl-C '
                             '(equivalent to --duration=∞)')
    parser.add_argument('--csv', type=str, default=None,
                        metavar='FILE',
                        help='Append rows to a CSV file')
    parser.add_argument('--json-log', type=str, default=None,
                        metavar='FILE',
                        help='Append raw JSON-lines to a file')
    parser.add_argument('--remote-ip', type=str, default=None,
                        metavar='IP',
                        help='Collect from a remote host via SSH')
    parser.add_argument('--remote-user', type=str, default='ubuntu',
                        metavar='USER',
                        help='SSH username (default: ubuntu)')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress console output (useful with --csv)')
    args = parser.parse_args()

    # ── Open output files ──────────────────────────────────────────────────
    csv_fp = json_fp = None
    if args.csv:
        write_header = not os.path.exists(args.csv)
        csv_fp = open(args.csv, 'a', buffering=1)
        if write_header:
            csv_fp.write(_csv_header() + '\n')

    if args.json_log:
        json_fp = open(args.json_log, 'a', buffering=1)

    # ── Print preamble ─────────────────────────────────────────────────────
    loop     = args.watch or args.duration > 0
    deadline = time.monotonic() + args.duration if args.duration > 0 \
               else float('inf')

    target = f'remote={args.remote_ip}' if args.remote_ip else 'local'
    print(f'Intel GPU PID Analyzer  –  interval={args.interval}s  target={target}')
    if not args.remote_ip:
        igt = _find_local_igt()
        if igt:
            print(f'  intel_gpu_top  : {igt}')
        else:
            print('  intel_gpu_top  : NOT FOUND')
            print('    Install:  sudo apt install intel-gpu-tools')
            print('    Enable:   sudo setcap cap_perfmon+eip $(which intel_gpu_top)')
    if not loop:
        print('  (one snapshot — use --watch or --duration N to loop)\n')
    else:
        print('  Press Ctrl-C to stop.\n')

    # ── Sampling loop ──────────────────────────────────────────────────────
    try:
        while True:
            snap = collect_snapshot(
                interval=args.interval,
                remote_ip=args.remote_ip,
                remote_user=args.remote_user,
            )

            if not args.quiet:
                print_snapshot(snap)

            if csv_fp:
                csv_fp.write(_snap_to_csv(snap) + '\n')
            if json_fp:
                json_fp.write(json.dumps(snap) + '\n')

            if not loop:
                break
            if time.monotonic() >= deadline:
                break

    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        if csv_fp:
            csv_fp.close()
        if json_fp:
            json_fp.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
