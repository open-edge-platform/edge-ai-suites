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

from fixtures import LEVEL1_KPI

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
#  Standalone runner (python3 tests/test_csv_export.py)
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import pytest as _pytest
    sys.exit(_pytest.main([__file__, '-v']))
