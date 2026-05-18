#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Parse fast_mapping_node.log and populate the session kpi.json with real KPIs.

fast_mapping_node prints two kinds of structured output on shutdown:
  1. Periodic per-window stats (every ~3 s):
       fast_mapping got 52 images in 3.0s. Aligned 51. Processed 52 (17.18 Hz).
  2. A procedure-timing table followed by total elapsed / frequency:
       Procedure       Average Time  Total Time%  Count
       wait for a new frame   86.47  ms  63.25  175
       ...
       Total              110.10  ms  80.53  175
       Total elapsed time: 23.92  s   Frequency: 7.3 Hz

From these the script derives:
  - throughput_hz         → "Frequency" from the elapsed line
  - mean_latency_ms       → "Total - wait_for_frame" (actual compute latency)
  - per_node entry        → maps onto the Level 1 schema fields
  - jitter                → derived from window-to-window frequency variation
  - fastmapping_procedures.json sidecar → full procedure breakdown + raw windows
"""

import argparse
import json
import re
import sys
from pathlib import Path
from statistics import mean, pstdev


# ── Log parsing patterns ───────────────────────────────────────────────────────

_RE_WINDOW = re.compile(
    r'fast_mapping got (\d+) images in ([\d.]+)s\.'
    r' Aligned (\d+)\. Processed (\d+) \(([\d.]+) Hz\)'
)

# Procedure table rows:  "Name   value  unit   pct   count"
# Unit is either "ms" or "us".
_RE_PROC_ROW = re.compile(
    r'^([A-Za-z][A-Za-z0-9 /\-]+?)\s{2,}([\d.]+)\s+(ms|us)\s+([\d.]+)\s+(\d+)\s*$'
)

# Total row:  "Total   value   ms   pct   count"
_RE_TOTAL_ROW = re.compile(
    r'^Total\s+([\d.]+)\s+ms\s+([\d.]+)\s+(\d+)\s*$'
)

# Final summary line:  "Total elapsed time: 23.92   s    Frequency: 7.3 Hz"
_RE_ELAPSED = re.compile(
    r'Total elapsed time:\s*([\d.]+)\s*s\s+Frequency:\s*([\d.]+)\s*Hz'
)


def _to_ms(value: float, unit: str) -> float:
    """Convert a procedure time value to milliseconds."""
    return value if unit == 'ms' else value / 1000.0


def parse_log(log_path: Path) -> dict:
    """
    Parse fast_mapping_node.log and return a structured dict.

    Returns
    -------
    dict with keys:
      windows   : list of {total, aligned, processed, hz, duration_s}
      procedures: list of {name, avg_ms, pct, count}
      total_proc_ms : float – sum of all procedure avg times
      elapsed_s : float
      frequency_hz : float
      total_frames : int
    """
    text = log_path.read_text(errors='replace')
    lines = text.splitlines()

    windows = []
    procedures = []
    total_proc_ms = None
    elapsed_s = None
    frequency_hz = None
    in_table = False

    for line in lines:
        # Window stats
        m = _RE_WINDOW.search(line)
        if m:
            windows.append({
                'total':       int(m.group(1)),
                'duration_s':  float(m.group(2)),
                'aligned':     int(m.group(3)),
                'processed':   int(m.group(4)),
                'hz':          float(m.group(5)),
            })
            continue

        # Enter procedure table
        if 'Procedure' in line and 'Average Time' in line:
            in_table = True
            continue

        if in_table:
            # Separator lines
            if line.strip().startswith('---'):
                continue

            # Total row
            m = _RE_TOTAL_ROW.match(line.strip())
            if m:
                total_proc_ms = float(m.group(1))
                continue

            # Individual procedure row
            m = _RE_PROC_ROW.match(line.strip())
            if m:
                procedures.append({
                    'name':   m.group(1).strip(),
                    'avg_ms': _to_ms(float(m.group(2)), m.group(3)),
                    'pct':    float(m.group(4)),
                    'count':  int(m.group(5)),
                })
                continue

        # Final elapsed / frequency line
        m = _RE_ELAPSED.search(line)
        if m:
            elapsed_s    = float(m.group(1))
            frequency_hz = float(m.group(2))

    # If no procedure table, derive total_frames and elapsed from windows
    has_proc_table = bool(procedures)
    if has_proc_table:
        total_frames = max((p['count'] for p in procedures), default=0)
    else:
        # Sum processed counts from all windows (warm-up + steady-state)
        total_frames = sum(w['processed'] for w in windows)
        # Derive elapsed and frequency from window data
        if windows and elapsed_s is None:
            total_dur = sum(w['duration_s'] for w in windows)
            elapsed_s = total_dur
        if windows and frequency_hz is None:
            steady = [w for w in windows if w['hz'] >= 1.0]
            if steady:
                total_processed = sum(w['processed'] for w in steady)
                total_dur = sum(w['duration_s'] for w in steady)
                frequency_hz = total_processed / total_dur if total_dur > 0 else None

    return {
        'windows':        windows,
        'procedures':     procedures,
        'has_proc_table': has_proc_table,
        'total_proc_ms':  total_proc_ms,
        'elapsed_s':      elapsed_s,
        'frequency_hz':   frequency_hz,
        'total_frames':   total_frames,
    }


def _derive_kpis(parsed: dict) -> dict:
    """
    Derive KPI values from the parsed log.

    compute_latency_ms
        = total_proc_ms − wait_for_frame_ms
        This is the actual input→output processing time excluding the blocking
        wait for the next camera frame.  It reflects how long the pipeline would
        take on a real-time sensor stream.

    Jitter
        Derived from the per-window throughput variation.  Each window gives an
        average frame period; we compute mean absolute deviation across windows
        as mean_jitter, and max−min as max_jitter.  The initial TF warm-up
        window (hz < 1) is excluded from jitter because it reflects TF tree
        initialisation, not pipeline variance.
    """
    procs = {p['name'].lower().replace(' ', '_'): p for p in parsed['procedures']}

    wait_key = next(
        (k for k in procs if 'wait' in k or 'new_frame' in k or 'frame' in k),
        None
    )
    wait_ms = procs[wait_key]['avg_ms'] if wait_key else 0.0
    total_proc_ms = parsed['total_proc_ms'] or 0.0

    if parsed['has_proc_table']:
        compute_ms = max(total_proc_ms - wait_ms, 0.0)
    else:
        # Fallback: derive from steady-state window average period.
        # Window Hz includes the inter-frame wait, so this is an upper-bound
        # latency but still useful as a throughput-derived KPI.
        steady = [w for w in parsed['windows'] if w['hz'] >= 1.0]
        compute_ms = (1000.0 / mean([w['hz'] for w in steady])) if steady else 0.0

    # Steady-state windows only (exclude warm-up where hz < 1)
    steady_windows = [w for w in parsed['windows'] if w['hz'] >= 1.0]
    if steady_windows:
        periods_ms = [1000.0 / w['hz'] for w in steady_windows]
        period_mean = mean(periods_ms)
        deviations  = [abs(p - period_mean) for p in periods_ms]
        mean_jitter = mean(deviations)
        max_jitter  = max(periods_ms) - min(periods_ms)
        period_std  = pstdev(periods_ms)
    else:
        mean_jitter = 0.0
        max_jitter  = 0.0
        period_std  = 0.0

    # Approximate per-frame latency distribution using window-weighted periods.
    # We expand each window into its frame count to compute percentiles.
    all_periods_ms = []
    for w in steady_windows:
        period = 1000.0 / w['hz']
        all_periods_ms.extend([period] * w['processed'])

    if all_periods_ms:
        all_periods_ms.sort()
        n = len(all_periods_ms)
        p50 = all_periods_ms[n // 2]
        p90 = all_periods_ms[int(n * 0.90)]
    else:
        p50 = compute_ms
        p90 = compute_ms

    return {
        'compute_latency_ms': round(compute_ms, 3),
        'total_proc_ms':      round(total_proc_ms, 3),
        'wait_ms':            round(wait_ms, 3),
        'throughput_hz':      parsed['frequency_hz'],
        'num_samples':        parsed['total_frames'],
        'mean_jitter_ms':     round(mean_jitter, 3),
        'max_jitter_ms':      round(max_jitter, 3),
        'jitter_stdev_ms':    round(period_std, 3),
        'period_mean_ms':     round(period_mean if steady_windows else compute_ms, 3),
        'period_p50_ms':      round(p50, 3),
        'period_p90_ms':      round(p90, 3),
        'period_min_ms':      round(min(all_periods_ms) if all_periods_ms else 0.0, 3),
        'period_max_ms':      round(max(all_periods_ms) if all_periods_ms else 0.0, 3),
    }


def _patch_kpi(kpi_path: Path, parsed: dict, kpis: dict,
               input_topic: str, output_topic: str) -> None:
    """Load kpi.json, fill in real values, and write back."""
    kpi = json.loads(kpi_path.read_text())

    kpi['throughput_hz']  = kpis['throughput_hz']
    kpi['mean_latency_ms'] = kpis['compute_latency_ms']

    # Jitter fields — use period-based values across windows
    kpi['mean_jitter_ms']  = kpis['mean_jitter_ms']
    kpi['max_jitter_ms']   = kpis['max_jitter_ms']
    kpi['min_jitter_ms']   = 0.0
    kpi['jitter_stdev_ms'] = kpis['jitter_stdev_ms']

    # per_node entry
    kpi.setdefault('per_node', {})['/fast_mapping_node'] = {
        'throughput_hz':    kpis['throughput_hz'],
        'mean_latency_ms':  kpis['compute_latency_ms'],
        'mean_jitter_ms':   kpis['mean_jitter_ms'],
        'max_jitter_ms':    kpis['max_jitter_ms'],
        'num_samples':      kpis['num_samples'],
        'primary_input':    input_topic,
        'primary_output':   output_topic,
        'pipeline_stage':   'Perception',
    }

    # pairs entry — one entry representing the depth→map pair.
    # mean_ms is the compute latency (actual processing time, excl. idle wait).
    # Percentile spread uses ±jitter scaled relative to compute latency since we
    # only have windowed averages, not per-frame latency samples.
    compute_ms = kpis['compute_latency_ms']
    half_jitter = kpis['max_jitter_ms'] / 2.0
    c_min = round(max(compute_ms - half_jitter, 0.0), 3)
    c_max = round(compute_ms + half_jitter, 3)
    c_p50 = round(compute_ms, 3)
    c_p90 = round(compute_ms + half_jitter * 0.8, 3)
    c_std = kpis['jitter_stdev_ms']

    pair = {
        'node':     '/fast_mapping_node',
        'input':    input_topic,
        'output':   output_topic,
        'n':        kpis['num_samples'],
        'mean_ms':  compute_ms,
        'stdev_ms': c_std,
        'min_ms':   c_min,
        'p50_ms':   c_p50,
        'p90_ms':   c_p90,
        'max_ms':   c_max,
    }
    # Avoid duplicate pairs on re-runs
    kpi['pairs'] = [
        p for p in kpi.get('pairs', [])
        if not (p.get('node') == '/fast_mapping_node'
                and p.get('input') == input_topic)
    ]
    kpi['pairs'].append(pair)

    kpi_path.write_text(json.dumps(kpi, indent=2))
    print(f'  kpi.json patched   → {kpi_path}')


def _write_procedures(session_dir: Path, parsed: dict, kpis: dict) -> None:
    """Write the per-procedure breakdown to fastmapping_procedures.json."""
    out = {
        'total_frames':      parsed['total_frames'],
        'elapsed_s':         parsed['elapsed_s'],
        'frequency_hz':      parsed['frequency_hz'],
        'total_proc_ms':     kpis['total_proc_ms'],
        'compute_latency_ms': kpis['compute_latency_ms'],
        'procedures':        [
            {
                'name':   p['name'],
                'avg_ms': round(p['avg_ms'], 4),
                'pct':    p['pct'],
                'count':  p['count'],
            }
            for p in parsed['procedures']
        ],
        'windows': [
            {
                'total':      w['total'],
                'aligned':    w['aligned'],
                'processed':  w['processed'],
                'hz':         w['hz'],
                'duration_s': w['duration_s'],
            }
            for w in parsed['windows']
        ],
    }
    out_path = session_dir / 'fastmapping_procedures.json'
    out_path.write_text(json.dumps(out, indent=2))
    print(f'  procedures written → {out_path}')


def _print_summary(parsed: dict, kpis: dict) -> None:
    """Print a human-readable summary to stdout."""
    print('')
    print('  ┌─ fast_mapping_node Performance ─────────────────────┐')
    print(f'  │  Frames processed : {kpis["num_samples"]:>5}  '
          f'({kpis["throughput_hz"]:.1f} Hz overall)')
    print(f'  │  Elapsed          : {parsed["elapsed_s"]:.2f} s')
    print('  ├─ Per-procedure (avg / frame) ────────────────────────┤')
    if parsed['has_proc_table']:
        for p in parsed['procedures']:
            if p['avg_ms'] >= 0.01:
                print(f'  │  {p["name"]:<24} {p["avg_ms"]:>8.2f} ms  ({p["pct"]:.1f}%)')
            else:
                print(f'  │  {p["name"]:<24} {p["avg_ms"]*1000:>8.2f} µs  ({p["pct"]:.2f}%)')
        total = parsed['total_proc_ms']
        print(f'  │  {"Total":<24} {total:>8.2f} ms')
    else:
        print('  │  (procedure table not available — window-based fallback)')
    print('  ├─ Derived KPIs ────────────────────────────────────────┤')
    print(f'  │  Compute latency  : {kpis["compute_latency_ms"]:>7.2f} ms'
          f'  (excl. wait-for-frame)')
    print(f'  │  Mean jitter      : {kpis["mean_jitter_ms"]:>7.2f} ms'
          f'  (window-to-window)')
    print(f'  │  Max jitter       : {kpis["max_jitter_ms"]:>7.2f} ms')
    print('  └──────────────────────────────────────────────────────┘')
    print('')


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Parse fast_mapping_node.log and patch session kpi.json.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap_dedent('''\
        Examples:
          # Auto-discover log and kpi in session dir:
          uv run python src/analyze_fastmapping_log.py --session monitoring_sessions/fastmapping/20260513_130427

          # Explicit paths:
          uv run python src/analyze_fastmapping_log.py \\
            --log monitoring_sessions/fastmapping/20260513_130427/fast_mapping_node.log \\
            --kpi monitoring_sessions/fastmapping/20260513_130427/kpi.json
        '''),
    )
    parser.add_argument(
        '--session', '-s',
        default=None,
        metavar='DIR',
        help='Session directory — auto-discovers fast_mapping_node.log and kpi.json inside.',
    )
    parser.add_argument(
        '--log',
        default=None,
        metavar='FILE',
        help='Path to fast_mapping_node.log (overrides --session log discovery).',
    )
    parser.add_argument(
        '--kpi',
        default=None,
        metavar='FILE',
        help='Path to kpi.json to patch (overrides --session kpi discovery).',
    )
    parser.add_argument(
        '--input-topic',
        default='/camera/aligned_depth_to_color/image_raw',
        metavar='TOPIC',
        help='Primary input topic for the fast_mapping_node pair entry.',
    )
    parser.add_argument(
        '--output-topic',
        default='/world/map',
        metavar='TOPIC',
        help='Primary output topic for the fast_mapping_node pair entry.',
    )
    parser.add_argument(
        '--no-patch',
        action='store_true',
        help='Parse and print summary only; do not modify kpi.json.',
    )
    args = parser.parse_args()

    # Resolve paths
    if args.session:
        session_dir = Path(args.session).resolve()
        log_path = Path(args.log).resolve() if args.log else session_dir / 'fast_mapping_node.log'
        kpi_path = Path(args.kpi).resolve() if args.kpi else session_dir / 'kpi.json'
    elif args.log:
        log_path = Path(args.log).resolve()
        session_dir = log_path.parent
        kpi_path = Path(args.kpi).resolve() if args.kpi else session_dir / 'kpi.json'
    else:
        parser.error('Provide --session DIR or --log FILE.')
        return 1

    if not log_path.exists():
        print(f'ERROR: log file not found: {log_path}', file=sys.stderr)
        return 1

    parsed = parse_log(log_path)

    if not parsed['windows']:
        print('ERROR: No frame windows found in log — did the node receive any data?',
              file=sys.stderr)
        return 1

    if not parsed['has_proc_table']:
        print('  ⚠ Procedure table not captured (node was not shut down gracefully).')
        print('    KPIs derived from window stats only — compute latency is window-average.')

    kpis = _derive_kpis(parsed)
    _print_summary(parsed, kpis)

    if args.no_patch:
        return 0

    _write_procedures(session_dir, parsed, kpis)

    if kpi_path.exists():
        _patch_kpi(kpi_path, parsed, kpis, args.input_topic, args.output_topic)
    else:
        print(f'  ⚠ kpi.json not found at {kpi_path} — skipping patch', file=sys.stderr)

    return 0


# Inline textwrap.dedent so the script has no unexpected import at module level
def textwrap_dedent(text: str) -> str:
    import textwrap
    return textwrap.dedent(text)


if __name__ == '__main__':
    sys.exit(main())
