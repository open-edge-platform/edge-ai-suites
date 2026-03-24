#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
analyze_trigger_latency.py  —  Trigger-based node latency analysis  (v2)
=========================================================================
For each node in the ROS2 graph this script identifies the *trigger*: the
last input message received on any subscribed topic before each output
message was emitted.  It then computes the time delta from that trigger to
the output (processing latency) and reports which specific input consistently
drives each output.

Approach
--------
For every output message O at time t_out on topic T_pub, for every
input topic T_sub subscribed by the same node, find:

    trigger_ts = max(timestamps_T_sub where ts <= t_out)
    latency    = t_out - trigger_ts

The input topic that produces the *smallest* latency for a given output is
the most-likely trigger.  All (input, output) pairs with ≥5 samples are
reported.

Usage
-----
  # analyse most recent session, all nodes
  uv run python src/analyze_trigger_latency.py

  # specific session directory
  uv run python src/analyze_trigger_latency.py --session monitoring_sessions/20260316_123325

  # focus on one node
  uv run python src/analyze_trigger_latency.py --node /robot_state_publisher

  # save per-event CSV + optional plot
  uv run python src/analyze_trigger_latency.py --export-csv --plot

  # suppress internal/bookkeeping topics
  uv run python src/analyze_trigger_latency.py --no-filter
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import os
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ──────────────────────────────────────────────────────────────────────────────
#  Internal topic filter  (bookkeeping / action plumbing / ROS2 internals)
# ──────────────────────────────────────────────────────────────────────────────

INTERNAL_TOPIC_RE = re.compile(
    r'(rosout'
    r'|parameter_events'
    r'|describe_parameters'
    r'|get_parameters'
    r'|list_parameters'
    r'|set_parameters'
    r'|rcl_interfaces'
    r'|/bond'
    r'|/_action'
    r'|/transition_event'
    r'|/tf_static'
    r'|/clock'
    r')'
)

MONITOR_NODE_RE = re.compile(
    r'(ros2_graph_monitor'
    r'|ros2_monitor'
    r'|rviz2?'
    r'|rqt'
    r'|transform_listener_impl'
    r')'
)


def _is_internal(topic: str) -> bool:
    return bool(INTERNAL_TOPIC_RE.search(topic))


# ──────────────────────────────────────────────────────────────────────────────
#  Data loading
# ──────────────────────────────────────────────────────────────────────────────

def load_topic_timestamps(csv_path: Path) -> Dict[str, List[float]]:
    """Return {topic_name: sorted list of wall-clock timestamps (seconds)}."""
    topic_times: Dict[str, List[float]] = defaultdict(list)
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            topic = row.get('topic_name', '').strip()
            try:
                ts = float(row['timestamp'])
            except (KeyError, ValueError):
                continue
            topic_times[topic].append(ts)
    for t in topic_times:
        topic_times[t].sort()
    return dict(topic_times)


def load_topic_timestamps_from_bag(bag_dir: Path) -> Dict[str, List[float]]:
    """Load topic timestamps from a rosbag2 directory (MCAP or SQLite3).

    Tries rosbag2_py first (handles both .mcap and .db3 natively).
    Falls back to direct sqlite3 reads when rosbag2_py is unavailable.
    Timestamps are converted from nanoseconds to seconds.
    """
    mcap_files = sorted(bag_dir.glob('*.mcap'))
    db3_files  = sorted(bag_dir.glob('*.db3'))

    if not mcap_files and not db3_files:
        raise FileNotFoundError(f'No .mcap or .db3 file found in {bag_dir}')

    # ── Preferred: rosbag2_py (works for both formats) ────────────────────────
    try:
        import rosbag2_py
        storage_id = 'mcap' if mcap_files else 'sqlite3'
        reader = rosbag2_py.SequentialReader()
        storage_opts   = rosbag2_py.StorageOptions(uri=str(bag_dir), storage_id=storage_id)
        converter_opts = rosbag2_py.ConverterOptions('', '')
        reader.open(storage_opts, converter_opts)
        topic_times: Dict[str, List[float]] = defaultdict(list)
        while reader.has_next():
            topic_name, _data, ts_ns = reader.read_next()
            topic_times[topic_name].append(ts_ns / 1e9)
        for t in topic_times:
            topic_times[t].sort()
        return dict(topic_times)
    except ImportError:
        pass

    # ── Fallback: direct SQLite3 for .db3 bags ────────────────────────────────
    if not db3_files:
        raise ImportError(
            'rosbag2_py is required to read .mcap bags.\n'
            '  source /opt/ros/jazzy/setup.bash  # makes rosbag2_py available'
        )
    import sqlite3
    topic_times = defaultdict(list)
    conn = sqlite3.connect(str(db3_files[0]))
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT t.name, m.timestamp
            FROM messages m
            JOIN topics t ON m.topic_id = t.id
        """)
        for name, ts_ns in cur.fetchall():
            topic_times[name].append(ts_ns / 1e9)
    finally:
        conn.close()
    for t in topic_times:
        topic_times[t].sort()
    return dict(topic_times)


def load_topology(topo_path: Path) -> Tuple[dict, dict]:
    """Return (nodes dict, topics dict) from graph_topology.json."""
    with open(topo_path) as f:
        topo = json.load(f)
    return topo.get('nodes', {}), topo.get('topics', {})


# ──────────────────────────────────────────────────────────────────────────────
#  Core analysis
# ──────────────────────────────────────────────────────────────────────────────

def find_trigger(out_ts: float, in_times: List[float]) -> Optional[float]:
    """
    Return the most-recent input timestamp that is <= out_ts, or None.
    Binary search via bisect for O(log n).
    """
    idx = bisect.bisect_right(in_times, out_ts) - 1
    return in_times[idx] if idx >= 0 else None


def analyze_node(
    node_name: str,
    pub_topics: List[str],
    sub_topics: List[str],
    topic_times: Dict[str, List[float]],
    filter_internal: bool = True,
    max_latency_ms: float = 10_000.0,
) -> List[dict]:
    """
    Compute trigger-based latency for every (input_topic, output_topic) pair
    for this node.

    Returns a list of result dicts, one per (in_topic, out_topic) pair that
    has at least 5 valid samples.
    """
    # Deduplicate while preserving order (topology JSON sometimes lists duplicates)
    pub_topics = list(dict.fromkeys(pub_topics))
    sub_topics = list(dict.fromkeys(sub_topics))

    if filter_internal:
        pub_topics = [t for t in pub_topics if not _is_internal(t)]
        sub_topics = [t for t in sub_topics if not _is_internal(t)]

    out_topics_with_data = [t for t in pub_topics if t in topic_times and len(topic_times[t]) > 1]
    in_topics_with_data  = [t for t in sub_topics  if t in topic_times and len(topic_times[t]) > 1]

    if not out_topics_with_data or not in_topics_with_data:
        return []

    results = []
    for out_t in out_topics_with_data:
        out_times = topic_times[out_t]

        # Per output message: record which input triggered it (smallest latency)
        # and the latency for every input topic.
        events: List[dict] = []  # one per output message
        for ot in out_times:
            trigger_candidates = {}
            for in_t in in_topics_with_data:
                trig_ts = find_trigger(ot, topic_times[in_t])
                if trig_ts is not None:
                    lat_ms = (ot - trig_ts) * 1000
                    if 0.0 < lat_ms <= max_latency_ms:
                        trigger_candidates[in_t] = (trig_ts, lat_ms)

            if not trigger_candidates:
                continue

            # The most-likely trigger = smallest non-zero latency
            best_in = min(trigger_candidates, key=lambda k: trigger_candidates[k][1])
            events.append({
                'out_ts':      ot,
                'best_input':  best_in,
                'trigger_ts':  trigger_candidates[best_in][0],
                'latency_ms':  trigger_candidates[best_in][1],
                'all_inputs':  trigger_candidates,   # {topic: (ts, lat_ms)}
            })

        if not events:
            continue

        # Per (in_t, out_t) pair statistics
        for in_t in in_topics_with_data:
            lats = [e['all_inputs'][in_t][1]
                    for e in events if in_t in e['all_inputs']]
            if len(lats) < 5:
                continue
            s = sorted(lats)
            n = len(s)
            pair_result = {
                'node':       node_name,
                'input':      in_t,
                'output':     out_t,
                'n':          n,
                'mean_ms':    statistics.mean(lats),
                'stdev_ms':   statistics.stdev(lats) if n > 1 else 0.0,
                'min_ms':     s[0],
                'p50_ms':     s[n // 2],
                'p90_ms':     s[int(n * 0.9)],
                'p99_ms':     s[min(int(n * 0.99), n - 1)],
                'max_ms':     s[-1],
                # count of outputs where this input was the best/closest trigger
                'trigger_count': sum(
                    1 for e in events if e['best_input'] == in_t
                ),
                'events':     events,   # full event list for CSV export / plot
            }
            results.append(pair_result)

    return results


# ──────────────────────────────────────────────────────────────────────────────
#  Console reporting
# ──────────────────────────────────────────────────────────────────────────────

def _bar(value: float, max_val: float = 200.0, width: int = 20) -> str:
    filled = int(round(width * min(value, max_val) / max_val))
    return '█' * filled + '░' * (width - filled)


def _health(mean_ms: float) -> str:
    if mean_ms < 10:   return '✅'
    if mean_ms < 50:   return '🟡'
    if mean_ms < 200:  return '🟠'
    return '🔴'


def print_results(all_results: List[dict], node_filter: Optional[str] = None) -> None:
    if not all_results:
        print('No trigger-based latency data found (need ≥5 samples per pair).')
        return

    # Group by node
    by_node: Dict[str, List[dict]] = defaultdict(list)
    for r in all_results:
        by_node[r['node']].append(r)

    for node_name, pairs in sorted(by_node.items()):
        if node_filter and node_filter not in node_name:
            continue

        # Sort pairs: primary key = output topic, secondary = mean latency asc
        pairs.sort(key=lambda x: (x['output'], x['mean_ms']))

        print()
        print('╔' + '═' * 110 + '╗')
        print(f'║  Node: {node_name:<102}║')
        print('╠' + '═' * 110 + '╣')

        # Group by output topic
        by_out: Dict[str, List[dict]] = defaultdict(list)
        for p in pairs:
            by_out[p['output']].append(p)

        for out_t, in_pairs in sorted(by_out.items()):
            print(f'║  OUTPUT ➜  {out_t:<98}║')
            print('║' + '─' * 110 + '║')
            # hdr: 2 + 55 + 1+5 + 1+7 + 1+7 + 1+7 + 1+7 + 1+7 + 1+6 = 110
            hdr = f"  {'Input Topic':<55} {'N':>5} {'mean':>7} {'p50':>7} {'p90':>7} {'p99':>7} {'stdev':>7} {'trigs':>6}"
            print(f'║{hdr:<110}║')
            print('║' + '─' * 110 + '║')
            for p in sorted(in_pairs, key=lambda x: x['trigger_count'], reverse=True):
                h = _health(p['mean_ms'])
                name_trunc = p['input'][-47:] if len(p['input']) > 47 else p['input']
                # body: 1+47+1+5 + 1+9×5 + 6 = 106 chars (no emoji — avoids wide-char padding skew)
                # Full row display: ║  (3) + emoji(2) + body(106) + ║(1) = 112 = box width ✓
                body = (f" {name_trunc:<47} "
                        f"{p['n']:>5} "
                        f"{p['mean_ms']:>6.1f}ms "
                        f"{p['p50_ms']:>6.1f}ms "
                        f"{p['p90_ms']:>6.1f}ms "
                        f"{p['p99_ms']:>6.1f}ms "
                        f"{p['stdev_ms']:>6.1f}ms "
                        f"{p['trigger_count']:>6}")
                print(f'║  {h}{body}║')
            print('║' + ' ' * 110 + '║')

        print('╚' + '═' * 110 + '╝')


# ──────────────────────────────────────────────────────────────────────────────
#  CSV export
# ──────────────────────────────────────────────────────────────────────────────

def export_events_csv(all_results: List[dict], out_path: Path) -> None:
    """
    Write a flat CSV with one row per output-message event, showing the
    winning (closest) trigger input and all competing input latencies.
    """
    # Collect all unique input topics to make dynamic columns
    all_in_topics: set = set()
    for r in all_results:
        for e in r.get('events', []):
            all_in_topics.update(e['all_inputs'].keys())
    in_cols = sorted(all_in_topics)

    fieldnames = ['node', 'output_topic', 'out_ts', 'best_input', 'trigger_ts',
                  'best_latency_ms'] + [f'lat_ms__{t.lstrip("/").replace("/", "__")}' for t in in_cols]

    written_keys: set = set()
    with open(out_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_results:
            key = (r['node'], r['output'])
            if key in written_keys:
                continue   # events are shared across per-input rows; write once per (node, out_t)
            written_keys.add(key)
            for e in r.get('events', []):
                row: dict = {
                    'node':             r['node'],
                    'output_topic':     r['output'],
                    'out_ts':           f"{e['out_ts']:.6f}",
                    'best_input':       e['best_input'],
                    'trigger_ts':       f"{e['trigger_ts']:.6f}",
                    'best_latency_ms':  f"{e['latency_ms']:.3f}",
                }
                for t in in_cols:
                    col = f'lat_ms__{t.lstrip("/").replace("/", "__")}'
                    if t in e['all_inputs']:
                        row[col] = f"{e['all_inputs'][t][1]:.3f}"
                    else:
                        row[col] = ''
                writer.writerow(row)

    print(f'\n  Events CSV written → {out_path}')


# ──────────────────────────────────────────────────────────────────────────────
#  Summary stats table
# ──────────────────────────────────────────────────────────────────────────────

def print_summary_table(all_results: List[dict]) -> None:
    """Print a compact ranked summary of worst p90 latencies across all nodes."""
    if not all_results:
        return

    # Deduplicate: keep only best (lowest mean) result per (node, out_topic, in_topic)
    seen: dict = {}
    for r in all_results:
        k = (r['node'], r['output'], r['input'])
        if k not in seen or r['mean_ms'] < seen[k]['mean_ms']:
            seen[k] = r

    ranked = sorted(seen.values(), key=lambda x: x['p90_ms'], reverse=True)

    print()
    print('━' * 110)
    print(f"  {'#':>3}  {'Node':<30} {'Input':<32} {'Output':<28} {'mean':>7} {'p90':>7} {'trigs':>6}")
    print('━' * 110)
    for i, r in enumerate(ranked[:30], 1):
        h = _health(r['mean_ms'])
        nd = r['node'].split('/')[-1][:28]
        inp = r['input'][-31:] if len(r['input']) > 31 else r['input']
        out = r['output'][-27:] if len(r['output']) > 27 else r['output']
        print(f"  {i:>3}  {h} {nd:<28} {inp:<32} {out:<28} "
              f"{r['mean_ms']:>6.1f}ms {r['p90_ms']:>6.1f}ms {r['trigger_count']:>6}")
    print('━' * 110)
    if len(ranked) > 30:
        print(f'  … {len(ranked) - 30} more pairs not shown (use --node to filter)')


# ──────────────────────────────────────────────────────────────────────────────
#  Optional plot
# ──────────────────────────────────────────────────────────────────────────────

def plot_trigger_timeline(
    all_results: List[dict],
    node_filter: Optional[str],
    session_dir: Path,
    show: bool = True,
) -> None:
    """
    For each selected node, draw a gantt-style timeline:
      - Each output topic = one swimlane
      - For each output event, a horizontal bar from trigger_ts to out_ts
        coloured by which input topic triggered it.
    """
    try:
        import matplotlib
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import numpy as np
    except ImportError:
        print('  matplotlib not available – skipping plot')
        return

    # Group by node
    by_node: Dict[str, List[dict]] = defaultdict(list)
    for r in all_results:
        if node_filter and node_filter not in r['node']:
            continue
        by_node[r['node']].append(r)

    if not by_node:
        print('  No matching nodes for plot.')
        return

    for node_name, pairs in sorted(by_node.items()):
        # Collect unique output topics and events
        by_out: Dict[str, List[dict]] = defaultdict(list)
        for p in pairs:
            for e in p.get('events', []):
                by_out[p['output']].append(e)

        out_topics = sorted(by_out.keys())
        if not out_topics:
            continue

        # Assign colours to input topics
        all_inputs_used: List[str] = sorted({
            e['best_input'] for events in by_out.values() for e in events
        })
        cmap = plt.cm.get_cmap('tab10', max(len(all_inputs_used), 1))
        in_color = {t: cmap(i) for i, t in enumerate(all_inputs_used)}

        fig, ax = plt.subplots(figsize=(16, max(4, len(out_topics) * 1.4)))
        fig.patch.set_facecolor('#fafafa')
        ax.set_facecolor('#fafafa')

        y_ticks = []
        y_labels = []

        for i, out_t in enumerate(out_topics):
            events = sorted(by_out[out_t], key=lambda e: e['out_ts'])
            y = i

            # Find global time reference (first event)
            t0 = events[0]['trigger_ts'] if events else 0

            for e in events:
                t_start = e['trigger_ts'] - t0
                t_end   = e['out_ts']     - t0
                width   = max(t_end - t_start, 0.001)
                color   = in_color.get(e['best_input'], '#cccccc')
                ax.barh(y, width, left=t_start, height=0.7,
                        color=color, alpha=0.75, edgecolor='none')

            y_ticks.append(y)
            short = out_t.split('/')[-1][:30]
            y_labels.append(short)

        ax.set_yticks(y_ticks)
        ax.set_yticklabels(y_labels, fontsize=8)
        ax.set_xlabel('Time from first trigger (s)', fontsize=9)
        ax.set_title(
            f'Trigger → Output timeline\n{node_name}',
            fontsize=10, fontweight='bold'
        )

        # Legend
        patches = [mpatches.Patch(color=in_color[t], label=t) for t in all_inputs_used]
        ax.legend(handles=patches, loc='upper right', fontsize=7,
                  title='Trigger input', title_fontsize=7)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()

        node_slug = node_name.lstrip('/').replace('/', '__')
        out_png = session_dir / 'visualizations' / f'trigger_timeline_{node_slug}.png'
        out_png.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(out_png, dpi=150, bbox_inches='tight')
        print(f'  Plot saved → {out_png}')
        if show:
            plt.show()
        plt.close(fig)


# ──────────────────────────────────────────────────────────────────────────────
#  Session discovery
# ──────────────────────────────────────────────────────────────────────────────

def find_latest_session(sessions_root: Path) -> Optional[Path]:
    """Return the most-recently-modified session directory that has both expected files."""
    candidates = [
        d for d in sessions_root.iterdir()
        if d.is_dir()
        and (d / 'graph_timing.csv').exists()
        and (d / 'graph_topology.json').exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda d: d.stat().st_mtime)


# ──────────────────────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Trigger-based node latency analysis (v2)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--bag', '-b',
        default=None,
        help=(
            'Path to a rosbag2 directory (or .mcap/.db3 file) containing recorded topics. '
            'When set, bag timestamps are used instead of graph_timing.csv. '
            'Requires graph_topology.json in the same directory (or use --topology).'
        ),
    )
    parser.add_argument(
        '--topology',
        default=None,
        help=(
            'Path to graph_topology.json to use with --bag. '
            'Defaults to graph_topology.json inside the bag directory. '
            'Use this when the topology was captured in a separate --analyze session.'
        ),
    )
    parser.add_argument(
        '--session', '-s',
        default=None,
        help='Path to monitoring session directory. Defaults to most recent session.',
    )
    parser.add_argument(
        '--sessions-dir',
        default='monitoring_sessions',
        help='Root directory containing session sub-dirs (default: monitoring_sessions).',
    )
    parser.add_argument(
        '--node', '-n',
        default=None,
        help='Filter output to a specific node name substring.',
    )
    parser.add_argument(
        '--max-latency-ms',
        type=float,
        default=10_000.0,
        help='Discard input→output pairs with latency above this threshold (default: 10000 ms).',
    )
    parser.add_argument(
        '--min-samples',
        type=int,
        default=5,
        help='Minimum number of trigger events required to report a pair (default: 5).',
    )
    parser.add_argument(
        '--no-filter',
        action='store_true',
        help='Include internal / bookkeeping topics (rosout, bond, clock, etc.).',
    )
    parser.add_argument(
        '--export-csv',
        action='store_true',
        help='Export per-event trigger data to trigger_events.csv in the session dir.',
    )
    parser.add_argument(
        '--plot',
        action='store_true',
        help='Generate trigger-timeline plots per node (saved to visualizations/).',
    )
    parser.add_argument(
        '--no-show',
        action='store_true',
        help='Do not open interactive plot windows (save only).',
    )
    parser.add_argument(
        '--summary-only',
        action='store_true',
        help='Print only the ranked summary table, skip per-node details.',
    )
    parser.add_argument(
        '--json-out',
        default=None,
        metavar='FILE',
        help='Save per-pair stats as JSON (for benchmark aggregation with aggregate_kpi.py).',
    )
    args = parser.parse_args()

    # ── Resolve data source ──────────────────────────────────────────────────
    ws_root = Path(__file__).parent.parent
    sessions_root = Path(args.sessions_dir) if Path(args.sessions_dir).is_absolute() \
        else ws_root / args.sessions_dir

    if args.bag:
        # ── Bag mode: rosbag2 timestamps + graph_topology.json in bag dir ────
        bag_input = Path(args.bag).resolve()
        # Accept both the bag directory AND a direct path to a .mcap/.db3 file
        bag_dir = bag_input.parent if bag_input.is_file() else bag_input
        session_dir = bag_dir   # exports / plots land in the bag dir

        bag_files = sorted(bag_dir.glob('*.mcap')) + sorted(bag_dir.glob('*.db3'))
        if not bag_files:
            print(f'ERROR: No .mcap or .db3 file found in {bag_dir}', file=sys.stderr)
            sys.exit(1)

        if args.topology:
            topo_path = Path(args.topology).resolve()
        else:
            topo_path = bag_dir / 'graph_topology.json'

        if not topo_path.exists():
            # Auto-discover the most recent topology from a sibling *_analysis dir
            candidates = sorted(
                bag_dir.parent.glob('*_analysis/graph_topology.json'),
                key=lambda p: p.parent.name, reverse=True,
            )
            if candidates:
                topo_path = candidates[0]
                print(f'\n  ℹ  No topology in bag dir — using nearest session:')
                print(f'     {topo_path}')
                print(f'     (pass --topology <path> to override)')
            else:
                print(f'ERROR: graph_topology.json not found.', file=sys.stderr)
                print(f'  Looked in: {bag_dir}', file=sys.stderr)
                print('  Fix: run a --analyze session first, or pass --topology <path>',
                      file=sys.stderr)
                sys.exit(1)

        bag_file = bag_files[0]
        fmt = 'MCAP' if bag_file.suffix == '.mcap' else 'DB3'
        print(f'\n  Bag dir  : {bag_dir}')
        print(f'  {fmt:<8} : {bag_file.name}')
        print(f'  Topology : {topo_path.name}')
        if args.node:
            print(f'  Node filter: {args.node}')

        print('\n  Loading topic timestamps from bag…', end='', flush=True)
        topic_times = load_topic_timestamps_from_bag(bag_dir)
        print(f' {len(topic_times)} topics loaded.')

    else:
        # ── Session mode: graph_timing.csv + graph_topology.json ─────────────
        if args.session:
            session_dir = Path(args.session) if Path(args.session).is_absolute() \
                else ws_root / args.session
        else:
            session_dir = find_latest_session(sessions_root)
            if session_dir is None:
                print(f'ERROR: No valid session found under {sessions_root}', file=sys.stderr)
                sys.exit(1)

        csv_path  = session_dir / 'graph_timing.csv'
        topo_path = session_dir / 'graph_topology.json'

        for p in (csv_path, topo_path):
            if not p.exists():
                print(f'ERROR: Required file not found: {p}', file=sys.stderr)
                sys.exit(1)

        print(f'\n  Session  : {session_dir}')
        print(f'  CSV      : {csv_path.name}')
        print(f'  Topology : {topo_path.name}')
        if args.node:
            print(f'  Node filter: {args.node}')

        print('\n  Loading topic timestamps…', end='', flush=True)
        topic_times = load_topic_timestamps(csv_path)
        print(f' {len(topic_times)} topics loaded.')

    nodes, topics = load_topology(topo_path)
    filter_internal = not args.no_filter

    # ── Analyse each node ────────────────────────────────────────────────────
    all_results: List[dict] = []
    print('  Analysing nodes…', end='', flush=True)
    for node_name, info in nodes.items():
        if MONITOR_NODE_RE.search(node_name):
            continue
        if args.node and args.node not in node_name:
            continue
        pubs = info.get('publishes', [])
        subs = info.get('subscribes', [])
        node_results = analyze_node(
            node_name, pubs, subs, topic_times,
            filter_internal=filter_internal,
            max_latency_ms=args.max_latency_ms,
        )
        # Apply min-samples filter
        node_results = [r for r in node_results if r['n'] >= args.min_samples]
        all_results.extend(node_results)

    print(f' {len(all_results)} (input→output) pairs found.')

    # ── Report ───────────────────────────────────────────────────────────────
    print_summary_table(all_results)

    if not args.summary_only:
        print_results(all_results, node_filter=args.node)

    # ── Export CSV ───────────────────────────────────────────────────────────
    if args.export_csv:
        export_path = session_dir / 'trigger_events.csv'
        export_events_csv(all_results, export_path)

    # ── JSON output (for benchmark aggregation) ──────────────────────────────
    if args.json_out:
        _SCALAR_KEYS = ('node','input','output','n','mean_ms','stdev_ms',
                        'min_ms','p50_ms','p90_ms','p99_ms','max_ms','trigger_count')
        # Deduplicate: keep best (lowest mean) per (node, input, output)
        seen: dict = {}
        for r in all_results:
            k = (r['node'], r['input'], r['output'])
            if k not in seen or r['mean_ms'] < seen[k]['mean_ms']:
                seen[k] = r
        payload = {
            'session': str(session_dir),
            'pairs': [{k: r[k] for k in _SCALAR_KEYS} for r in seen.values()],
        }
        json_path = Path(args.json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, 'w') as _jf:
            json.dump(payload, _jf, indent=2)
        print(f'  KPI JSON written → {json_path}')

    # ── Plot ─────────────────────────────────────────────────────────────────
    if args.plot:
        print('\n  Generating plots…')
        plot_trigger_timeline(
            all_results,
            node_filter=args.node,
            session_dir=session_dir,
            show=not args.no_show,
        )


if __name__ == '__main__':
    main()
