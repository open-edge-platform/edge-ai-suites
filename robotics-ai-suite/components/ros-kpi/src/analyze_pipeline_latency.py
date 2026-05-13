#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
analyze_pipeline_latency.py — Level 2 end-to-end pipeline KPI analysis.

Reads a Level 1 kpi.json produced by analyze_trigger_latency.py and derives
Level 2 pipeline KPIs:

  - End-to-end latency   (sensor input → control output, chained from stages)
  - Pipeline throughput  (bottleneck stage rate)
  - Drop rate            (% of sensor inputs without a matching control output)
  - Per-stage latency    (Sensor / Perception / Planning / Control breakdown)
  - Bottleneck stage     (highest mean latency contributor)

Method: "chained" — the per-stage e2e estimates are computed by summing the
representative (highest trigger-count) pair's latency statistics for each
pipeline stage present in the Level 1 data.  This is a conservative estimate
suitable for regression tracking.  True message-traced e2e would require
correlating header stamps across all stages in the raw bag.

Usage
-----
  # Analyse the most recent wandering session
  uv run python src/analyze_pipeline_latency.py

  # Specific session kpi.json
  uv run python src/analyze_pipeline_latency.py --kpi monitoring_sessions/wandering/20260424_173315/kpi.json

  # Write Level 2 JSON output
  uv run python src/analyze_pipeline_latency.py --json-out monitoring_sessions/wandering/20260424_173315/kpi_level2.json

  # Specify the bench directory to aggregate across all runs
  uv run python src/analyze_pipeline_latency.py --bench monitoring_sessions/wandering/bench_20260424_120000
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import socket
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional


# ──────────────────────────────────────────────────────────────────────────────
#  Pipeline stage ordering
# ──────────────────────────────────────────────────────────────────────────────

STAGE_ORDER = ['Sensor', 'Perception', 'Planning', 'Control', 'Other']


# ──────────────────────────────────────────────────────────────────────────────
#  Schema path
# ──────────────────────────────────────────────────────────────────────────────

def _schema_path() -> Path:
    return Path(__file__).resolve().parent.parent / 'schemas' / 'kpi_level2_v1.json'


def validate_level2_json(payload: dict) -> list[str]:
    """Validate payload against the Level 2 schema. Returns list of error strings."""
    schema_file = _schema_path()
    if not schema_file.exists():
        return [f'Schema file not found: {schema_file}']
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return ['jsonschema not installed — skipping validation (pip install jsonschema)']
    with open(schema_file) as f:
        schema = json.load(f)
    ValidatorCls = getattr(jsonschema, 'Draft202012Validator', None) or \
        getattr(jsonschema, 'Draft7Validator', None) or \
        jsonschema.Draft4Validator
    validator = ValidatorCls(schema)
    return [str(e.message) for e in sorted(validator.iter_errors(payload), key=str)]


# ──────────────────────────────────────────────────────────────────────────────
#  Provenance helpers (shared with Level 1)
# ──────────────────────────────────────────────────────────────────────────────

def _framework_version() -> str:
    try:
        import importlib.metadata
        return importlib.metadata.version('ros2-kpi')
    except Exception:
        pass
    try:
        import re as _re
        p = Path(__file__).resolve().parent.parent / 'pyproject.toml'
        m = _re.search(r'^version\s*=\s*"([^"]+)"', p.read_text(), _re.MULTILINE)
        return m.group(1) if m else 'unknown'
    except Exception:
        return 'unknown'


def _cpu_model() -> str:
    try:
        with open('/proc/cpuinfo') as f:
            for line in f:
                if line.startswith('model name'):
                    return line.split(':', 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or 'unknown'


def _gpu_model() -> Optional[str]:
    try:
        import subprocess as _sp
        out = _sp.run(['lspci', '-mm'], capture_output=True, text=True, timeout=5).stdout
        for line in out.splitlines():
            low = line.lower()
            if 'vga' in low or '3d controller' in low or 'display' in low:
                parts = [p.strip().strip('"') for p in line.split('"') if p.strip().strip('"')]
                return parts[2] if len(parts) >= 3 else line.strip()
    except Exception:
        pass
    return None


def _total_ram_gb() -> Optional[float]:
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 2)
    except Exception:
        return None


def _build_metadata(session_dir: Path, level1_meta: Optional[dict] = None) -> dict:
    """
    Build Level 2 metadata.

    When level1_meta is provided (the metadata block from the source kpi.json),
    inherit ros_distro, framework_version, and hardware from it — these were
    captured during the actual ROS session and are more reliable than
    re-probing the environment from inside uv run.
    """
    if level1_meta:
        ros_distro        = level1_meta.get('ros_distro') or os.environ.get('ROS_DISTRO', 'unknown')
        framework_version = level1_meta.get('framework_version') or _framework_version()
        hardware          = level1_meta.get('hardware') or {
            'cpu_model':    _cpu_model(),
            'cpu_cores':    os.cpu_count(),
            'gpu_model':    _gpu_model(),
            'total_ram_gb': _total_ram_gb(),
        }
        hostname = level1_meta.get('hostname', socket.gethostname())
        arch     = level1_meta.get('arch', platform.machine())
        os_str   = level1_meta.get('os', f'{platform.system()} {platform.release()}')
    else:
        ros_distro        = os.environ.get('ROS_DISTRO', 'unknown')
        framework_version = _framework_version()
        hardware          = {
            'cpu_model':    _cpu_model(),
            'cpu_cores':    os.cpu_count(),
            'gpu_model':    _gpu_model(),
            'total_ram_gb': _total_ram_gb(),
        }
        hostname = socket.gethostname()
        arch     = platform.machine()
        os_str   = f'{platform.system()} {platform.release()}'

    return {
        'name':              session_dir.name,
        'datetime':          datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'hostname':          hostname,
        'arch':              arch,
        'os':                os_str,
        'data_path':         str(session_dir),
        'framework_version': framework_version,
        'ros_distro':        ros_distro,
        'hardware':          hardware,
    }


# ──────────────────────────────────────────────────────────────────────────────
#  Level 1 → Level 2 derivation
# ──────────────────────────────────────────────────────────────────────────────

def _representative_pair(pairs: List[dict]) -> dict:
    """Return the pair with the highest trigger_count (most active path)."""
    return max(pairs, key=lambda p: p.get('trigger_count', 0))


def derive_level2(kpi1_path: Path) -> dict:
    """
    Load a Level 1 kpi.json and return a Level 2 KPI dict.

    Algorithm
    ---------
    1. Group per_node entries by pipeline_stage.
    2. For each stage, find the representative pair from the 'pairs' list
       (highest trigger_count among pairs belonging to that stage's nodes).
    3. Sum representative latency statistics across stages for e2e estimates.
    4. Drop rate = max(0, 1 - n_control / n_sensor) * 100.
    5. Throughput = min throughput_hz across stage representatives.
    6. Bottleneck = stage with highest mean_ms.
    """
    with open(kpi1_path) as f:
        kpi1 = json.load(f)

    per_node: dict = kpi1.get('per_node', {})
    pairs: List[dict] = kpi1.get('pairs', [])

    if not per_node or not pairs:
        raise ValueError(f'Level 1 KPI has no per_node/pairs data: {kpi1_path}')

    # Map node → pipeline_stage
    node_stage: Dict[str, str] = {
        node: info['pipeline_stage']
        for node, info in per_node.items()
    }

    # Group pairs by pipeline stage of their node
    stage_pairs: Dict[str, List[dict]] = defaultdict(list)
    for pair in pairs:
        stage = node_stage.get(pair['node'], 'Other')
        stage_pairs[stage].append(pair)

    # Identify which stages are actually present (in order)
    present_stages = [s for s in STAGE_ORDER if s in stage_pairs]

    if not present_stages:
        raise ValueError('No pipeline stages found in Level 1 data.')

    # Build per-stage entries
    stage_latency_ms: dict = {}
    all_nodes_in_stage: Dict[str, List[str]] = defaultdict(list)
    for node, stage in node_stage.items():
        all_nodes_in_stage[stage].append(node)

    for stage in present_stages:
        rep = _representative_pair(stage_pairs[stage])
        stage_latency_ms[stage] = {
            'mean_ms':               rep['mean_ms'],
            'p50_ms':                rep.get('p50_ms'),
            'p90_ms':                rep['p90_ms'],
            'p99_ms':                rep.get('p99_ms'),
            'max_ms':                rep.get('max_ms'),
            'n':                     rep['n'],
            'throughput_hz':         rep.get('fps'),
            'nodes':                 sorted(all_nodes_in_stage.get(stage, [])),
            'representative_node':   rep['node'],
            'representative_input':  rep['input'],
            'representative_output': rep['output'],
        }

    # ── E2E latency: sum across stages ───────────────────────────────────────
    def _sum_field(field: str) -> Optional[float]:
        vals = [stage_latency_ms[s].get(field) for s in present_stages]
        if any(v is None for v in vals):
            return None
        return sum(vals)  # type: ignore[arg-type]

    e2e_mean = _sum_field('mean_ms')
    e2e_p50  = _sum_field('p50_ms')
    e2e_p90  = _sum_field('p90_ms')
    e2e_p99  = _sum_field('p99_ms')
    e2e_max  = _sum_field('max_ms')
    e2e_n    = min(stage_latency_ms[s]['n'] for s in present_stages)

    # ── Throughput: bottleneck (min Hz across stages) ─────────────────────────
    hz_vals = [
        stage_latency_ms[s]['throughput_hz']
        for s in present_stages
        if stage_latency_ms[s].get('throughput_hz') is not None
    ]
    throughput_hz = min(hz_vals) if hz_vals else None

    # ── Drop rate ─────────────────────────────────────────────────────────────
    n_sensor  = stage_latency_ms.get('Sensor', {}).get('n')
    n_control = stage_latency_ms.get('Control', {}).get('n')
    if n_sensor and n_control and n_sensor > 0:
        drop_rate_pct = max(0.0, (1.0 - n_control / n_sensor) * 100.0)
    else:
        drop_rate_pct = None

    # ── Bottleneck ────────────────────────────────────────────────────────────
    bottleneck = max(present_stages, key=lambda s: stage_latency_ms[s]['mean_ms'])

    # ── Pipeline entry / exit ─────────────────────────────────────────────────
    input_stage  = present_stages[0]
    output_stage = present_stages[-1]
    input_topic  = stage_latency_ms[input_stage]['representative_input']
    output_topic = stage_latency_ms[output_stage]['representative_output']

    # ── Assemble Level 2 payload ──────────────────────────────────────────────
    session_dir = kpi1_path.parent

    return {
        'schema_version': 'level2_v1',
        'pipeline': {
            'input_topic':    input_topic,
            'output_topic':   output_topic,
            'stage_sequence': present_stages,
        },
        'e2e_latency_ms': {
            'mean':   e2e_mean,
            'p50':    e2e_p50,
            'p90':    e2e_p90,
            'p99':    e2e_p99,
            'max':    e2e_max,
            'n':      e2e_n,
            'method': 'chained',
        },
        'throughput_hz':   throughput_hz,
        'drop_rate_pct':   drop_rate_pct,
        'bottleneck_stage': bottleneck,
        'stage_latency_ms': stage_latency_ms,
        'cpu_mean_pct':    kpi1.get('cpu_mean_pct'),
        'cpu_max_pct':     kpi1.get('cpu_max_pct'),
        'level1_source':   str(kpi1_path.resolve()),
        'metadata':        _build_metadata(session_dir, level1_meta=kpi1.get('metadata')),
    }


# ──────────────────────────────────────────────────────────────────────────────
#  Console report
# ──────────────────────────────────────────────────────────────────────────────

_HEALTH = {
    'OK':     '✅',
    'WARN':   '🟡',
    'SLOW':   '🟠',
    'CRIT':   '🔴',
}


def _health(ms: Optional[float]) -> str:
    """Return a health emoji for a latency value in milliseconds."""
    if ms is None:
        return '  '
    if ms < 100:   return '✅'
    if ms < 300:   return '🟡'
    if ms < 1000:  return '🟠'
    return '🔴'


def print_report(kpi2: dict, kpi1_path: Path) -> None:
    """Print a formatted Level 2 pipeline KPI report to stdout."""
    W = 90
    print()
    print('━' * W)
    print('  Level 2 Pipeline KPI')
    print(f'  Source  : {kpi1_path}')
    m = kpi2['metadata']
    print(f'  Host    : {m["hostname"]}  ({m["hardware"]["cpu_model"]})')
    print(f'  ROS     : {m["ros_distro"]}  |  Framework: {m["framework_version"]}')
    print('━' * W)

    pipe  = kpi2['pipeline']
    e2e   = kpi2['e2e_latency_ms']
    print(f'\n  Pipeline  : {pipe["input_topic"]}  →  {pipe["output_topic"]}')
    print(f'  Stages    : {" → ".join(pipe["stage_sequence"])}')
    print(f'  Method    : {e2e["method"]}')

    h = _health(e2e['mean'])
    print(f'\n  {h} End-to-end latency (chained)')
    print(f'       mean : {e2e["mean"]:.1f} ms' if e2e['mean'] is not None else '       mean : —')
    print(f'        p50 : {e2e["p50"]:.1f} ms' if e2e.get('p50') is not None else '        p50 : —')
    print(f'        p90 : {e2e["p90"]:.1f} ms' if e2e.get('p90') is not None else '        p90 : —')
    print(f'        p99 : {e2e["p99"]:.1f} ms' if e2e.get('p99') is not None else '        p99 : —')
    print(f'        max : {e2e["max"]:.1f} ms' if e2e.get('max') is not None else '        max : —')
    print(f'          n : {e2e["n"]} samples (min across stages)')

    hz = kpi2.get('throughput_hz')
    print(f'\n  Throughput     : {hz:.2f} Hz' if hz is not None else '\n  Throughput     : —')
    dr = kpi2.get('drop_rate_pct')
    print(f'  Drop rate      : {dr:.1f}%' if dr is not None else '  Drop rate      : —')
    print(f'  Bottleneck     : {kpi2["bottleneck_stage"]}')

    print('\n  Per-stage breakdown:')
    print(f'  {"Stage":<14} {"Node":<28} {"mean":>8} {"p90":>8} {"Hz":>8}  Representative pair')
    print(f'  {"─"*14} {"─"*28} {"─"*8} {"─"*8} {"─"*8}  {"─"*32}')
    for stage in kpi2['pipeline']['stage_sequence']:
        entry = kpi2['stage_latency_ms'].get(stage)
        if not entry:
            continue
        h_s  = _health(entry['mean_ms'])
        nd   = entry['representative_node'].split('/')[-1][:26]
        hz_s = f'{entry["throughput_hz"]:.1f}' if entry.get('throughput_hz') else '—'
        inp  = entry['representative_input'].split('/')[-1][:16]
        out  = entry['representative_output'].split('/')[-1][:16]
        print(f'  {h_s} {stage:<12} {nd:<28} {entry["mean_ms"]:>7.1f}ms '
              f'{entry["p90_ms"]:>7.1f}ms {hz_s:>8}  {inp} → {out}')
    print()
    print('━' * W)


# ──────────────────────────────────────────────────────────────────────────────
#  Session / bench discovery
# ──────────────────────────────────────────────────────────────────────────────

def _find_latest_kpi(sessions_root: Path) -> Optional[Path]:
    """Return the most-recently-modified kpi.json under sessions_root."""
    candidates = sorted(
        sessions_root.rglob('kpi.json'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


# ──────────────────────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point for Level 2 pipeline KPI analysis."""
    parser = argparse.ArgumentParser(
        description='Level 2 end-to-end pipeline KPI analysis from Level 1 kpi.json.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyse the most recent session automatically
  uv run python src/analyze_pipeline_latency.py

  # Specific Level 1 kpi.json
  uv run python src/analyze_pipeline_latency.py \\
      --kpi monitoring_sessions/wandering/20260424_173315/kpi.json

  # Write Level 2 output next to the Level 1 file
  uv run python src/analyze_pipeline_latency.py \\
      --kpi monitoring_sessions/wandering/20260424_173315/kpi.json \\
      --json-out monitoring_sessions/wandering/20260424_173315/kpi_level2.json

  # Also export a flat CSV (e2e summary + one row per pipeline stage)
  uv run python src/analyze_pipeline_latency.py \\
      --kpi monitoring_sessions/wandering/20260424_173315/kpi.json \\
      --csv-out monitoring_sessions/wandering/20260424_173315/kpi_level2.csv
        """,
    )
    parser.add_argument(
        '--kpi',
        type=str,
        default=None,
        metavar='PATH',
        help='Path to Level 1 kpi.json. Default: most recent kpi.json under '
             'monitoring_sessions/.',
    )
    parser.add_argument(
        '--json-out',
        type=str,
        default=None,
        metavar='PATH',
        help='Write Level 2 KPI JSON to this path and validate against the schema.',
    )
    parser.add_argument(
        '--csv-out',
        type=str,
        default=None,
        metavar='PATH',
        help='Write Level 2 KPI results as a flat CSV. '
             'Contains one summary row (type=e2e) and one row per pipeline stage (type=stage). '
             'Columns: type, session, stage, representative_node, representative_input, '
             'representative_output, mean_ms, p50_ms, p90_ms, p99_ms, max_ms, n, '
             'throughput_hz, drop_rate_pct, bottleneck_stage, cpu_mean_pct, cpu_max_pct.',
    )
    parser.add_argument(
        '--xlsx-out',
        type=str,
        default=None,
        metavar='PATH',
        help='Write Level 2 KPI results as an Excel workbook (.xlsx). '
             'Same columns as --csv-out. Requires openpyxl (pip install openpyxl).',
    )
    args = parser.parse_args()

    ws_root = Path(__file__).resolve().parent.parent

    # Resolve Level 1 kpi.json
    if args.kpi:
        kpi1_path = Path(args.kpi).resolve()
    else:
        sessions_root = ws_root / 'monitoring_sessions'
        kpi1_path = _find_latest_kpi(sessions_root)
        if kpi1_path is None:
            print(f'ERROR: No kpi.json found under {sessions_root}', file=sys.stderr)
            print('  Run: uv run python src/analyze_trigger_latency.py --json-out <session>/kpi.json',
                  file=sys.stderr)
            sys.exit(1)
        print(f'  Auto-selected: {kpi1_path}')

    if not kpi1_path.exists():
        print(f'ERROR: kpi.json not found: {kpi1_path}', file=sys.stderr)
        sys.exit(1)

    print(f'\n  Loading Level 1 KPI from: {kpi1_path}')

    try:
        kpi2 = derive_level2(kpi1_path)
    except ValueError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)

    print_report(kpi2, kpi1_path)

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w') as f:
            json.dump(kpi2, f, indent=2)
        print(f'  Level 2 KPI JSON written → {out_path}')

        errors = validate_level2_json(kpi2)
        if errors:
            print(f'  WARNING: KPI Level 2 JSON failed schema validation ({len(errors)} error(s)):',
                  file=sys.stderr)
            for e in errors:
                print(f'    • {e}', file=sys.stderr)
        else:
            print('  KPI Level 2 JSON schema validation passed ✓')

    if args.csv_out or args.xlsx_out:
        import csv as _csv
        _L2_FIELDS = [
            'type', 'session', 'stage',
            'representative_node', 'representative_input', 'representative_output',
            'mean_ms', 'p50_ms', 'p90_ms', 'p99_ms', 'max_ms', 'n',
            'throughput_hz', 'drop_rate_pct', 'bottleneck_stage',
            'cpu_mean_pct', 'cpu_max_pct',
        ]
        session_name = kpi2['metadata']['name']
        e2e = kpi2['e2e_latency_ms']
        pipe = kpi2['pipeline']
        _l2_rows = []
        # E2E summary row
        _l2_rows.append({
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
        })
        # Per-stage rows
        for stage in pipe['stage_sequence']:
            entry = kpi2['stage_latency_ms'].get(stage, {})
            _l2_rows.append({
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

        if args.csv_out:
            csv_out_path = Path(args.csv_out)
            csv_out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(csv_out_path, 'w', newline='') as _cf:
                writer = _csv.DictWriter(_cf, fieldnames=_L2_FIELDS, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(_l2_rows)
            print(f'  Level 2 KPI CSV written → {csv_out_path}  ({len(_l2_rows)} rows)')

        if args.xlsx_out:
            xlsx_out_path = Path(args.xlsx_out)
            xlsx_out_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                import openpyxl  # type: ignore
                from openpyxl.styles import Font as _Font  # type: ignore
                _wb = openpyxl.Workbook()
                _ws = _wb.active
                _ws.title = 'Level2 KPI'
                _ws.append(_L2_FIELDS)
                for _cell in _ws[1]:
                    _cell.font = _Font(bold=True)
                for _row in _l2_rows:
                    _ws.append([_row.get(f, '') for f in _L2_FIELDS])
                for _col in _ws.columns:
                    _ws.column_dimensions[_col[0].column_letter].width = (
                        max((len(str(c.value or '')) for c in _col), default=8) + 2
                    )
                _wb.save(xlsx_out_path)
                print(f'  Level 2 KPI Excel written → {xlsx_out_path}  ({len(_l2_rows)} rows)')
            except ImportError:
                print('  WARNING: openpyxl not installed — Excel export skipped. '
                      'Install with: pip install openpyxl', file=sys.stderr)


if __name__ == '__main__':
    main()
