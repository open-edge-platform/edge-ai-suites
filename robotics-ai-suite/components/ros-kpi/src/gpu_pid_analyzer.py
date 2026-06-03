#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""Intel GPU PID Analyzer (qmassa).

==============================================
Per-process GPU utilisation with full engine-class breakdown, frequency,
temperature and power using qmassa (reads xe/i915 DRM fdinfo; no CAP_PERFMON).

Reported metrics
----------------
  GPU-level
    • Engine busy % per class (Render/3D, Blitter, Compute, Video, VE)
    • Actual GT frequency (MHz)
    • GPU and package power (W)  [when RAPL is accessible]
    • GPU temperature (°C)       [from hwmon sysfs]
    • VRAM and shared memory usage (MB)
    • Throttle status

  Per-PID (from qmassa clis_stats via DRM fdinfo)
    • Total GPU busy %
    • Per-engine-class busy %
    • Process name

Prerequisites
-------------
  make install-qmassa   # installs qmassa via cargo

Usage
-----
  python src/gpu_pid_analyzer.py                  # one-shot snapshot
  python src/gpu_pid_analyzer.py --watch          # refresh every 2 s
  python src/gpu_pid_analyzer.py --duration 60    # run for 60 seconds
  python src/gpu_pid_analyzer.py --interval 1 --duration 120 --csv gpu.csv
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

# sys.path must be extended before importing project-local modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gpu_engine_defs import ENG_COLS as _ENG_COLS  # noqa: E402
from monitor_resources import _find_local_qmassa, _try_qmassa_local  # noqa: E402,I201
# ──────────────────────────────────────────────────────────────────────────────
# Display
# ──────────────────────────────────────────────────────────────────────────────


def _bar(pct: float, width: int = 12) -> str:
    filled = max(0, min(int(round(pct / 100 * width)), width))
    return '█' * filled + '░' * (width - filled)


def print_snapshot(snap: dict):  # pylint: disable=too-many-locals,too-many-statements
    """Pretty-print one qmassa snapshot to stdout."""
    ts = snap.get('ts', '')[:19].replace('T', ' ')

    if not snap.get('ok'):
        print(f'\n[{ts}]  qmassa unavailable (no DRM device or qmassa not installed)')
        print('  ▶  make install-qmassa')
        return

    freq_a = snap.get('act_freq_mhz', 0)
    pwr_g = snap.get('power_gpu_w', 0.0)
    pwr_p = snap.get('power_pkg_w', 0.0)
    temp = snap.get('temp_c')
    period = snap.get('period_ms', 0)
    drv = snap.get('drv_name', 'xe')
    throttle_str = '  ⚠ THROTTLE' if snap.get('throttled') else ''
    vram = snap.get('vram_used_mb', 0.0)
    smem = snap.get('smem_used_mb', 0.0)

    temp_str = f'  Temp: {temp:.0f} °C' if temp is not None else '  Temp: n/a'
    pwr_str = (f'  GPU: {pwr_g:.1f} W   Pkg: {pwr_p:.1f} W'
               if pwr_g else '  Power: RAPL unavailable')
    mem_str = f'  VRAM: {vram:.0f} MB   Shared: {smem:.0f} MB' if (vram or smem) else ''

    print(f'\n╔══ Intel GPU [{drv}]  [{ts}]  period={period:.0f} ms{throttle_str}')
    print('║')
    print(f'║  Frequency : {freq_a:>5} MHz actual')
    print(f'║  Power     :{pwr_str}')
    print(f'║  Temp      :{temp_str}')
    if mem_str:
        print(f'║  Memory    :{mem_str}')
    print('║')
    print('║  ── Engine Utilization ──────────────────────────────────────────')
    print(f'║   {"Engine":<12}  {"Busy":>6}  {"Bar":^14}')
    print(f'║   {"─"*12}  {"─"*6}  {"─"*14}')

    eng = snap.get('engines', {})
    for cls in _ENG_COLS:
        v = eng.get(cls, {})
        busy = v.get('busy', 0.0) if isinstance(v, dict) else float(v)
        busy_bar = _bar(busy)
        print(f'║   {cls:<12}  {busy:>5.1f}%  [{busy_bar}]')

    clients = snap.get('clients', [])
    if clients:
        print('║')
        print('║  ── Per-PID GPU Usage ───────────────────────────────────────────')
        hdr_eng = '  '.join(f'{c:<9}' for c in _ENG_COLS)
        print(f'║   {"PID":>7}  {"Process":<28}  {"Total":>6}  {hdr_eng}')
        print(f'║   {"─"*7}  {"─"*28}  {"─"*6}  {"─"*(9*len(_ENG_COLS)+2*(len(_ENG_COLS)-1))}')
        shown = 0
        for c in clients:
            if c['total'] < 0.05 and shown > 0:
                continue
            eng_vals = '  '.join(
                f'{c["engines"].get(cls, 0.0):>8.1f}%' for cls in _ENG_COLS
            )
            print(f'║   {c["pid"]:>7}  {c["name"]:<28}  {c["total"]:>5.1f}%  {eng_vals}')
            shown += 1

    print(f'╚{"═" * 68}')


# ──────────────────────────────────────────────────────────────────────────────
# CSV helpers
# ──────────────────────────────────────────────────────────────────────────────

def _csv_header() -> str:
    eng_hdrs = ','.join(f'{c}_busy_pct' for c in _ENG_COLS)
    return (f'timestamp,act_freq_mhz,power_gpu_w,power_pkg_w,temp_c,'
            f'vram_used_mb,smem_used_mb,throttled,{eng_hdrs},'
            f'top_pid,top_pid_name,top_pid_total_pct,'
            + ','.join(f'top_pid_{c}_pct' for c in _ENG_COLS))


def _snap_to_csv(snap: dict) -> str:
    if not snap.get('ok'):
        empty = ','.join([''] * (len(_ENG_COLS) + 3 + len(_ENG_COLS)))
        return f'{snap.get("ts", "")[:19]},,,,,,,{empty}'

    eng = snap.get('engines', {})
    eng_vals = ','.join(
        f'{eng.get(c, {}).get("busy", 0.0) if isinstance(eng.get(c), dict) else float(eng.get(c, 0)):.2f}'
        for c in _ENG_COLS
    )
    clients = snap.get('clients', [])
    top = clients[0] if clients else {}
    top_eng = ','.join(
        f'{top.get("engines", {}).get(c, 0.0):.2f}' for c in _ENG_COLS
    )
    temp = snap.get('temp_c', '')
    return (
        f'{snap["ts"][:19]},'
        f'{snap.get("act_freq_mhz", 0)},'
        f'{snap.get("power_gpu_w", 0)},{snap.get("power_pkg_w", 0)},'
        f'{temp if temp is not None else ""},'
        f'{snap.get("vram_used_mb", "")},{snap.get("smem_used_mb", "")},'
        f'{int(snap.get("throttled", False))},'
        f'{eng_vals},'
        f'{top.get("pid", "")},{top.get("name", "")},{top.get("total", "")},'
        f'{top_eng}'
    )


# ──────────────────────────────────────────────────────────────────────────────
# Main probe
# ──────────────────────────────────────────────────────────────────────────────

def collect_snapshot(interval: float = 2.0) -> dict:
    """Collect one GPU snapshot via qmassa.

    Returns a normalised dict with keys:
        ts, ok, source, act_freq_mhz, power_gpu_w, power_pkg_w, temp_c,
        engines, clients, throttled, vram_used_mb, smem_used_mb, period_ms
    """
    snap = _try_qmassa_local(interval=interval)
    if not snap:
        return {'ts': datetime.now().isoformat(), 'ok': False, 'source': 'unavailable'}
    snap['ok'] = True
    return snap


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main():  # pylint: disable=too-many-branches,too-many-statements
    """Parse CLI arguments and run the GPU sampling loop."""
    parser = argparse.ArgumentParser(
        description='Intel GPU PID Analyzer \u2013 per-process GPU usage with '
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
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress console output (useful with --csv)')
    args = parser.parse_args()

    # ── Open output files ──
    csv_fp = json_fp = None
    if args.csv:
        write_header = not os.path.exists(args.csv)
        csv_fp = open(  # pylint: disable=consider-using-with
            args.csv, 'a', buffering=1, encoding='utf-8')
        if write_header:
            csv_fp.write(_csv_header() + '\n')

    if args.json_log:
        json_fp = open(  # pylint: disable=consider-using-with
            args.json_log, 'a', buffering=1, encoding='utf-8')

    # ── Print preamble ──
    loop = args.watch or args.duration > 0
    deadline = (
        time.monotonic() + args.duration if args.duration > 0
        else float('inf')
    )

    print(f'Intel GPU PID Analyzer (qmassa)  \u2013  interval={args.interval}s')
    qmassa_bin = _find_local_qmassa()
    if qmassa_bin:
        print(f'  qmassa  : {qmassa_bin}')
    else:
        print('  qmassa  : NOT FOUND')
        print('    Install:  make install-qmassa')
    if not loop:
        print('  (one snapshot \u2014 use --watch or --duration N to loop)\n')
    else:
        print('  Press Ctrl-C to stop.\n')

    # ── Sampling loop ──
    try:
        while True:
            snap = collect_snapshot(interval=args.interval)

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
