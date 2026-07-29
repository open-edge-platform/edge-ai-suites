#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
r"""
compare_kpi.py — KPI regression detection against a stored baseline.

Loads a current benchmark result (Level 1 or Level 2 JSON) and diffs it
against a baseline file.  Exits non-zero when any KPI regresses beyond the
configured threshold.

Usage
-----
    python3 src/compare_kpi.py \
        --baseline tests/fixtures/baseline/kpi_level2.json \
        --current  session/kpi_level2.json \
        [--threshold 5.0] \
        [--report   report.json]

Exit codes
----------
    0  All KPIs within threshold.
    1  One or more regressions found.
    2  Error (bad arguments, unreadable files, unsupported schema).
"""

import argparse
import json
import sys
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────────────
#  KPI descriptors
# ──────────────────────────────────────────────────────────────────────────────

# (label, dotted-key-path, direction)
# direction: 'higher' = higher value is regression (latency/jitter/drop)
#            'lower'  = lower value is regression  (throughput)
_L1_KPIS = [
    ('throughput_hz',    'throughput_hz',    'lower'),
    ('mean_latency_ms',  'mean_latency_ms',  'higher'),
    ('mean_jitter_ms',   'mean_jitter_ms',   'higher'),
    ('max_jitter_ms',    'max_jitter_ms',    'higher'),
]

_L2_KPIS = [
    ('e2e_mean_ms',    'e2e_latency_ms.mean',  'higher'),
    ('e2e_p50_ms',     'e2e_latency_ms.p50',   'higher'),
    ('e2e_p90_ms',     'e2e_latency_ms.p90',   'higher'),
    ('e2e_p99_ms',     'e2e_latency_ms.p99',   'higher'),
    ('throughput_hz',  'throughput_hz',         'lower'),
    ('drop_rate_pct',  'drop_rate_pct',         'higher'),
]


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get(data: dict, dotted_key: str):
    """Traverse a nested dict with a dotted key path; return None if missing."""
    obj = data
    for part in dotted_key.split('.'):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
    return obj


def _pct_delta(baseline_val: float, current_val: float, direction: str) -> float:
    """Return signed regression percentage (positive = regression)."""
    if baseline_val == 0:
        # Avoid division by zero: treat any change in a higher-bad metric as 100% regression
        if direction == 'higher':
            return 100.0 if current_val > 0 else 0.0
        return 0.0
    if direction == 'higher':
        return (current_val - baseline_val) / abs(baseline_val) * 100.0
    # lower-is-regression: baseline higher than current is bad
    return (baseline_val - current_val) / abs(baseline_val) * 100.0


def _unit(label: str) -> str:
    """Return a display unit suffix for a KPI label."""
    if label.endswith('_hz'):
        return ' Hz'
    if label.endswith('_pct'):
        return ' %'
    if label.endswith('_ms'):
        return ' ms'
    return ''


# ──────────────────────────────────────────────────────────────────────────────
#  Core comparison
# ──────────────────────────────────────────────────────────────────────────────

def compare(baseline: dict, current: dict, threshold: float) -> list[dict]:
    """Compare KPIs and return a list of result dicts."""
    schema = baseline.get('schema_version', '')
    if schema.startswith('level2'):
        descriptors = _L2_KPIS
    elif schema.startswith('level1'):
        descriptors = _L1_KPIS
    else:
        print(f'  WARNING: unknown schema_version "{schema}", defaulting to Level 2 KPIs',
              file=sys.stderr)
        descriptors = _L2_KPIS

    results = []
    for label, key, direction in descriptors:
        b_val = _get(baseline, key)
        c_val = _get(current, key)

        if b_val is None or c_val is None:
            results.append({
                'metric':    label,
                'baseline':  b_val,
                'current':   c_val,
                'delta_pct': None,
                'status':    'SKIP',
                'passed':    True,
            })
            continue

        delta = _pct_delta(float(b_val), float(c_val), direction)
        passed = delta <= threshold
        results.append({
            'metric':    label,
            'baseline':  float(b_val),
            'current':   float(c_val),
            'delta_pct': round(delta, 2),
            'status':    'PASS' if passed else 'FAIL',
            'passed':    passed,
        })

    return results


# ──────────────────────────────────────────────────────────────────────────────
#  Reporting
# ──────────────────────────────────────────────────────────────────────────────

def _print_table(results: list[dict], baseline_path: str, current_path: str,
                 threshold: float) -> None:
    """Print an ASCII regression table."""
    col_w = 22
    print()
    print('  KPI Regression Report')
    print(f'  Baseline  : {baseline_path}')
    print(f'  Current   : {current_path}')
    print(f'  Threshold : {threshold:.1f}%')
    print()
    hdr = (f'  {"METRIC":<{col_w}}  {"BASELINE":>12}  {"CURRENT":>12}  '
           f'{"DELTA":>8}  STATUS')
    print(hdr)
    print('  ' + '─' * (len(hdr) - 2))

    for r in results:
        unit = _unit(r['metric'])
        if r['status'] == 'SKIP':
            b_str = 'n/a'
            c_str = 'n/a'
            d_str = '  n/a'
            icon  = '⚠️  SKIP'
        else:
            b_str = f'{r["baseline"]:.1f}{unit}'
            c_str = f'{r["current"]:.1f}{unit}'
            sign  = '+' if r['delta_pct'] >= 0 else ''
            d_str = f'{sign}{r["delta_pct"]:.1f}%'
            icon  = '✅ PASS' if r['passed'] else '❌ FAIL'
        print(f'  {r["metric"]:<{col_w}}  {b_str:>12}  {c_str:>12}  {d_str:>8}  {icon}')

    print()
    fails = [r for r in results if not r['passed']]
    if fails:
        print(f'  OVERALL: {len(fails)} regression(s) found  [threshold={threshold:.1f}%]')
    else:
        print(f'  OVERALL: All KPIs within threshold ({threshold:.1f}%)')
    print()


# ──────────────────────────────────────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────────────────────────────────────

def _parse_args(argv=None):
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(
        description='Compare benchmark KPI results against a stored baseline.',
    )
    p.add_argument('--baseline',  required=True,
                   help='Path to the baseline kpi.json or kpi_level2.json.')
    p.add_argument('--current',   required=True,
                   help='Path to the current-run kpi.json or kpi_level2.json.')
    p.add_argument('--threshold', type=float, default=5.0,
                   help='Regression threshold as a percentage (default: 5.0).')
    p.add_argument('--report',    default=None,
                   help='Optional path to write a JSON summary report.')
    return p.parse_args(argv)


def main(argv=None) -> int:
    """Entry point; returns exit code."""
    args = _parse_args(argv)

    # Load files
    try:
        baseline_path = Path(args.baseline)
        current_path  = Path(args.current)
        with open(baseline_path) as f:
            baseline = json.load(f)
        with open(current_path) as f:
            current = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f'  ERROR: {exc}', file=sys.stderr)
        return 2

    results = compare(baseline, current, args.threshold)
    _print_table(results, str(baseline_path), str(current_path), args.threshold)

    # Optional JSON report
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            'passed':     all(r['passed'] for r in results),
            'threshold':  args.threshold,
            'baseline':   str(baseline_path),
            'current':    str(current_path),
            'schema':     baseline.get('schema_version', 'unknown'),
            'regressions': [r for r in results if not r['passed']],
            'results':    results,
        }
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f'  Report written → {report_path}')

    fails = [r for r in results if not r['passed']]
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
