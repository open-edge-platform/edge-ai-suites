#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
analyze_bag_e2e.py — Level 2 traced end-to-end pipeline KPI from a ROS 2 bag.

Complements analyze_pipeline_latency.py (which uses the *chained* method — summing
per-stage Level 1 representative-pair latencies).  This module uses the *traced*
method: correlate actual message timestamps recorded in the raw .mcap bag to measure
true sensor-to-control latency and detect message drops.

Algorithm
---------
1. Load the pipeline entry topic and exit topic from graph_topology.json (the
   highest-frequency Sensor-stage input and the highest-frequency Control-stage
   output, as determined from the companion Level 1 kpi.json).
2. Read all message timestamps for those two topics from the .mcap bag via
   rosbag2_py.SequentialReader.
3. For each entry timestamp, find the nearest exit timestamp within a configurable
   tolerance window (default 500 ms).  A message with no partner within the window
   counts as dropped.
4. Compute e2e latency statistics (mean/p50/p90/p99/max) from the matched pairs and
   drop rate from unmatched entry messages.
5. Assemble a Level 2 KPI dict with method='traced', inheriting stage_latency_ms and
   CPU fields from the companion Level 1 kpi.json (chained path still provides those).

Usage
-----
  # Traced e2e from the most recent session's bag
  uv run python src/analyze_bag_e2e.py

  # Specific session
  uv run python src/analyze_bag_e2e.py \\
      --bag  monitoring_sessions/wandering/20260430_145545/bag \\
      --kpi  monitoring_sessions/wandering/20260430_145545/kpi.json

  # Write Level 2 JSON output
  uv run python src/analyze_bag_e2e.py \\
      --bag  monitoring_sessions/wandering/20260430_145545/bag \\
      --kpi  monitoring_sessions/wandering/20260430_145545/kpi.json \\
      --json-out monitoring_sessions/wandering/20260430_145545/kpi_level2_traced.json

  # Adjust the correlation tolerance (default 500 ms)
  uv run python src/analyze_bag_e2e.py \\
      --bag  monitoring_sessions/wandering/20260430_145545/bag \\
      --kpi  monitoring_sessions/wandering/20260430_145545/kpi.json \\
      --tol-ms 1000
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Re-use metadata / validation helpers from the chained analyser.
from analyze_pipeline_latency import (  # noqa: E402
    STAGE_ORDER,
    _build_metadata,
    _find_latest_kpi,
    print_report,
    validate_level2_json,
)

# ──────────────────────────────────────────────────────────────────────────────
#  Bag reading
# ──────────────────────────────────────────────────────────────────────────────

_NS_PER_S = 1_000_000_000


def _load_bag_timestamps(bag_dir: Path, topics: List[str]) -> Dict[str, List[int]]:
    """
    Read all message receive-timestamps (nanoseconds) for the requested topics
    from an .mcap bag directory.

    Parameters
    ----------
    bag_dir:
        Directory that contains metadata.yaml and the *.mcap file(s).
    topics:
        List of ROS topic names to collect timestamps for.

    Returns
    -------
    dict mapping topic name → sorted list of timestamps in nanoseconds.
    Only topics that actually appear in the bag are included in the result.

    Raises
    ------
    ImportError  when rosbag2_py is not available (source the ROS overlay first).
    FileNotFoundError  when bag_dir does not exist or contains no metadata.yaml.
    """
    try:
        import rosbag2_py  # type: ignore  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            'rosbag2_py is required to read .mcap files.\n'
            '  source /opt/ros/jazzy/setup.bash  (or humble)'
        ) from exc

    metadata = bag_dir / 'metadata.yaml'
    if not metadata.exists():
        raise FileNotFoundError(
            f'No metadata.yaml in bag directory: {bag_dir}\n'
            '  Pass the directory that contains metadata.yaml, not the .mcap file itself.'
        )

    topic_set = set(topics)
    timestamps: Dict[str, List[int]] = {t: [] for t in topic_set}

    storage_opts = rosbag2_py.StorageOptions(uri=str(bag_dir), storage_id='mcap')
    converter_opts = rosbag2_py.ConverterOptions('', '')
    reader = rosbag2_py.SequentialReader()
    reader.open(storage_opts, converter_opts)

    # Apply a topic filter so rosbag2_py only deserialises what we need.
    filter_obj = rosbag2_py.StorageFilter()
    filter_obj.topics = list(topic_set)
    reader.set_filter(filter_obj)

    while reader.has_next():
        topic_name, _data, ts_ns = reader.read_next()
        if topic_name in topic_set:
            timestamps[topic_name].append(ts_ns)

    # Sort each list (should already be ordered but guarantee it).
    for ts_list in timestamps.values():
        ts_list.sort()

    # Drop topics that produced no messages.
    return {t: ts for t, ts in timestamps.items() if ts}


# ──────────────────────────────────────────────────────────────────────────────
#  Timestamp correlation
# ──────────────────────────────────────────────────────────────────────────────

def _correlate_e2e(
    entry_ts: List[int],
    exit_ts: List[int],
    tol_ns: int = 500_000_000,
) -> Dict:
    """
    Match each entry timestamp to the nearest exit timestamp within *tol_ns*.

    Uses bisect for O(n log n) performance.

    Parameters
    ----------
    entry_ts:
        Sorted list of pipeline-entry message timestamps (nanoseconds).
    exit_ts:
        Sorted list of pipeline-exit message timestamps (nanoseconds).
    tol_ns:
        Maximum allowed latency in nanoseconds.  Entry messages with no exit
        timestamp within [entry_ts, entry_ts + tol_ns] are counted as dropped.
        Default: 500_000_000 ns = 500 ms.

    Returns
    -------
    dict with keys:
        latencies_ms  - list[float] of matched e2e latencies in milliseconds
        drop_count    - int number of entry messages with no match
        n_entry       - int total entry messages considered
        n_exit        - int total exit messages available
    """
    latencies_ms: List[float] = []
    drop_count = 0
    n_exit = len(exit_ts)
    # Two-pointer: i advances only when a match is consumed, so each exit
    # timestamp is matched to at most one entry timestamp.
    i = 0

    for ts in entry_ts:
        # Skip exit timestamps that arrived before this entry message.
        while i < n_exit and exit_ts[i] < ts:
            i += 1
        if i >= n_exit:
            drop_count += 1
            continue
        delta_ns = exit_ts[i] - ts
        if delta_ns <= tol_ns:
            latencies_ms.append(delta_ns / 1_000_000.0)
            i += 1  # consume — cannot match another entry
        else:
            # Exit is too far ahead; do NOT consume — next entry may match it.
            drop_count += 1

    return {
        'latencies_ms': latencies_ms,
        'drop_count':   drop_count,
        'n_entry':      len(entry_ts),
        'n_exit':       n_exit,
    }


def _latency_stats(latencies_ms: List[float]) -> Dict:
    """Return mean/p50/p90/p99/max statistics dict, or all-None if list is empty."""
    if not latencies_ms:
        return {'mean': None, 'p50': None, 'p90': None, 'p99': None, 'max': None}
    n = len(latencies_ms)
    s = sorted(latencies_ms)

    def _pct(p: float) -> float:
        idx = (p / 100.0) * (n - 1)
        lo, hi = int(idx), min(int(idx) + 1, n - 1)
        frac = idx - lo
        return s[lo] + frac * (s[hi] - s[lo])

    return {
        'mean': round(statistics.mean(latencies_ms), 3),
        'p50':  round(_pct(50), 3),
        'p90':  round(_pct(90), 3),
        'p99':  round(_pct(99), 3),
        'max':  round(max(latencies_ms), 3),
    }


# ──────────────────────────────────────────────────────────────────────────────
#  Pipeline entry / exit topic selection
# ──────────────────────────────────────────────────────────────────────────────

def _pick_entry_exit_topics(kpi1: dict) -> tuple[str, str]:
    """
    Choose the pipeline entry and exit topics from a Level 1 kpi.json.

    Entry  = primary_input of the highest-throughput Sensor-stage node.
    Exit   = primary_output of the highest-throughput Control-stage node.

    Falls back to the first Sensor/Control node found if throughput is absent.

    Returns
    -------
    (entry_topic, exit_topic)
    """
    per_node: dict = kpi1.get('per_node', {})
    if not per_node:
        raise ValueError('Level 1 kpi.json has no per_node entries.')

    sensor_nodes  = {n: v for n, v in per_node.items() if v.get('pipeline_stage') == 'Sensor'}
    control_nodes = {n: v for n, v in per_node.items() if v.get('pipeline_stage') == 'Control'}

    if not sensor_nodes:
        raise ValueError('No Sensor-stage nodes found in Level 1 kpi.json.')
    if not control_nodes:
        raise ValueError('No Control-stage nodes found in Level 1 kpi.json.')

    best_sensor  = max(sensor_nodes.items(),  key=lambda kv: kv[1].get('throughput_hz', 0.0))
    best_control = max(control_nodes.items(), key=lambda kv: kv[1].get('throughput_hz', 0.0))

    entry_topic = best_sensor[1]['primary_input']
    exit_topic  = best_control[1]['primary_output']
    return entry_topic, exit_topic


# ──────────────────────────────────────────────────────────────────────────────
#  Main derivation
# ──────────────────────────────────────────────────────────────────────────────

def derive_traced(
    bag_dir: Path,
    kpi1_path: Path,
    tol_ms: float = 500.0,
) -> dict:
    """
    Derive a Level 2 KPI dict using the *traced* method.

    Reads the raw .mcap bag to correlate pipeline entry and exit message
    timestamps, producing genuine end-to-end latency and drop-rate measurements.
    Stage-level breakdown and CPU utilisation are inherited from the companion
    Level 1 kpi.json (same as the chained path in analyze_pipeline_latency.py).

    Parameters
    ----------
    bag_dir:
        Directory containing the .mcap bag (has metadata.yaml inside).
    kpi1_path:
        Path to the Level 1 kpi.json produced by analyze_trigger_latency.py.
    tol_ms:
        Correlation window in milliseconds.  Entry messages with no exit message
        within this window are counted as dropped.  Default: 500 ms.

    Returns
    -------
    Level 2 KPI dict conforming to kpi_level2_v1.json with method='traced'.
    """
    with open(kpi1_path) as f:
        kpi1 = json.load(f)

    # Derive stage breakdown first so we use the same consistent topic selection
    # as the per-stage table (representative_input/output, not primary_input/output).
    # This avoids the bug where primary_output for a Control node (e.g.
    # velocity_smoother) resolves to the same topic as the Sensor entry topic,
    # producing a degenerate /cmd_vel → /cmd_vel pipeline with 0 ms latency.
    from analyze_pipeline_latency import derive_level2  # noqa: PLC0415
    kpi2_chained = derive_level2(kpi1_path)

    entry_topic = kpi2_chained['pipeline']['input_topic']
    exit_topic  = kpi2_chained['pipeline']['output_topic']

    if entry_topic == exit_topic:
        raise ValueError(
            f'Pipeline entry and exit resolved to the same topic ({entry_topic!r}). '
            'The Level 1 KPI has an ambiguous stage topology; '
            'cannot compute a meaningful end-to-end latency.'
        )

    # Load timestamps from bag.
    tol_ns = int(tol_ms * 1_000_000)
    ts_map = _load_bag_timestamps(bag_dir, [entry_topic, exit_topic])

    entry_ts = ts_map.get(entry_topic, [])
    exit_ts  = ts_map.get(exit_topic,  [])

    if not entry_ts:
        raise ValueError(
            f'Entry topic {entry_topic!r} produced no messages in bag: {bag_dir}'
        )
    if not exit_ts:
        raise ValueError(
            f'Exit topic {exit_topic!r} produced no messages in bag: {bag_dir}'
        )

    corr = _correlate_e2e(entry_ts, exit_ts, tol_ns=tol_ns)
    stats = _latency_stats(corr['latencies_ms'])

    # Drop rate: fraction of entry messages that could not be matched.
    n_entry = corr['n_entry']
    drop_rate_pct = round(corr['drop_count'] / n_entry * 100.0, 2) if n_entry > 0 else None

    # Throughput: exit message rate from bag wall time.
    throughput_hz: Optional[float] = None
    if len(exit_ts) >= 2:
        span_s = (exit_ts[-1] - exit_ts[0]) / _NS_PER_S
        if span_s > 0:
            throughput_hz = round((len(exit_ts) - 1) / span_s, 3)

    session_dir = kpi1_path.parent
    present_stages = [s for s in STAGE_ORDER if s in kpi2_chained.get('stage_latency_ms', {})]

    return {
        'schema_version': 'level2_v1',
        'pipeline': {
            'input_topic':    entry_topic,
            'output_topic':   exit_topic,
            'stage_sequence': present_stages,
        },
        'e2e_latency_ms': {
            'mean':   stats['mean'],
            'p50':    stats['p50'],
            'p90':    stats['p90'],
            'p99':    stats['p99'],
            'max':    stats['max'],
            'n':      len(corr['latencies_ms']),
            'method': 'traced',
        },
        'throughput_hz':    throughput_hz,
        'drop_rate_pct':    drop_rate_pct,
        'bottleneck_stage': kpi2_chained.get('bottleneck_stage'),
        'stage_latency_ms': kpi2_chained.get('stage_latency_ms', {}),
        'cpu_mean_pct':     kpi1.get('cpu_mean_pct'),
        'cpu_max_pct':      kpi1.get('cpu_max_pct'),
        'bag_source':       str(bag_dir.resolve()),
        'level1_source':    str(kpi1_path.resolve()),
        'metadata':         _build_metadata(session_dir, level1_meta=kpi1.get('metadata')),
    }


# ──────────────────────────────────────────────────────────────────────────────
#  Session discovery
# ──────────────────────────────────────────────────────────────────────────────

def _find_latest_bag(sessions_root: Path) -> Optional[Path]:
    """
    Return the bag directory of the most-recently-modified session under
    *sessions_root*.  Looks for directories that contain metadata.yaml.
    """
    candidates = sorted(
        sessions_root.rglob('metadata.yaml'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0].parent if candidates else None


# ──────────────────────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point for traced Level 2 pipeline KPI analysis."""
    parser = argparse.ArgumentParser(
        description='Level 2 traced end-to-end pipeline KPI from a ROS 2 .mcap bag.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Most recent session (auto-discover bag and kpi.json)
  uv run python src/analyze_bag_e2e.py

  # Specific session
  uv run python src/analyze_bag_e2e.py \\
      --bag monitoring_sessions/wandering/20260430_145545/bag \\
      --kpi monitoring_sessions/wandering/20260430_145545/kpi.json

  # Write traced Level 2 JSON
  uv run python src/analyze_bag_e2e.py \\
      --bag monitoring_sessions/wandering/20260430_145545/bag \\
      --kpi monitoring_sessions/wandering/20260430_145545/kpi.json \\
      --json-out monitoring_sessions/wandering/20260430_145545/kpi_level2_traced.json

  # Wider correlation window
  uv run python src/analyze_bag_e2e.py \\
      --bag monitoring_sessions/wandering/20260430_145545/bag \\
      --kpi monitoring_sessions/wandering/20260430_145545/kpi.json \\
      --tol-ms 1000
        """,
    )
    parser.add_argument(
        '--bag',
        type=str,
        default=None,
        metavar='DIR',
        help='Path to the bag directory (contains metadata.yaml). '
             'Default: most recent bag under monitoring_sessions/.',
    )
    parser.add_argument(
        '--kpi',
        type=str,
        default=None,
        metavar='PATH',
        help='Path to the companion Level 1 kpi.json. '
             'Default: kpi.json in the same session directory as the bag.',
    )
    parser.add_argument(
        '--tol-ms',
        type=float,
        default=500.0,
        metavar='MS',
        help='Correlation tolerance in milliseconds. Entry messages with no exit '
             'message within this window are counted as dropped. Default: 500.',
    )
    parser.add_argument(
        '--json-out',
        type=str,
        default=None,
        metavar='PATH',
        help='Write traced Level 2 KPI JSON to this path and validate against the schema.',
    )
    parser.add_argument(
        '--csv-out',
        type=str,
        default=None,
        metavar='PATH',
        help='Write traced Level 2 KPI as a flat CSV (same columns as '
             'analyze_pipeline_latency.py --csv-out).',
    )
    args = parser.parse_args()

    ws_root = Path(__file__).resolve().parent.parent

    # Resolve bag directory.
    if args.bag:
        bag_dir = Path(args.bag).resolve()
    else:
        sessions_root = ws_root / 'monitoring_sessions'
        bag_dir = _find_latest_bag(sessions_root)
        if bag_dir is None:
            print(f'ERROR: No bag found under {sessions_root}', file=sys.stderr)
            sys.exit(1)
        print(f'  Auto-selected bag: {bag_dir}')

    if not bag_dir.exists():
        print(f'ERROR: Bag directory not found: {bag_dir}', file=sys.stderr)
        sys.exit(1)

    # Resolve Level 1 kpi.json.
    if args.kpi:
        kpi1_path = Path(args.kpi).resolve()
    else:
        # Look for kpi.json in the session directory (parent of bag/).
        kpi1_path = _find_latest_kpi(bag_dir.parent)
        if kpi1_path is None:
            # Fall back to workspace-wide search.
            kpi1_path = _find_latest_kpi(ws_root / 'monitoring_sessions')
        if kpi1_path is None:
            print('ERROR: No kpi.json found. Pass --kpi <path>.', file=sys.stderr)
            sys.exit(1)
        print(f'  Auto-selected kpi.json: {kpi1_path}')

    if not kpi1_path.exists():
        print(f'ERROR: kpi.json not found: {kpi1_path}', file=sys.stderr)
        sys.exit(1)

    print(f'\n  Bag        : {bag_dir}')
    print(f'  Level 1 KPI: {kpi1_path}')
    print(f'  Tolerance  : {args.tol_ms} ms\n')

    try:
        kpi2 = derive_traced(bag_dir, kpi1_path, tol_ms=args.tol_ms)
    except (ValueError, FileNotFoundError, ImportError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)

    print_report(kpi2, kpi1_path)

    if args.json_out:
        import csv as _csv  # noqa: PLC0415
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w') as f:
            json.dump(kpi2, f, indent=2)
        print(f'  Traced Level 2 KPI JSON written → {out_path}')

        errors = validate_level2_json(kpi2)
        if errors:
            print(
                f'  WARNING: schema validation failed ({len(errors)} error(s)):',
                file=sys.stderr,
            )
            for e in errors:
                print(f'    • {e}', file=sys.stderr)
        else:
            print('  Schema validation passed ✓')

    if args.csv_out:
        import csv as _csv  # noqa: PLC0415,F811
        _L2_FIELDS = [
            'type', 'session', 'stage',
            'representative_node', 'representative_input', 'representative_output',
            'mean_ms', 'p50_ms', 'p90_ms', 'p99_ms', 'max_ms', 'n',
            'throughput_hz', 'drop_rate_pct', 'bottleneck_stage',
            'cpu_mean_pct', 'cpu_max_pct',
        ]
        session_name = kpi2['metadata']['name']
        e2e  = kpi2['e2e_latency_ms']
        pipe = kpi2['pipeline']
        _rows = [{
            'type':                   'e2e',
            'session':                session_name,
            'stage':                  'e2e',
            'representative_node':    '',
            'representative_input':   pipe['input_topic'],
            'representative_output':  pipe['output_topic'],
            'mean_ms':                e2e.get('mean', ''),
            'p50_ms':                 e2e.get('p50', ''),
            'p90_ms':                 e2e.get('p90', ''),
            'p99_ms':                 e2e.get('p99', ''),
            'max_ms':                 e2e.get('max', ''),
            'n':                      e2e.get('n', ''),
            'throughput_hz':          kpi2.get('throughput_hz', ''),
            'drop_rate_pct':          kpi2.get('drop_rate_pct', ''),
            'bottleneck_stage':       kpi2.get('bottleneck_stage', ''),
            'cpu_mean_pct':           kpi2.get('cpu_mean_pct', ''),
            'cpu_max_pct':            kpi2.get('cpu_max_pct', ''),
        }]
        for stage in pipe['stage_sequence']:
            entry = kpi2['stage_latency_ms'].get(stage, {})
            _rows.append({
                'type':                   'stage',
                'session':                session_name,
                'stage':                  stage,
                'representative_node':    entry.get('representative_node', ''),
                'representative_input':   entry.get('representative_input', ''),
                'representative_output':  entry.get('representative_output', ''),
                'mean_ms':                entry.get('mean_ms', ''),
                'p50_ms':                 entry.get('p50_ms', ''),
                'p90_ms':                 entry.get('p90_ms', ''),
                'p99_ms':                 entry.get('p99_ms', ''),
                'max_ms':                 entry.get('max_ms', ''),
                'n':                      entry.get('n', ''),
                'throughput_hz':          entry.get('throughput_hz', ''),
                'drop_rate_pct':          '',
                'bottleneck_stage':       '',
                'cpu_mean_pct':           '',
                'cpu_max_pct':            '',
            })
        csv_path = Path(args.csv_out)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, 'w', newline='') as _cf:
            writer = _csv.DictWriter(_cf, fieldnames=_L2_FIELDS, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(_rows)
        print(f'  Traced Level 2 KPI CSV written → {csv_path}  ({len(_rows)} rows)')


if __name__ == '__main__':
    main()
