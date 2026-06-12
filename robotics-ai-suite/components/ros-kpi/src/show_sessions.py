#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
show_sessions.py — Tree view of all benchmark sessions.

Walks monitoring_sessions/ and prints a structured summary:

  monitoring_sessions/
  ├── wandering/
  │   ├── bench_20260521_123522/   10 runs  │ 50m total
  │   │   ├── 20260521_131229   5m00s  e2e=35.3ms  thr=16.2Hz  drop=0.1%  goals=12
  │   │   └── 20260521_131636   5m00s  ⚠ level2 failed
  │   └── 20260513_003015       5m00s  thr=18.5Hz  lat=42ms
  └── fastmapping/
      └── 20260513_130427       4m59s  thr=2.1Hz   lat=35ms

Usage
-----
  python src/show_sessions.py
  python src/show_sessions.py --root /opt/ros/jazzy/benchmarking/monitoring_sessions
  make show-sessions
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_TS_RE = re.compile(r'^(\d{8}_\d{6})$')
_BENCH_RE = re.compile(r'^bench_(\d{8}_\d{6})$')


def _parse_ts(name: str) -> Optional[datetime]:
    """Parse YYYYMMDD_HHMMSS directory name into a datetime, or None."""
    try:
        return datetime.strptime(name, '%Y%m%d_%H%M%S')
    except ValueError:
        return None


def _fmt_dur(seconds: float) -> str:
    """Format a duration in seconds as e.g. '5m02s' or '1h03m'."""
    if seconds < 0:
        return '?'
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f'{h}h{m:02d}m'
    if m:
        return f'{m}m{s:02d}s'
    return f'{s}s'


def _session_duration(session_dir: Path) -> Optional[float]:
    """
    Estimate session duration in seconds.

    Uses the timestamp embedded in the directory name as the start time.
    The end time is taken from the mtime of files written during the live
    session (graph_timing.csv, resource_usage.log, *.log) to avoid being
    skewed by kpi.json files generated long after the fact.
    """
    start_dt = _parse_ts(session_dir.name)
    if start_dt is None:
        return None
    start_s = start_dt.timestamp()

    # Prefer files that are only written during the live session run.
    live_globs = ['graph_timing.csv', 'resource_usage.log', 'gpu_usage.log',
                  'npu_usage.log', 'cpu_power.log', '*.log']
    mtimes = []
    for pattern in live_globs:
        for p in session_dir.glob(pattern):
            try:
                mtimes.append(p.stat().st_mtime)
            except OSError:
                pass
    if not mtimes:
        # fallback: any file
        try:
            mtimes = [p.stat().st_mtime for p in session_dir.rglob('*') if p.is_file()]
        except OSError:
            pass
    if not mtimes:
        return None
    return max(0.0, max(mtimes) - start_s)


def _load_json(path: Path) -> Optional[dict]:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _count_goals(session_dir: Path) -> Optional[int]:
    """Count 'Goal was reached' occurrences in any launch log under session_dir."""
    for log_file in session_dir.glob('*.log'):
        try:
            text = log_file.read_text(errors='replace')
            count = text.count('Goal was reached')
            if count > 0:
                return count
        except OSError:
            pass
    return None


def _session_summary(session_dir: Path) -> dict:
    """
    Extract key metrics for a single session directory.

    Returns a dict with: dur_s, thr_hz, lat_ms, e2e_ms, drop_pct, goals,
    has_kpi, has_l2, host, throttled.
    """
    info: dict = {
        'dur_s':     _session_duration(session_dir),
        'thr_hz':    None,
        'lat_ms':    None,
        'e2e_ms':    None,
        'drop_pct':  None,
        'goals':     _count_goals(session_dir),
        'has_kpi':   False,
        'has_l2':    False,
        'host':      None,
        'throttled': False,
        'cpu_thr':   False,
        'gpu_thr':   False,
    }

    kpi1 = _load_json(session_dir / 'kpi.json')
    if kpi1:
        info['has_kpi'] = True
        info['thr_hz']  = kpi1.get('throughput_hz')
        info['lat_ms']  = kpi1.get('mean_latency_ms')
        meta = kpi1.get('metadata') or {}
        info['host'] = meta.get('host')
        thermal = kpi1.get('thermal') or {}
        if thermal.get('cpu_throttled') or thermal.get('gpu_throttled'):
            info['throttled'] = True
            info['cpu_thr'] = bool(thermal.get('cpu_throttled'))
            info['gpu_thr'] = bool(thermal.get('gpu_throttled'))

    kpi2 = _load_json(session_dir / 'kpi_level2_traced.json')
    if kpi2:
        e2e = kpi2.get('e2e_latency_ms') or {}
        mean = e2e.get('mean')
        # Skip degenerate 0ms results (entry == exit topic bug)
        if mean is not None and mean > 0.1:
            info['has_l2']   = True
            info['e2e_ms']   = mean
            info['drop_pct'] = kpi2.get('drop_rate_pct')
            # L2 throughput is the pipeline output rate — more meaningful than L1
            if kpi2.get('throughput_hz') is not None:
                info['thr_hz'] = kpi2['throughput_hz']

    return info


def _fmt_session_line(name: str, info: dict, prefix: str) -> str:
    """Format one session line for the tree."""
    parts = [f'{prefix}{name}']

    dur = info['dur_s']
    parts.append(f'  {_fmt_dur(dur) if dur is not None else "?":>6}')

    if info['has_l2']:
        parts.append(f'  e2e={info["e2e_ms"]:5.1f}ms')
        if info['thr_hz'] is not None:
            parts.append(f'  thr={info["thr_hz"]:5.1f}Hz')
        if info['drop_pct'] is not None:
            parts.append(f'  drop={info["drop_pct"]:4.1f}%')
    elif info['has_kpi']:
        if info['thr_hz'] is not None:
            parts.append(f'  thr={info["thr_hz"]:5.1f}Hz')
        if info['lat_ms'] is not None:
            parts.append(f'  lat={info["lat_ms"]:5.1f}ms')
    else:
        parts.append('  (no kpi.json)')

    if info['goals']:
        parts.append(f'  goals={info["goals"]}')

    if info['throttled']:
        hw = []
        if info['cpu_thr']:
            hw.append('CPU')
        if info['gpu_thr']:
            hw.append('GPU')
        label = '+'.join(hw) if hw else 'THR'
        parts.append(f'  ⚠ {label} throttled')

    return ''.join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# Tree rendering
# ──────────────────────────────────────────────────────────────────────────────

def _render_type_dir(type_dir: Path, is_last_type: bool):
    """Render one scenario type directory (e.g. wandering/, fastmapping/)."""
    children = sorted(type_dir.iterdir(), key=lambda p: p.name)

    bench_dirs   = [p for p in children if p.is_dir() and _BENCH_RE.match(p.name)]
    session_dirs = [p for p in children if p.is_dir() and _TS_RE.match(p.name)]

    # Sort each group by name (= chronological)
    bench_dirs.sort(key=lambda p: p.name)
    session_dirs.sort(key=lambda p: p.name)

    all_items = bench_dirs + session_dirs
    all_items.sort(key=lambda p: p.name)

    type_prefix = '└── ' if is_last_type else '├── '
    child_indent = '    ' if is_last_type else '│   '

    # Count totals for the type header
    total_runs = sum(
        len([c for c in p.iterdir() if c.is_dir() and _TS_RE.match(c.name)])
        for p in bench_dirs
    ) + len(session_dirs)

    print(f'{type_prefix}{type_dir.name}/   ({total_runs} runs total)')

    for idx, item in enumerate(all_items):
        is_last = idx == len(all_items) - 1
        item_prefix = f'{child_indent}{"└── " if is_last else "├── "}'
        item_indent = f'{child_indent}{"    " if is_last else "│   "}'

        if _BENCH_RE.match(item.name):
            _render_bench_dir(item, item_prefix, item_indent)
        elif _TS_RE.match(item.name):
            info = _session_summary(item)
            print(_fmt_session_line(item.name, info, item_prefix))


def _render_bench_dir(bench_dir: Path, prefix: str, indent: str):
    """Render one bench_YYYYMMDD_HHMMSS directory with its sub-sessions."""
    sub_sessions = sorted(
        [p for p in bench_dir.iterdir() if p.is_dir() and _TS_RE.match(p.name)],
        key=lambda p: p.name,
    )
    n = len(sub_sessions)

    # Aggregate totals across sessions
    total_dur = 0.0
    total_goals = 0
    any_goals = False

    summaries = []
    for s in sub_sessions:
        info = _session_summary(s)
        summaries.append((s, info))
        if info['dur_s']:
            total_dur += info['dur_s']
        if info['goals']:
            total_goals += info['goals']
            any_goals = True

    dur_str = _fmt_dur(total_dur) if total_dur else '?'
    goals_str = f'  goals={total_goals}' if any_goals else ''
    print(f'{prefix}{bench_dir.name}/   {n} runs │ {dur_str} total{goals_str}')

    for idx, (sess_dir, info) in enumerate(summaries):
        is_last = idx == len(summaries) - 1
        line_prefix = f'{indent}{"└── " if is_last else "├── "}'
        print(_fmt_session_line(sess_dir.name, info, line_prefix))


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def show(root: Path):
    if not root.exists():
        print(f'[Error] sessions root not found: {root}', file=sys.stderr)
        sys.exit(1)

    type_dirs = sorted(
        [p for p in root.iterdir() if p.is_dir()],
        key=lambda p: p.name,
    )
    if not type_dirs:
        print(f'{root}/  (empty — no sessions yet)')
        return

    print(f'{root}/')
    for idx, td in enumerate(type_dirs):
        _render_type_dir(td, is_last_type=idx == len(type_dirs) - 1)


def main():
    parser = argparse.ArgumentParser(
        description='Show all benchmark sessions in a tree view.',
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--root', '-r',
        default='monitoring_sessions',
        help='Root directory to scan (default: monitoring_sessions)',
    )
    args = parser.parse_args()
    show(Path(args.root))


if __name__ == '__main__':
    main()
