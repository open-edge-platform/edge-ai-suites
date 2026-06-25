#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
summarize_benchmark.py — Print and save an aggregate table for a bench run.

Reads kpi.json and kpi_level2_traced.json from each session sub-directory
inside a bench_YYYYMMDD_HHMMSS/ directory, prints a cross-run table to
stdout, and writes the same text to <bench_dir>/summary.txt.

Usage
-----
  python src/summarize_benchmark.py <bench_dir>
  make summarize-benchmark BENCH=<bench_dir>
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Optional

_TS_RE = re.compile(r'^\d{8}_\d{6}$')
_W = 76  # total display width


# ─────────────────────────────────────────────────────────────────────────────
# Small helpers (self-contained, no shared-module dependency)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_ts(name: str) -> Optional[datetime]:
    try:
        return datetime.strptime(name, '%Y%m%d_%H%M%S')
    except ValueError:
        return None


def _fmt_dur(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f'{h}h{m:02d}m'
    if m:
        return f'{m}m{sec:02d}s'
    return f'{sec}s'


def _load_json(path: Path) -> Optional[dict]:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _session_duration(sess: Path) -> Optional[float]:
    start_dt = _parse_ts(sess.name)
    if start_dt is None:
        return None
    start_s = start_dt.timestamp()
    mtimes = []
    for pattern in ('graph_timing.csv', 'resource_usage.log', 'gpu_usage.log',
                    'cpu_power.log', '*.log'):
        for p in sess.glob(pattern):
            try:
                mtimes.append(p.stat().st_mtime)
            except OSError:
                pass
    if not mtimes:
        try:
            mtimes = [p.stat().st_mtime for p in sess.rglob('*') if p.is_file()]
        except OSError:
            pass
    return max(0.0, max(mtimes) - start_s) if mtimes else None


def _count_goals(sess: Path) -> int:
    for log_file in sess.glob('*.log'):
        try:
            count = log_file.read_text(errors='replace').count('Goal was reached')
            if count:
                return count
        except OSError:
            pass
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# Per-session data extraction
# ─────────────────────────────────────────────────────────────────────────────

def _load_session(sess: Path) -> dict:
    row: dict = {
        'name':      sess.name,
        'dur_s':     _session_duration(sess),
        'e2e_mean':  None,
        'e2e_p90':   None,
        'thr_hz':    None,
        'drop_pct':  None,
        'goals':     _count_goals(sess),
        'throttled': False,
        'cpu_thr':   False,
        'gpu_thr':   False,
        'pipeline':  None,
        'host':      None,
        'has_l2':    False,
    }

    kpi1 = _load_json(sess / 'kpi.json')
    if kpi1:
        row['thr_hz'] = kpi1.get('throughput_hz')
        meta = kpi1.get('metadata') or {}
        row['host'] = meta.get('host')
        thermal = kpi1.get('thermal') or {}
        if thermal.get('cpu_throttled') or thermal.get('gpu_throttled'):
            row['throttled'] = True
            row['cpu_thr'] = bool(thermal.get('cpu_throttled'))
            row['gpu_thr'] = bool(thermal.get('gpu_throttled'))

    kpi2 = _load_json(sess / 'kpi_level2_traced.json')
    if kpi2:
        e2e = kpi2.get('e2e_latency_ms') or {}
        mean_ms = e2e.get('mean')
        if mean_ms is not None and mean_ms > 0.1:
            row['has_l2']   = True
            row['e2e_mean'] = mean_ms
            row['e2e_p90']  = e2e.get('p90')
            row['drop_pct'] = kpi2.get('drop_rate_pct')
            pipe = kpi2.get('pipeline') or {}
            inp  = pipe.get('input_topic')
            out  = pipe.get('output_topic')
            if inp and out:
                row['pipeline'] = f'{inp}  →  {out}'
            # prefer L2 throughput if available
            if kpi2.get('throughput_hz') is not None:
                row['thr_hz'] = kpi2['throughput_hz']

    return row


# ─────────────────────────────────────────────────────────────────────────────
# Table rendering
# ─────────────────────────────────────────────────────────────────────────────

def _bar(ch: str = '━') -> str:
    return ch * _W


def _ms(v: Optional[float]) -> str:
    return f'{v:6.1f}ms' if v is not None else '      —  '


def _hz(v: Optional[float]) -> str:
    return f'{v:6.1f}' if v is not None else '     —'


def _pct(v: Optional[float]) -> str:
    return f'{v:5.1f}%' if v is not None else '    —'


def _dur(v: Optional[float]) -> str:
    return f'{_fmt_dur(v):>6}' if v is not None else '     ?'


def build_table(bench_dir: Path, rows: list[dict]) -> str:
    lines = []

    # ── header ──
    bench_name = bench_dir.name
    n = len(rows)
    host = next((r['host'] for r in rows if r['host']), None)
    pipeline = next((r['pipeline'] for r in rows if r['pipeline']), None)

    lines.append(_bar())
    lines.append(f'  Benchmark Summary: {bench_name}   ({n} runs)')
    if host:
        lines.append(f'  Host: {host}')
    if pipeline:
        lines.append(f'  Pipeline: {pipeline}')
    lines.append(_bar())

    # ── column header ──
    lines.append(
        f'  {"Run":<19}  {"Dur":>6}  {"e2e mean":>9}  {"e2e p90":>8}'
        f'  {"thr Hz":>6}  {"drop":>5}  {"goals":>5}  {"":3}'
    )
    lines.append('  ' + '─' * (_W - 2))

    # ── per-run rows ──
    for r in rows:
        flag = ''
        if r['throttled']:
            parts = []
            if r['cpu_thr']:
                parts.append('CPU')
            if r['gpu_thr']:
                parts.append('GPU')
            flag = '⚠ ' + '+'.join(parts) if parts else '⚠ THR'
        elif not r['has_l2']:
            flag = 'no L2'
        elif r['e2e_mean'] is not None and r['e2e_mean'] > 60:
            flag = 'slow'

        goals_str = f'{r["goals"]:>5}' if r['goals'] else '    —'
        lines.append(
            f'  {r["name"]:<19}  {_dur(r["dur_s"])}'
            f'  {_ms(r["e2e_mean"])}'
            f'  {_ms(r["e2e_p90"])}'
            f'  {_hz(r["thr_hz"])}'
            f'  {_pct(r["drop_pct"])}'
            f'  {goals_str}'
            f'  {flag}'
        )

    # ── aggregate footer ──
    l2_rows = [r for r in rows if r['has_l2']]
    lines.append('  ' + '─' * (_W - 2))
    if l2_rows:
        def _avg(key):
            vals = [r[key] for r in l2_rows if r[key] is not None]
            return mean(vals) if vals else None

        total_goals = sum(r['goals'] for r in rows)
        lines.append(
            f'  {"Mean  (" + str(len(l2_rows)) + "/" + str(n) + " L2)":<19}'
            f'  {"":>6}'
            f'  {_ms(_avg("e2e_mean"))}'
            f'  {_ms(_avg("e2e_p90"))}'
            f'  {_hz(_avg("thr_hz"))}'
            f'  {_pct(_avg("drop_pct"))}'
            f'  {total_goals:>5}'
        )
    else:
        lines.append('  No Level 2 results available.')

    lines.append(_bar())
    return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def summarize(bench_dir: Path) -> int:
    if not bench_dir.is_dir():
        print(f'[Error] not a directory: {bench_dir}', file=sys.stderr)
        return 1

    session_dirs = sorted(
        [p for p in bench_dir.iterdir() if p.is_dir() and _TS_RE.match(p.name)],
        key=lambda p: p.name,
    )
    if not session_dirs:
        print(f'[Error] no session sub-directories found in {bench_dir}', file=sys.stderr)
        return 1

    rows = [_load_session(s) for s in session_dirs]
    table = build_table(bench_dir, rows)

    print(table)

    out_path = bench_dir / 'summary.txt'
    try:
        out_path.write_text(table + '\n')
        print(f'  Summary written → {out_path}')
    except OSError as exc:
        print(f'  [warn] could not write summary: {exc}', file=sys.stderr)

    print(_bar())
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Print and save an aggregate table for a benchmark run.',
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('bench_dir', help='Path to bench_YYYYMMDD_HHMMSS/ directory')
    args = parser.parse_args()
    sys.exit(summarize(Path(args.bench_dir)))


if __name__ == '__main__':
    main()
