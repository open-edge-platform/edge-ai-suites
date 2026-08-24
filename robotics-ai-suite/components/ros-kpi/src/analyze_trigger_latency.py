#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
analyze_trigger_latency.py — Trigger-based node latency analysis (v2).

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

  # write flat KPI CSV (one row per input→output pair)
  uv run python src/analyze_trigger_latency.py --csv-out kpi_pairs.csv

  # suppress internal/bookkeeping topics
  uv run python src/analyze_trigger_latency.py --no-filter
"""

from __future__ import annotations

import argparse
import bisect
import csv
import datetime
import json
import os
import platform
import re
import socket
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from log_config import get_logger

logger = get_logger(__name__)

# Optional wandering-specific goal-calc latency extraction (sibling module)
try:
    from wandering_metrics import extract_goal_calc_latency as _extract_goal_calc_latency
    from wandering_metrics import extract_goal_response_latency as _extract_goal_response_latency
except ImportError:  # pragma: no cover
    _extract_goal_calc_latency = None  # type: ignore[assignment]
    _extract_goal_response_latency = None  # type: ignore[assignment]

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
        # Avoid MCAP warning "attempted to read in receive timestamp order with
        # no message index". Recorded timestamps are correct for latency analysis
        # and do not require a per-message index in the bag.
        if hasattr(rosbag2_py, 'ReadOrder') and hasattr(rosbag2_py, 'ReadOrderSortBy'):
            _order = rosbag2_py.ReadOrder()
            _order.sort_by = rosbag2_py.ReadOrderSortBy.PublishedTimestamp
            reader.set_read_order(_order)
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


def _compute_topic_fps(topic_times: Dict[str, List[float]]) -> Dict[str, float]:
    """Return {topic: measured_fps} derived from observed message timestamps."""
    fps_map: Dict[str, float] = {}
    for topic, times in topic_times.items():
        if len(times) >= 2:
            duration = times[-1] - times[0]
            if duration > 0:
                fps_map[topic] = (len(times) - 1) / duration
    return fps_map


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
    Compute trigger-based latency for every (input_topic, output_topic) pair.

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
            best_in = min(trigger_candidates, key=lambda k, tc=trigger_candidates: tc[k][1])
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
            # Throughput: measured fps of the output topic
            _out_ts_list = topic_times.get(out_t, [])
            if len(_out_ts_list) >= 2:
                _dur = _out_ts_list[-1] - _out_ts_list[0]
                pair_result['fps'] = (len(_out_ts_list) - 1) / _dur if _dur > 0 else None
            else:
                pair_result['fps'] = None
            pair_result['jitter_mean_ms'] = pair_result['stdev_ms']
            pair_result['jitter_max_ms']  = pair_result['max_ms'] - pair_result['mean_ms']
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
    """Print detailed per-node trigger latency results."""
    if not all_results:
        logger.warning('No trigger-based latency data found (need ≥5 samples per pair).')
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

        logger.debug('\n╔' + '═' * 110 + '╗')
        logger.debug(f'║  Node: {node_name:<102}║')
        logger.debug('╠' + '═' * 110 + '╣')

        # Group by output topic
        by_out: Dict[str, List[dict]] = defaultdict(list)
        for p in pairs:
            by_out[p['output']].append(p)

        for out_t, in_pairs in sorted(by_out.items()):
            logger.debug(f'║  OUTPUT ➜  {out_t:<98}║')
            logger.debug('║' + '─' * 110 + '║')
            # hdr: 2 + 55 + 1+5 + 1+7 + 1+7 + 1+7 + 1+7 + 1+7 + 1+6 = 110
            hdr = f"  {'Input Topic':<55} {'N':>5} {'mean':>7} {'p50':>7} {'p90':>7} {'p99':>7} {'stdev':>7} {'trigs':>6}"
            logger.debug(f'║{hdr:<110}║')
            logger.debug('║' + '─' * 110 + '║')
            for p in sorted(in_pairs, key=lambda x: x['trigger_count'], reverse=True):
                h = _health(p['mean_ms'])
                name_trunc = p['input'][-47:] if len(p['input']) > 47 else p['input']
                # body: 1+47+1+5 + 1+9×5 + 6 = 106 chars (no emoji — avoids wide-char padding skew)
                # Full row display: ║  (3) + emoji(2) + body(106) + ║(1) = 112 = box width ✓
                body = (f' {name_trunc:<47} '
                        f"{p['n']:>5} "
                        f"{p['mean_ms']:>6.1f}ms "
                        f"{p['p50_ms']:>6.1f}ms "
                        f"{p['p90_ms']:>6.1f}ms "
                        f"{p['p99_ms']:>6.1f}ms "
                        f"{p['stdev_ms']:>6.1f}ms "
                        f"{p['trigger_count']:>6}")
                logger.debug(f'║  {h}{body}║')
            logger.debug('║' + ' ' * 110 + '║')

        logger.debug('╚' + '═' * 110 + '╝')


# ──────────────────────────────────────────────────────────────────────────────
#  CSV export
# ──────────────────────────────────────────────────────────────────────────────

def export_events_csv(all_results: List[dict], out_path: Path) -> None:
    """
    Write a flat CSV with one row per output-message event.

    Shows the winning (closest) trigger input and all competing input latencies.
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

    logger.info(f'\n  Events CSV written → {out_path}')


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

    logger.debug('\n' + '━' * 110)
    logger.debug(f"  {'#':>3}  {'Node':<30} {'Input':<32} {'Output':<28} {'mean':>7} {'p90':>7} {'trigs':>6}")
    logger.debug('━' * 110)
    for i, r in enumerate(ranked[:30], 1):
        h = _health(r['mean_ms'])
        nd = r['node'].split('/')[-1][:28]
        inp = r['input'][-31:] if len(r['input']) > 31 else r['input']
        out = r['output'][-27:] if len(r['output']) > 27 else r['output']
        logger.debug(f'  {i:>3}  {h} {nd:<28} {inp:<32} {out:<28} '
              f"{r['mean_ms']:>6.1f}ms {r['p90_ms']:>6.1f}ms {r['trigger_count']:>6}")
    logger.debug('━' * 110)
    if len(ranked) > 30:
        logger.debug(f'  … {len(ranked) - 30} more pairs not shown (use --node to filter)')


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
    For each selected node, draw a gantt-style timeline.

    - Each output topic = one swimlane.
    - For each output event, a horizontal bar from trigger_ts to out_ts
      coloured by which input topic triggered it.
    """
    try:
        import matplotlib
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        logger.info('  matplotlib not available – skipping plot')
        return

    # Group by node
    by_node: Dict[str, List[dict]] = defaultdict(list)
    for r in all_results:
        if node_filter and node_filter not in r['node']:
            continue
        by_node[r['node']].append(r)

    if not by_node:
        logger.info('  No matching nodes for plot.')
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
        # matplotlib.cm.get_cmap(name, lut) was removed in matplotlib 3.11;
        # matplotlib.colormaps[name].resampled(lut) is the modern equivalent.
        cmap = matplotlib.colormaps['tab10'].resampled(max(len(all_inputs_used), 1))
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
        logger.info(f'  Plot saved → {out_png}')
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
#  Hardware / provenance helpers
# ──────────────────────────────────────────────────────────────────────────────

def _framework_version() -> str:
    """Read the framework version from pyproject.toml, fall back to 'unknown'."""
    try:
        import importlib.metadata
        return importlib.metadata.version('ros2-kpi')
    except Exception:
        pass
    try:
        _pyproject = Path(__file__).resolve().parent.parent / 'pyproject.toml'
        text = _pyproject.read_text()
        m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
        return m.group(1) if m else 'unknown'
    except Exception:
        return 'unknown'


def _cpu_model() -> str:
    """Return the CPU model string from /proc/cpuinfo, or platform fallback."""
    try:
        with open('/proc/cpuinfo') as f:
            for line in f:
                if line.startswith('model name'):
                    return line.split(':', 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or 'unknown'


def _gpu_model() -> Optional[str]:
    """Detect GPU model via lspci (best-effort, returns None if unavailable)."""
    try:
        import subprocess as _sp
        out = _sp.run(
            ['lspci', '-mm'],
            capture_output=True, text=True, timeout=5,
        ).stdout
        for line in out.splitlines():
            low = line.lower()
            if 'vga' in low or '3d controller' in low or 'display' in low:
                # lspci -mm: fields are tab/quote separated; extract the device field
                parts = [p.strip().strip('"') for p in line.split('"') if p.strip().strip('"')]
                if len(parts) >= 3:
                    return parts[2]
                return line.strip()
    except Exception:
        pass
    return None


def _total_ram_gb() -> Optional[float]:
    """Return total system RAM in GiB via psutil, or None."""
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 2)
    except Exception:
        return None


def _hardware_info() -> dict:
    """Collect hardware provenance fields for the metadata block."""
    return {
        'cpu_model':   _cpu_model(),
        'cpu_cores':   os.cpu_count(),
        'gpu_model':   _gpu_model(),
        'total_ram_gb': _total_ram_gb(),
    }


def _compute_resource_cpu_stats(session_dir: Path):
    """
    Parse ``resource_usage.json`` (a single JSON document written by
    _psutil_probe.py via monitor_resources.py) and return
    ``(cpu_mean_pct, cpu_max_pct)`` as a percentage of total system capacity
    (0-100), or ``(None, None)`` if the file is absent, empty, or unreadable.

    Sums each sample's per-process cpu_pct across all processes (each
    already on a 100%=1-core scale), then scales by num_cpus to get 0-100
    system-wide.
    """
    log = session_dir / 'resource_usage.json'
    if not log.exists():
        return None, None

    try:
        document = json.loads(log.read_text(errors='replace'))
    except (OSError, json.JSONDecodeError):
        return None, None

    num_cpus = document.get('num_cpus') or 1  # safe fallback
    totals = [
        sum(p.get('cpu_pct', 0.0) for p in sample.get('processes', []))
        for sample in document.get('samples', [])
    ]
    if not totals:
        return None, None

    scale = num_cpus * 100.0
    cpu_mean = round(statistics.mean(totals) / scale * 100.0, 1)
    cpu_max = round(max(totals) / scale * 100.0, 1)
    return cpu_mean, cpu_max


def _load_resource_thermal(session_dir: Path) -> dict:
    """
    DEPRECATED: GPU/NPU thermal collection is not reliably supported across
    hardware (no hwmon sysfs node for many iGPUs; NPU temp via PMT telemetry
    was never implemented), so this data is no longer surfaced in kpi.json to
    avoid confusing consumers with always-null fields. Kept only for any
    external callers; returns an empty dict.
    """
    return {}


# Default cap on how many latency spikes are surfaced in kpi.json.
DEFAULT_MAX_LATENCY_SPIKES = 5


def _load_resource_samples(session_dir: Path):
    """
    Parse ``resource_usage.json`` once and return ``(epoch_ts, samples,
    node_map)`` sorted by time, or ``None`` if the file is absent, empty, or
    unreadable.

    epoch_ts is a list of epoch-second floats (each sample's ISO ``ts``
    converted via ``datetime.fromisoformat(...).timestamp()``), parallel to
    samples -- ready for a bisect-based nearest-timestamp lookup. node_map is
    ``{pid: node_name}`` from ``ros2_node_map`` (#58), empty if absent.
    """
    log = session_dir / 'resource_usage.json'
    if not log.exists():
        return None
    try:
        document = json.loads(log.read_text(errors='replace'))
    except (OSError, json.JSONDecodeError):
        return None

    epoch_ts, samples = [], []
    for sample in document.get('samples', []):
        try:
            ts = datetime.datetime.fromisoformat(sample['ts']).timestamp()
        except (KeyError, TypeError, ValueError):
            continue
        epoch_ts.append(ts)
        samples.append(sample)
    if not epoch_ts:
        return None

    order = sorted(range(len(epoch_ts)), key=epoch_ts.__getitem__)
    epoch_ts = [epoch_ts[i] for i in order]
    samples = [samples[i] for i in order]

    node_map = {int(pid): name for pid, name in (document.get('ros2_node_map') or {}).items()}
    return epoch_ts, samples, node_map


def _nearest_sample_index(epoch_ts: List[float], target: float) -> int:
    """Return the index into a sorted epoch_ts closest to target."""
    idx = bisect.bisect_left(epoch_ts, target)
    if idx == 0:
        return 0
    if idx == len(epoch_ts):
        return len(epoch_ts) - 1
    before, after = epoch_ts[idx - 1], epoch_ts[idx]
    return idx - 1 if (target - before) <= (after - target) else idx


def _find_latency_spikes(
    all_results: List[dict],
    session_dir: Path,
    max_spikes: int = DEFAULT_MAX_LATENCY_SPIKES,
) -> List[dict]:
    """
    Cross-reference latency outliers against resource_usage.json to surface
    "node X spiked CPU right before this latency outlier" root-cause hints,
    instead of two disconnected charts (#59).

    A spike is any event whose latency for its own (node, input, output)
    pair meets or exceeds that pair's own p99_ms (reusing the percentile
    already computed per pair rather than a second statistical pass). Each
    surfaced spike is joined to the nearest resource_usage.json sample by
    timestamp and annotated with its top-3 CPU consumers.

    Known limitation: out_ts is wall-clock/bag-recorded epoch seconds, while
    resource_usage.json's ts is always the resource probe's wall clock. If
    the session used --use-sim-time, out_ts may be simulated time and
    diverge from the probe's wall-clock samples, making the correlation
    unreliable (same category as the sim-time bug fixed in
    ros2_graph_monitor.py).

    Returns [] if resource_usage.json is absent/unreadable or no event meets
    its pair's p99 threshold. Sorted by latency_ms descending, capped to
    max_spikes to keep kpi.json bounded.
    """
    loaded = _load_resource_samples(session_dir)
    if loaded is None:
        return []
    epoch_ts, samples, node_map = loaded

    candidates = []
    for pair_result in all_results:
        threshold = pair_result.get('p99_ms')
        if threshold is None:
            continue
        in_t = pair_result['input']
        for event in pair_result.get('events', []):
            hit = event.get('all_inputs', {}).get(in_t)
            if hit is None:
                continue
            _trigger_ts, lat_ms = hit
            if lat_ms < threshold:
                continue
            candidates.append({
                'node':       pair_result['node'],
                'input':      in_t,
                'output':     pair_result['output'],
                'out_ts':     event['out_ts'],
                'latency_ms': round(lat_ms, 3),
            })

    if not candidates:
        return []

    candidates.sort(key=lambda c: c['latency_ms'], reverse=True)
    candidates = candidates[:max_spikes]

    spikes = []
    for c in candidates:
        idx = _nearest_sample_index(epoch_ts, c['out_ts'])
        sample_ts, sample = epoch_ts[idx], samples[idx]
        top_processes = sorted(
            sample.get('processes', []),
            key=lambda p: p.get('cpu_pct', 0.0), reverse=True,
        )[:3]
        spikes.append({
            **c,
            'resource_sample_ts': sample_ts,
            'time_delta_sec':     round(abs(sample_ts - c['out_ts']), 3),
            'top_consumers': [
                {
                    'pid':     p.get('pid'),
                    'node':    node_map.get(p.get('pid')),
                    'cpu_pct': p.get('cpu_pct', 0.0),
                }
                for p in top_processes
            ],
        })

    return spikes


# ──────────────────────────────────────────────────────────────────────────────
#  JSON schema validation
# ──────────────────────────────────────────────────────────────────────────────

def _schema_path() -> Path:
    """Return the path to the Level 1 KPI JSON schema bundled with the repo."""
    return Path(__file__).resolve().parent.parent / 'schemas' / 'kpi_level1_v1.json'


def validate_kpi_json(payload: dict) -> list[str]:
    """
    Validate *payload* against the Level 1 KPI JSON schema.

    Returns a list of human-readable error strings (empty means valid).
    Falls back gracefully when jsonschema is not installed.
    """
    schema_file = _schema_path()
    if not schema_file.exists():
        return [f'Schema file not found: {schema_file}']
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return ['jsonschema not installed — skipping validation (pip install jsonschema)']

    with open(schema_file) as _sf:
        schema = json.load(_sf)

    ValidatorCls = getattr(jsonschema, 'Draft202012Validator', None) or \
        getattr(jsonschema, 'Draft7Validator', None) or \
        jsonschema.Draft4Validator
    validator = ValidatorCls(schema)
    return [str(err.message) for err in sorted(validator.iter_errors(payload), key=str)]


_PIPELINE_ORDER_ATL = ['Sensor', 'Perception', 'Planning', 'Control', 'Other']


def _classify_node(node: str) -> str:
    """Return the pipeline stage for a node name."""
    n = node.split('/')[-1]
    if n in ('ros_gz_bridge', 'robot_state_publisher'):
        return 'Sensor'
    if n in ('rtabmap', 'local_costmap', 'global_costmap'):
        return 'Perception'
    if n in ('route_server', 'behavior_server', 'planner_server', 'bt_navigator'):
        return 'Planning'
    if n in ('controller_server', 'velocity_smoother', 'collision_monitor', 'docking_server'):
        return 'Control'
    return 'Other'


def build_performance_kpi(
    all_results: List[dict],
    session_dir: Path,
    topic_times: Dict[str, List[float]],  # noqa: ARG001 — kept for API symmetry
    max_latency_spikes: int = DEFAULT_MAX_LATENCY_SPIKES,
) -> dict:
    """
    Build a structured per-session KPI dict using standard benchmark metric keys.

    Top-level BasicPerformanceMetrics.* keys summarizes the dominant (highest
    trigger-count) pair in the session.  Per-node breakdowns are stored under
    'per_node'.  The full scalar pair list is kept under 'pairs' for downstream
    aggregation by aggregate_kpi.py.
    """
    _SCALAR_KEYS = (
        'node', 'input', 'output', 'n',
        'mean_ms', 'stdev_ms', 'min_ms', 'p50_ms', 'p90_ms', 'p99_ms', 'max_ms',
        'trigger_count', 'fps', 'jitter_mean_ms', 'jitter_max_ms',
    )

    # De-duplicate: best (lowest mean) per (node, input, output)
    seen: dict = {}
    for r in all_results:
        k = (r['node'], r['input'], r['output'])
        if k not in seen or r['mean_ms'] < seen[k]['mean_ms']:
            seen[k] = r
    deduped = list(seen.values())

    # System-level summary from the dominant (highest trigger_count) pair
    if deduped:
        dominant     = max(deduped, key=lambda r: r.get('trigger_count', 0))
        sys_fps      = dominant.get('fps')
        sys_lat      = dominant['mean_ms']
        sys_lat_min  = dominant['min_ms']
        sys_lat_max  = dominant['max_ms']
        sys_jit_mean = dominant.get('jitter_mean_ms', dominant['stdev_ms'])
        sys_jit_max  = dominant.get('jitter_max_ms', dominant['max_ms'] - dominant['mean_ms'])
        all_jitters  = [r.get('jitter_mean_ms', r['stdev_ms']) for r in deduped]
        sys_jit_min  = min(all_jitters)
        sys_jit_std  = statistics.stdev(all_jitters) if len(all_jitters) > 1 else 0.0
    else:
        sys_fps = sys_lat = sys_lat_min = sys_lat_max = None
        sys_jit_mean = sys_jit_max = sys_jit_min = sys_jit_std = None

    # Per-node summary
    by_node: Dict[str, List[dict]] = defaultdict(list)
    for r in deduped:
        by_node[r['node']].append(r)

    per_node: dict = {}
    for node_name, pairs in sorted(by_node.items()):
        primary = max(pairs, key=lambda r: r.get('trigger_count', 0))
        per_node[node_name] = {
            'throughput_hz':    primary.get('fps'),
            'mean_latency_ms':  primary['mean_ms'],
            'min_latency_ms':   primary['min_ms'],
            'max_latency_ms':   primary['max_ms'],
            'mean_jitter_ms':   primary.get('jitter_mean_ms', primary['stdev_ms']),
            'max_jitter_ms':    primary.get('jitter_max_ms',
                                            primary['max_ms'] - primary['mean_ms']),
            'num_samples':      primary['n'],
            'primary_input':    primary['input'],
            'primary_output':   primary['output'],
            'pipeline_stage':   _classify_node(node_name),
        }

    _cpu_mean, _cpu_max = _compute_resource_cpu_stats(session_dir)
    _latency_spikes = _find_latency_spikes(all_results, session_dir, max_latency_spikes)
    payload = {
        'schema_version':   'level1_v1',
        'throughput_hz':    sys_fps,
        'mean_latency_ms':  sys_lat,
        'min_latency_ms':   sys_lat_min,
        'max_latency_ms':   sys_lat_max,
        'max_jitter_ms':    sys_jit_max,
        'min_jitter_ms':    sys_jit_min,
        'mean_jitter_ms':   sys_jit_mean,
        'jitter_stdev_ms':  sys_jit_std,
        'cpu_mean_pct':     _cpu_mean,
        'cpu_max_pct':      _cpu_max,
        'latency_spikes':   _latency_spikes,
        'per_node': per_node,
        'pairs': [{k: r[k] for k in _SCALAR_KEYS if k in r} for r in deduped],
        'metadata': {
            'name':              session_dir.name,
            'datetime':          datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'hostname':          socket.gethostname(),
            'arch':              platform.machine(),
            'os':                f'{platform.system()} {platform.release()}',
            'data_path':         str(session_dir),
            'framework_version': _framework_version(),
            'ros_distro':        os.environ.get('ROS_DISTRO', 'unknown'),
            'hardware':          _hardware_info(),
        },
    }
    _log = session_dir / 'wandering_launch.log'
    if _log.exists():
        _log_text = _log.read_text(errors='replace')
        if _extract_goal_calc_latency is not None:
            _gcl = _extract_goal_calc_latency(_log_text)
            if _gcl:
                payload.setdefault('wandering', {})['goal_calc_latency_ms'] = _gcl
        _bag = session_dir / 'bag'
        if _extract_goal_response_latency is not None and _bag.exists():
            _grl = _extract_goal_response_latency(_log_text, _bag)
            if _grl:
                payload.setdefault('wandering', {})['goal_response_latency_ms'] = _grl
    return payload


def print_performance_summary(all_results: List[dict]) -> None:
    """Print a compact ranked performance summary table (throughput + latency per component)."""
    if not all_results:
        return

    # Best (highest trigger_count) pair per (node, output)
    by_node_out: Dict[tuple, dict] = {}
    for r in all_results:
        k = (r['node'], r['output'])
        if k not in by_node_out or r.get('trigger_count', 0) > by_node_out[k].get('trigger_count', 0):
            by_node_out[k] = r

    ranked = sorted(
        by_node_out.values(),
        key=lambda r: (
            _PIPELINE_ORDER_ATL.index(_classify_node(r['node']))
            if _classify_node(r['node']) in _PIPELINE_ORDER_ATL
            else len(_PIPELINE_ORDER_ATL),
            r['mean_ms'],
        ),
    )

    W = 104
    logger.info('\n' + '━' * W)
    logger.info('  Performance Summary')
    logger.info('━' * W)
    logger.info(f"  {'Component':<28} {'Input → Output':<44} {'Throughput':>12}  {'Latency':>9}  {'p90':>9}")
    logger.info('━' * W)
    for r in ranked:
        nd   = r['node'].split('/')[-1][:26]
        inp  = r['input'].split('/')[-1][:18]
        out  = r['output'].split('/')[-1][:18]
        io   = f'{inp} → {out}'
        fps  = r.get('fps')
        fps_s = f'{fps:.1f} Hz' if fps is not None else '—'
        h    = _health(r['mean_ms'])
        logger.info(f"  {h} {nd:<26} {io:<44} {fps_s:>12}  {r['mean_ms']:>7.1f} ms  {r['p90_ms']:>7.1f} ms")
    logger.info('━' * W)


# ──────────────────────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point for trigger-based node latency analysis."""
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
        '--max-latency-spikes',
        type=int,
        default=DEFAULT_MAX_LATENCY_SPIKES,
        help='Max number of latency outliers to cross-reference against resource_usage.json '
             'in the KPI output (default: 5). An outlier is an event at or above its own '
             'pair\'s p99 latency.',
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
        '--no-table',
        action='store_true',
        help='Suppress all table output (summary table + performance summary). '
             'KPI exports (--json-out, --csv-out) are unaffected.',
    )
    parser.add_argument(
        '--json-out',
        default=None,
        metavar='FILE',
        help='Save per-pair stats as JSON (for benchmark aggregation with aggregate_kpi.py).',
    )
    parser.add_argument(
        '--csv-out',
        default=None,
        metavar='FILE',
        help='Write per-pair KPI results as a flat CSV (one row per node/input/output pair). '
             'Columns: session, node, pipeline_stage, input, output, n, '
             'mean_ms, stdev_ms, min_ms, p50_ms, p90_ms, p99_ms, max_ms, '
             'trigger_count, fps, jitter_mean_ms, jitter_max_ms.',
    )
    parser.add_argument(
        '--xlsx-out',
        default=None,
        metavar='FILE',
        help='Write per-pair KPI results as an Excel workbook (.xlsx). '
             'Same columns as --csv-out. Requires openpyxl (pip install openpyxl).',
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
        # resource_usage.json and other session logs live in the parent of the
        # bag directory (e.g. session_dir/bag/ → session_dir/)
        session_dir = bag_dir.parent if (bag_dir.parent / 'resource_usage.json').exists() else bag_dir

        bag_files = sorted(bag_dir.glob('*.mcap')) + sorted(bag_dir.glob('*.db3'))
        if not bag_files:
            logger.error(f'No .mcap or .db3 file found in {bag_dir}')
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
                logger.info('\n  ℹ  No topology in bag dir — using nearest session:')
                logger.info(f'     {topo_path}')
                logger.info('     (pass --topology <path> to override)')
            else:
                logger.error('graph_topology.json not found.')
                logger.error(f'  Looked in: {bag_dir}')
                logger.error('  Fix: run a --analyze session first, or pass --topology <path>')
                sys.exit(1)

        bag_file = bag_files[0]
        fmt = 'MCAP' if bag_file.suffix == '.mcap' else 'DB3'
        logger.info(f'\n  Bag dir  : {bag_dir}')
        logger.info(f'  {fmt:<8} : {bag_file.name}')
        logger.info(f'  Topology : {topo_path.name}')
        if args.node:
            logger.info(f'  Node filter: {args.node}')

        print('\n  Loading topic timestamps from bag…', end='', flush=True)
        topic_times = load_topic_timestamps_from_bag(bag_dir)
        logger.info(f' {len(topic_times)} topics loaded.')

    else:
        # ── Session mode: graph_timing.csv + graph_topology.json ─────────────
        if args.session:
            session_dir = Path(args.session) if Path(args.session).is_absolute() \
                else ws_root / args.session
        else:
            session_dir = find_latest_session(sessions_root)
            if session_dir is None:
                logger.error(f'No valid session found under {sessions_root}')
                sys.exit(1)

        csv_path  = session_dir / 'graph_timing.csv'
        topo_path = session_dir / 'graph_topology.json'

        for p in (csv_path, topo_path):
            if not p.exists():
                logger.error(f'Required file not found: {p}')
                sys.exit(1)

        logger.info(f'\n  Session  : {session_dir}')
        logger.info(f'  CSV      : {csv_path.name}')
        logger.info(f'  Topology : {topo_path.name}')
        if args.node:
            logger.info(f'  Node filter: {args.node}')

        print('\n  Loading topic timestamps…', end='', flush=True)
        topic_times = load_topic_timestamps(csv_path)
        logger.info(f' {len(topic_times)} topics loaded.')

    nodes, _ = load_topology(topo_path)
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

    if not args.no_table:
        logger.info(f' {len(all_results)} (input→output) pairs found.')

    # ── Report ───────────────────────────────────────────────────────────────
    if not args.no_table:
        print_summary_table(all_results)

    if not args.summary_only and not args.no_table:
        print_results(all_results, node_filter=args.node)

    if not args.no_table:
        print_performance_summary(all_results)

    # ── Export CSV ───────────────────────────────────────────────────────────
    if args.export_csv:
        export_path = session_dir / 'trigger_events.csv'
        export_events_csv(all_results, export_path)

    # ── JSON output (for benchmark aggregation) ──────────────────────────────
    if args.json_out:
        payload = build_performance_kpi(
            all_results, session_dir, topic_times,
            max_latency_spikes=args.max_latency_spikes,
        )
        json_path = Path(args.json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, 'w') as _jf:
            json.dump(payload, _jf, indent=2)
        logger.info(f'  KPI JSON written → {json_path}')
        if not args.no_table and payload.get('latency_spikes'):
            logger.info(f"  ⚠  {len(payload['latency_spikes'])} latency spike(s) cross-referenced "
                        f"against resource usage — see 'latency_spikes' in the KPI JSON")
        errors = validate_kpi_json(payload)
        if errors:
            logger.warning(f'  KPI JSON failed schema validation ({len(errors)} error(s)):')
            for err in errors:
                logger.info(f'    • {err}')
        else:
            logger.info('  KPI JSON schema validation passed ✓')
        _gcl = (payload.get('wandering') or {}).get('goal_calc_latency_ms')
        if _gcl:
            logger.info(f'  Goal-calc latency    mean={_gcl["mean_ms"]:.1f}ms  '
                  f'p90={_gcl["p90_ms"]:.1f}ms  max={_gcl["max_ms"]:.1f}ms  '
                  f'(n={_gcl["n"]} transitions)')

    # ── Tabular KPI export (CSV / Excel) ─────────────────────────────────────
    if args.csv_out or args.xlsx_out:
        _L1_FIELDS = [
            'session', 'node', 'pipeline_stage', 'input', 'output',
            'n', 'mean_ms', 'stdev_ms', 'min_ms', 'p50_ms', 'p90_ms', 'p99_ms', 'max_ms',
            'trigger_count', 'fps', 'jitter_mean_ms', 'jitter_max_ms',
        ]
        _l1_rows = [
            {
                'session':        session_dir.name,
                'node':           r.get('node', ''),
                'pipeline_stage': r.get('pipeline_stage', ''),
                'input':          r.get('input', ''),
                'output':         r.get('output', ''),
                'n':              r.get('n', ''),
                'mean_ms':        r.get('mean_ms', ''),
                'stdev_ms':       r.get('stdev_ms', ''),
                'min_ms':         r.get('min_ms', ''),
                'p50_ms':         r.get('p50_ms', ''),
                'p90_ms':         r.get('p90_ms', ''),
                'p99_ms':         r.get('p99_ms', ''),
                'max_ms':         r.get('max_ms', ''),
                'trigger_count':  r.get('trigger_count', ''),
                'fps':            r.get('fps', ''),
                'jitter_mean_ms': r.get('jitter_mean_ms', ''),
                'jitter_max_ms':  r.get('jitter_max_ms', ''),
            }
            for r in all_results
        ]

        if args.csv_out:
            csv_out_path = Path(args.csv_out)
            csv_out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(csv_out_path, 'w', newline='') as _cf:
                writer = csv.DictWriter(_cf, fieldnames=_L1_FIELDS, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(_l1_rows)
            logger.info(f'  Level 1 KPI CSV written → {csv_out_path}  ({len(_l1_rows)} rows)')

        if args.xlsx_out:
            xlsx_out_path = Path(args.xlsx_out)
            xlsx_out_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                import openpyxl  # type: ignore
                from openpyxl.styles import Font as _Font  # type: ignore
                _wb = openpyxl.Workbook()
                _ws = _wb.active
                _ws.title = 'Level1 KPI'
                _ws.append(_L1_FIELDS)
                for _cell in _ws[1]:
                    _cell.font = _Font(bold=True)
                for _row in _l1_rows:
                    _ws.append([_row.get(f, '') for f in _L1_FIELDS])
                for _col in _ws.columns:
                    _ws.column_dimensions[_col[0].column_letter].width = (
                        max((len(str(c.value or '')) for c in _col), default=8) + 2
                    )
                _wb.save(xlsx_out_path)
                logger.info(f'  Level 1 KPI Excel written → {xlsx_out_path}  ({len(_l1_rows)} rows)')
            except ImportError:
                logger.warning('  openpyxl not installed — Excel export skipped. '
                      'Install with: pip install openpyxl')

    # ── Plot ─────────────────────────────────────────────────────────────────
    if args.plot:
        logger.info('\n  Generating plots…')
        plot_trigger_timeline(
            all_results,
            node_filter=args.node,
            session_dir=session_dir,
            show=not args.no_show,
        )


if __name__ == '__main__':
    main()
