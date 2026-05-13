#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Smoke test for --csv-out on analyze_trigger_latency.py and analyze_pipeline_latency.py.

Run:
    python3 tests/test_csv_export.py
"""

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC  = ROOT / 'src'

# ──────────────────────────────────────────────────────────────────────────────
#  Minimal synthetic Level 1 kpi.json
# ──────────────────────────────────────────────────────────────────────────────

LEVEL1_KPI = {
    'schema_version': 'level1_v1',
    'throughput_hz': 20.0,
    'mean_latency_ms': 50.0,
    'max_jitter_ms': 5.0,
    'min_jitter_ms': 0.5,
    'mean_jitter_ms': 2.0,
    'jitter_stdev_ms': 1.0,
    'cpu_mean_pct': 30.0,
    'cpu_max_pct': 60.0,
    'per_node': {
        '/camera_node': {
            'throughput_hz': 20.0,
            'mean_latency_ms': 10.0,
            'mean_jitter_ms': 1.0,
            'max_jitter_ms': 3.0,
            'num_samples': 200,
            'primary_input': '/camera/raw',
            'primary_output': '/camera/image',
            'pipeline_stage': 'Sensor',
        },
        '/detector_node': {
            'throughput_hz': 18.0,
            'mean_latency_ms': 40.0,
            'mean_jitter_ms': 3.0,
            'max_jitter_ms': 8.0,
            'num_samples': 180,
            'primary_input': '/camera/image',
            'primary_output': '/detections',
            'pipeline_stage': 'Perception',
        },
        '/planner_node': {
            'throughput_hz': 15.0,
            'mean_latency_ms': 60.0,
            'mean_jitter_ms': 4.0,
            'max_jitter_ms': 12.0,
            'num_samples': 150,
            'primary_input': '/detections',
            'primary_output': '/cmd_vel',
            'pipeline_stage': 'Planning',
        },
    },
    'pairs': [
        {
            'node': '/camera_node',
            'input': '/camera/raw',
            'output': '/camera/image',
            'pipeline_stage': 'Sensor',
            'n': 200,
            'mean_ms': 10.0,
            'stdev_ms': 1.2,
            'min_ms': 7.0,
            'p50_ms': 10.0,
            'p90_ms': 12.0,
            'p99_ms': 14.0,
            'max_ms': 16.0,
            'trigger_count': 200,
            'fps': 20.0,
            'jitter_mean_ms': 1.0,
            'jitter_max_ms': 3.0,
        },
        {
            'node': '/detector_node',
            'input': '/camera/image',
            'output': '/detections',
            'pipeline_stage': 'Perception',
            'n': 180,
            'mean_ms': 40.0,
            'stdev_ms': 3.5,
            'min_ms': 30.0,
            'p50_ms': 39.0,
            'p90_ms': 46.0,
            'p99_ms': 52.0,
            'max_ms': 58.0,
            'trigger_count': 180,
            'fps': 18.0,
            'jitter_mean_ms': 3.0,
            'jitter_max_ms': 8.0,
        },
        {
            'node': '/planner_node',
            'input': '/detections',
            'output': '/cmd_vel',
            'pipeline_stage': 'Planning',
            'n': 150,
            'mean_ms': 60.0,
            'stdev_ms': 5.0,
            'min_ms': 45.0,
            'p50_ms': 59.0,
            'p90_ms': 68.0,
            'p99_ms': 75.0,
            'max_ms': 82.0,
            'trigger_count': 150,
            'fps': 15.0,
            'jitter_mean_ms': 4.0,
            'jitter_max_ms': 12.0,
        },
    ],
    'metadata': {
        'name': 'test_session',
        'datetime': '2026-04-28T00:00:00Z',
        'hostname': 'testhost',
        'arch': 'x86_64',
        'os': 'Linux 6.8.0',
        'data_path': '/tmp/test_session',
        'framework_version': '0.1.6',
        'ros_distro': 'jazzy',
        'hardware': {
            'cpu_model': 'Test CPU',
            'cpu_cores': 8,
            'gpu_model': None,
            'total_ram_gb': 16.0,
        },
    },
}

# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _run(cmd, **kw):
    result = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if result.returncode != 0:
        print('STDOUT:', result.stdout[-2000:])
        print('STDERR:', result.stderr[-2000:])
        raise RuntimeError(
            f'Command failed (exit {result.returncode}): '
            f'{" ".join(str(c) for c in cmd)}'
        )
    return result


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


# ──────────────────────────────────────────────────────────────────────────────
#  Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_level2_csv_from_kpi_json():
    """analyze_pipeline_latency --csv-out produces correct rows and columns."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        kpi1_path  = tmp / 'kpi.json'
        kpi2_path  = tmp / 'kpi_level2.json'
        csv_path   = tmp / 'kpi_level2.csv'

        kpi1_path.write_text(json.dumps(LEVEL1_KPI, indent=2))

        _run([sys.executable, str(SRC / 'analyze_pipeline_latency.py'),
              '--kpi', str(kpi1_path),
              '--json-out', str(kpi2_path),
              '--csv-out', str(csv_path)])

        assert csv_path.exists(), 'CSV file not created'
        rows = _read_csv(csv_path)

        # Expect: 1 e2e row + 1 per stage
        stages_in_kpi = ['Sensor', 'Perception', 'Planning']  # those with pairs
        assert len(rows) == 1 + len(stages_in_kpi), \
            f'Expected {1 + len(stages_in_kpi)} rows, got {len(rows)}'

        e2e_rows   = [r for r in rows if r['type'] == 'e2e']
        stage_rows = [r for r in rows if r['type'] == 'stage']

        assert len(e2e_rows) == 1, 'Expected exactly 1 e2e row'
        assert len(stage_rows) == len(stages_in_kpi), \
            f'Expected {len(stages_in_kpi)} stage rows'

        # Verify e2e mean is sum of stage means (10 + 40 + 60 = 110)
        e2e_mean = float(e2e_rows[0]['mean_ms'])
        assert abs(e2e_mean - 110.0) < 0.1, f'e2e mean_ms expected 110.0, got {e2e_mean}'

        # Verify bottleneck is the slowest stage
        assert e2e_rows[0]['bottleneck_stage'] == 'Planning', \
            f'Bottleneck expected Planning, got {e2e_rows[0]["bottleneck_stage"]}'

        # Verify required columns are present
        required = {'type', 'session', 'stage', 'representative_node',
                    'mean_ms', 'p90_ms', 'n', 'throughput_hz'}
        missing = required - set(rows[0].keys())
        assert not missing, f'Missing CSV columns: {missing}'

        print(f'  ✓ Level 2 CSV: {len(rows)} rows, e2e mean={e2e_mean} ms, '
              f'bottleneck={e2e_rows[0]["bottleneck_stage"]}')


def test_level1_csv_flag_exists():
    """analyze_trigger_latency --help shows --csv-out."""
    result = _run([sys.executable, str(SRC / 'analyze_trigger_latency.py'), '--help'])
    assert '--csv-out' in result.stdout, '--csv-out not in --help output'
    print('  ✓ Level 1 --csv-out flag present in --help')


def test_level2_csv_flag_exists():
    """analyze_pipeline_latency --help shows --csv-out."""
    result = _run([sys.executable, str(SRC / 'analyze_pipeline_latency.py'), '--help'])
    assert '--csv-out' in result.stdout, '--csv-out not in --help output'
    print('  ✓ Level 2 --csv-out flag present in --help')


# ──────────────────────────────────────────────────────────────────────────────
#  Runner
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    tests = [
        test_level1_csv_flag_exists,
        test_level2_csv_flag_exists,
        test_level2_csv_from_kpi_json,
    ]
    failed = 0
    for t in tests:
        try:
            print(f'\n[RUN] {t.__name__}')
            t()
        except Exception as exc:
            print(f'  ✗ FAILED: {exc}')
            failed += 1

    print()
    if failed:
        print(f'RESULT: {failed}/{len(tests)} tests FAILED')
        sys.exit(1)
    else:
        print(f'RESULT: All {len(tests)} tests passed ✓')
