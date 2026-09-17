#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
aggregate_kpi.py  —  Cross-run KPI aggregation for wandering benchmark sessions.
=================================================================================
Reads kpi.json files produced by:
    analyze_trigger_latency.py --json-out SESSION_DIR/kpi.json

from every run inside a benchmark directory, then computes cross-run statistics
to identify consistently slow pairs (bottlenecks) vs occasional spikes.

Usage
-----
  # Aggregate a completed benchmark (25 runs)
  python3 src/aggregate_kpi.py monitoring_sessions/wandering/bench_20260318_120000

  # Require pair to appear in at least N runs (default: half of total runs)
  python3 src/aggregate_kpi.py BENCH_DIR --min-runs 5

  # Also write a CSV for spreadsheet analysis
  python3 src/aggregate_kpi.py BENCH_DIR --csv-out BENCH_DIR/results.csv

  # Show only a specific node
  python3 src/aggregate_kpi.py BENCH_DIR --node controller_server
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from log_config import configure_logging, get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
#  Health colour (same thresholds as analyze_trigger_latency.py)
# ──────────────────────────────────────────────────────────────────────────────

def _health(mean_ms: float) -> str:
    if mean_ms < 10:   return '✅'
    if mean_ms < 50:   return '🟡'
    if mean_ms < 200:  return '🟠'
    return '🔴'


def _consistency(cv_pct: float) -> str:
    """Variance indicator: how consistent is this pair across runs."""
    if cv_pct < 10:  return '◆'   # Very consistent
    if cv_pct < 25:  return '◇'   # Moderate variance
    if cv_pct < 50:  return '△'   # High variance
    return '✗'                    # Unstable — may be RTF-sensitive


# ──────────────────────────────────────────────────────────────────────────────
#  Pipeline stage classification
# ──────────────────────────────────────────────────────────────────────────────

PIPELINE_ORDER = ['Sensor', 'Perception', 'Planning', 'Control', 'Other']


def _classify(node: str, inp: str, out: str) -> str:  # noqa: ARG001
    """
    Assign a pipeline stage to a (node, input, output) pair.

    Stages (in execution order):
      Sensor     — raw data ingestion: sim bridge, joint/state publishers
      Perception — SLAM and costmap construction: rtabmap, local/global costmap
      Planning   — path & behaviour planning: route_server, behavior_server,
                   planner_server, bt_navigator
      Control    — velocity generation and safety: controller_server,
                   velocity_smoother, collision_monitor, docking_server
      Other      — everything else
    """
    n = node.split('/')[-1]
    if n in ('ros_gz_bridge', 'robot_state_publisher'):
        return 'Sensor'
    if n in ('rtabmap', 'local_costmap', 'global_costmap'):
        return 'Perception'
    if n in ('route_server', 'behavior_server', 'planner_server', 'bt_navigator'):
        return 'Planning'
    if n in ('controller_server', 'velocity_smoother', 'collision_monitor',
             'docking_server'):
        return 'Control'
    return 'Other'


# ──────────────────────────────────────────────────────────────────────────────
#  Core aggregation
# ──────────────────────────────────────────────────────────────────────────────

def load_bench(bench_dir: Path) -> tuple[int, dict]:
    """
    Returns (total_runs, per_pair_data).

    per_pair_data: {(node, input, output): [run_dict, ...]}
    where run_dict is the raw pair dict from kpi.json plus 'run_id'.
    """
    json_files = sorted(bench_dir.glob('*/kpi.json'))
    if not json_files:
        logger.error("No kpi.json files found under %s", bench_dir)
        logger.error("Re-run the scenario's *_run.sh script with --record, or check that "
                     "--record was used for this benchmark.")
        sys.exit(1)

    per_pair: Dict[tuple, List[dict]] = defaultdict(list)
    for jf in json_files:
        run_id = jf.parent.name
        try:
            with open(jf) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("skipping %s: %s", jf, e)
            continue
        for pair in data.get('pairs', []):
            key = (pair['node'], pair['input'], pair['output'])
            per_pair[key].append({**pair, 'run_id': run_id})

    return len(json_files), per_pair


def aggregate(per_pair: dict, total_runs: int, min_runs: int,
              node_filter: Optional[str] = None) -> List[dict]:
    """
    Compute cross-run statistics for every (node, input, output) pair seen in
    at least min_runs runs.  Returns a list sorted by worst_p90 descending.
    """
    results = []
    for (node, inp, out), run_pairs in per_pair.items():
        if node_filter and node_filter not in node:
            continue
        if len(run_pairs) < min_runs:
            continue

        means   = [p['mean_ms']  for p in run_pairs]
        p90s    = [p['p90_ms']   for p in run_pairs]
        p50s    = [p['p50_ms']   for p in run_pairs]
        stdevs  = [p['stdev_ms'] for p in run_pairs]
        ns      = [p['n']        for p in run_pairs]
        fps_vals = [p['fps'] for p in run_pairs if p.get('fps') is not None]

        mean_of_means   = statistics.mean(means)
        stdev_of_means  = statistics.stdev(means) if len(means) > 1 else 0.0
        cv_pct          = (stdev_of_means / mean_of_means * 100) if mean_of_means > 0 else 0.0

        results.append({
            'node':          node,
            'input':         inp,
            'output':        out,
            'category':      _classify(node, inp, out),
            'runs_seen':     len(run_pairs),
            'total_runs':    total_runs,
            # Per-run mean statistics
            'mean_ms':       mean_of_means,
            'stdev_runs':    stdev_of_means,
            'cv_pct':        cv_pct,
            'min_mean_ms':   min(means),
            'max_mean_ms':   max(means),
            # p90 statistics across runs
            'mean_p90_ms':   statistics.mean(p90s),
            'worst_p90_ms':  max(p90s),
            'best_p90_ms':   min(p90s),
            # p50 statistics
            'mean_p50_ms':   statistics.mean(p50s),
            # Within-run stdev (avg across runs = typical jitter per run)
            'mean_stdev_ms': statistics.mean(stdevs),
            # Average sample count per run
            'mean_n':        statistics.mean(ns),
            # Throughput across runs
            'mean_fps':      statistics.mean(fps_vals) if fps_vals else None,
            'fps_stdev':     statistics.stdev(fps_vals) if len(fps_vals) > 1 else 0.0,
        })

    results.sort(key=lambda x: (
        PIPELINE_ORDER.index(x['category']) if x['category'] in PIPELINE_ORDER
        else len(PIPELINE_ORDER),
        -x['worst_p90_ms'],
    ))
    return results


# ──────────────────────────────────────────────────────────────────────────────
#  Console report
# ──────────────────────────────────────────────────────────────────────────────

W = 140

_CAT_LABELS = {
    'Sensor':     'Sensor  ',
    'Perception': 'Percept ',
    'Planning':   'Planning',
    'Control':    'Control ',
    'Other':      'Other   ',
}


def print_report(results: List[dict], bench_dir: Path, total_runs: int) -> None:
    if not results:
        logger.warning("No pairs met the minimum-runs threshold.")
        return

    logger.debug("\n" + '━' * W)
    logger.debug("  Benchmark: %s  |  %s runs x 120 s", bench_dir.name, total_runs)
    logger.debug("  Columns: Hz = avg throughput  mean = avg(mean_ms across runs)  ±stdev  cv%s = consistency", "%")
    logger.debug("           p90 = avg(p90_ms)  worst_p90 = max across all runs")
    logger.debug("  Legend (health): ✅<10ms  🟡<50ms  🟠<200ms  🔴≥200ms")
    logger.debug("  Legend (consistency ◆<10%scv  ◇<25%s  △<50%s  ✗≥50%s — RTF-sensitive)", "%", "%", "%", "%")
    logger.debug("  Pipeline stages (in order): Sensor → Perception → Planning → Control → Other")
    logger.debug('━' * W)
    _pm = '±'
    logger.debug("  %3s  %-10s %-22s %-30s %-26s %8s %8s %1s %6s %5s %8s %9s %6s",
                '#', 'Stage', 'Node', 'Input', 'Output',
                'Hz', 'mean', _pm, 'stdev', 'cv%', 'p90', 'worst_p90', 'runs')
    logger.debug('━' * W)

    visible = results[:40]
    current_cat = None
    for i, r in enumerate(visible, 1):
        cat = r.get('category', 'Other')
        if cat != current_cat:
            current_cat = cat
            banner = f" {cat.upper()} "
            side = (W - len(banner) - 2) // 2
            logger.debug("  %s%s%s", '─' * side, banner, '─' * (W - 2 - side - len(banner)))
        h   = _health(r['mean_ms'])
        c   = _consistency(r['cv_pct'])
        cat_label = _CAT_LABELS.get(cat, 'Other   ')
        nd  = r['node'].split('/')[-1][:20]
        inp = r['input'][-29:] if len(r['input']) > 29 else r['input']
        out = r['output'][-25:] if len(r['output']) > 25 else r['output']
        run_frac = f"{r['runs_seen']:>2}/{r['total_runs']}"
        fps = r.get('mean_fps')
        fps_s = f'{fps:.1f}' if fps is not None else '—'
        logger.debug("  %3d  %s%s %s %-20s %-30s %-26s %8s %7.1fms %5.1f %5.1f%% %7.1fms %8.1fms %6s",
                    i, h, c, cat_label, nd, inp, out,
                    fps_s, r['mean_ms'], r['stdev_runs'], r['cv_pct'],
                    r['mean_p90_ms'], r['worst_p90_ms'], run_frac)

    logger.debug('━' * W)
    if len(results) > 40:
        logger.debug("  … %d more pairs not shown (use --node to filter)", len(results) - 40)
    logger.debug("")

    # Bottleneck summary
    red_pairs = [r for r in results if r['mean_ms'] >= 200 and r['cv_pct'] < 30]
    if red_pairs:
        logger.debug("  🔴 CONSISTENT BOTTLENECKS (mean ≥200ms, cv<30%s — reliably slow every run):", "%")
        for r in red_pairs[:8]:
            nd  = r['node'].split('/')[-1]
            inp = r['input'].split('/')[-1]
            out = r['output'].split('/')[-1]
            logger.debug("     %s  %s → %s   %.0fms ± %.0fms  (worst p90: %.0fms, %d/%d runs)",
                        nd, inp, out, r['mean_ms'], r['stdev_runs'],
                        r['worst_p90_ms'], r['runs_seen'], r['total_runs'])
        logger.debug("")

    unstable = [r for r in results if r['cv_pct'] >= 50 and r['mean_ms'] >= 50]
    if unstable:
        logger.debug("  ✗ RTF-SENSITIVE PAIRS (cv≥50%s — highly variable, likely sim-speed limited):", "%")
        for r in unstable[:5]:
            nd  = r['node'].split('/')[-1]
            inp = r['input'].split('/')[-1]
            out = r['output'].split('/')[-1]
            logger.debug("     %s  %s → %s   range [%.0f–%.0f]ms  cv=%.0f%%",
                        nd, inp, out, r['min_mean_ms'], r['max_mean_ms'], r['cv_pct'])
        logger.debug("")


# ──────────────────────────────────────────────────────────────────────────────
#  CSV export
# ──────────────────────────────────────────────────────────────────────────────

_CSV_FIELDS = [
    'node', 'input', 'output', 'category',
    'runs_seen', 'total_runs',
    'mean_fps', 'fps_stdev',
    'mean_ms', 'stdev_runs', 'cv_pct',
    'min_mean_ms', 'max_mean_ms',
    'mean_p90_ms', 'worst_p90_ms', 'best_p90_ms',
    'mean_p50_ms', 'mean_stdev_ms', 'mean_n',
]


def print_aggregate_summary(results: List[dict], bench_dir: Path, total_runs: int) -> None:
    """Print a compact per-component aggregate summary (throughput + latency)."""
    if not results:
        return

    # One row per (node, output): pick the dominant input (highest mean trigger count)
    # We collapse the input dimension by choosing the pair with the lowest worst_p90.
    by_node_out: Dict[tuple, dict] = {}
    for r in results:
        k = (r['node'], r['output'])
        if k not in by_node_out or r['worst_p90_ms'] < by_node_out[k]['worst_p90_ms']:
            by_node_out[k] = r

    ranked = sorted(
        by_node_out.values(),
        key=lambda r: (
            PIPELINE_ORDER.index(r['category']) if r['category'] in PIPELINE_ORDER
            else len(PIPELINE_ORDER),
            r['mean_ms'],
        ),
    )

    W = 108
    logger.debug("\n" + '━' * W)
    logger.debug("  Aggregate Summary  |  %s  |  %s runs", bench_dir.name, total_runs)
    logger.debug('━' * W)
    logger.debug("  %-28s %-26s %12s  %14s  %10s",
                'Component', 'Output', 'Throughput', 'Mean Latency', 'Worst p90')
    logger.debug('━' * W)
    for r in ranked:
        nd    = r['node'].split('/')[-1][:26]
        out   = r['output'][-25:] if len(r['output']) > 25 else r['output']
        fps   = r.get('mean_fps')
        fps_s = f'{fps:.1f} Hz' if fps is not None else '—'
        h     = _health(r['mean_ms'])
        logger.debug("  %s %-26s %-26s %12s  %12.1f ms  %8.1f ms",
                    h, nd, out, fps_s, r['mean_ms'], r['worst_p90_ms'])
    logger.debug('━' * W)


def write_csv(results: List[dict], path: Path) -> None:
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=_CSV_FIELDS, extrasaction='ignore')
        w.writeheader()
        w.writerows(results)
    logger.info("  CSV written → %s", path)


# ──────────────────────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Cross-run KPI aggregation for wandering benchmark sessions.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        'bench_dir',
        help='Benchmark directory containing per-run subdirs with kpi.json files.',
    )
    parser.add_argument(
        '--min-runs',
        type=int,
        default=0,
        help='Minimum number of runs a pair must appear in to be reported '
             '(default: half of total runs, min 3).',
    )
    parser.add_argument(
        '--node', '-n',
        default=None,
        help='Filter output to a specific node name substring.',
    )
    parser.add_argument(
        '--csv-out',
        default=None,
        metavar='FILE',
        help='Write aggregated results to a CSV file.',
    )
    parser.add_argument(
        '--json-out',
        default=None,
        metavar='FILE',
        help='Write aggregated results to a JSON file.',
    )
    parser.add_argument(
        '--log-level',
        default=None,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging verbosity. Defaults to the LOG_LEVEL env var (or .env file), '
             'falling back to INFO.',
    )
    args = parser.parse_args()

    configure_logging(args.log_level)

    bench_dir = Path(args.bench_dir).resolve()
    if not bench_dir.is_dir():
        logger.error("%s is not a directory", bench_dir)
        sys.exit(1)

    total_runs, per_pair = load_bench(bench_dir)
    logger.info("  Loaded %d run(s) from %s", total_runs, bench_dir.name)
    logger.info("  Found %d unique (node, input, output) pairs across all runs", len(per_pair))

    # Default min_runs: half of total runs, at least 3
    min_runs = args.min_runs if args.min_runs > 0 else max(3, total_runs // 2)
    logger.info("  Minimum runs threshold: %d", min_runs)

    results = aggregate(per_pair, total_runs, min_runs, node_filter=args.node)

    print_report(results, bench_dir, total_runs)
    print_aggregate_summary(results, bench_dir, total_runs)

    if args.csv_out:
        write_csv(results, Path(args.csv_out))

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w') as f:
            json.dump({'bench_dir': str(bench_dir), 'total_runs': total_runs,
                       'results': results}, f, indent=2)
        logger.info("  JSON written → %s", out_path)


if __name__ == '__main__':
    main()
