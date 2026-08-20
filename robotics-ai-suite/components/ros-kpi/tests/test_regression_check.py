#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Unit tests for src/compare_kpi.py regression detection logic.

Run:
    python3 tests/test_regression_check.py
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT    = Path(__file__).resolve().parent.parent
SRC     = ROOT / 'src'
SCRIPT  = SRC / 'compare_kpi.py'
BASEDIR = ROOT / 'tests' / 'fixtures' / 'baseline'

# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _run(cmd, **kw):
    """Run a command and return the CompletedProcess (don't raise on non-zero)."""
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def _write(tmp: Path, data: dict, name: str) -> Path:
    """Write a dict as JSON into tmp dir and return the path."""
    p = tmp / name
    p.write_text(json.dumps(data, indent=2))
    return p


# ──────────────────────────────────────────────────────────────────────────────
#  Tests
# ──────────────────────────────────────────────────────────────────────────────

_PASS = 0
_FAIL_REGRESSION = 1


def test_regression_pass_level1():
    """Identical Level 1 baseline and current → exit 0, all PASS."""
    baseline = BASEDIR / 'kpi.json'
    result = _run([sys.executable, str(SCRIPT), '--baseline', str(baseline),
                   '--current', str(baseline)])
    assert result.returncode == _PASS, (
        f'Expected exit 0, got {result.returncode}\n{result.stdout}\n{result.stderr}'
    )
    assert 'FAIL' not in result.stdout, f'Unexpected FAIL in output:\n{result.stdout}'
    print('  ✓ Level 1: identical baseline/current → all PASS')


def test_regression_pass_level2():
    """Identical Level 2 baseline and current → exit 0, all PASS."""
    baseline = BASEDIR / 'kpi_level2.json'
    result = _run([sys.executable, str(SCRIPT), '--baseline', str(baseline),
                   '--current', str(baseline)])
    assert result.returncode == _PASS, (
        f'Expected exit 0, got {result.returncode}\n{result.stdout}\n{result.stderr}'
    )
    assert 'FAIL' not in result.stdout, f'Unexpected FAIL in output:\n{result.stdout}'
    print('  ✓ Level 2: identical baseline/current → all PASS')


def test_regression_fail_latency():
    """e2e mean latency 20% higher → exit 1, FAIL in output."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        with open(BASEDIR / 'kpi_level2.json') as f:
            current = json.load(f)
        current['e2e_latency_ms']['mean'] = 132.0   # 110 * 1.20 = 132
        curr_path = _write(tmp, current, 'kpi_level2.json')

        result = _run([sys.executable, str(SCRIPT),
                       '--baseline', str(BASEDIR / 'kpi_level2.json'),
                       '--current', str(curr_path),
                       '--threshold', '5.0'])
        assert result.returncode == _FAIL_REGRESSION, (
            f'Expected exit 1, got {result.returncode}\n{result.stdout}\n{result.stderr}'
        )
        assert 'FAIL' in result.stdout, f'Expected FAIL row in output:\n{result.stdout}'
    print('  ✓ Level 2: e2e_mean +20% → FAIL (threshold=5%)')


def test_regression_fail_throughput():
    """Throughput 20% lower → exit 1, FAIL in output."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        with open(BASEDIR / 'kpi_level2.json') as f:
            current = json.load(f)
        current['throughput_hz'] = 12.0   # 15 * 0.80 = 12
        curr_path = _write(tmp, current, 'kpi_level2.json')

        result = _run([sys.executable, str(SCRIPT),
                       '--baseline', str(BASEDIR / 'kpi_level2.json'),
                       '--current', str(curr_path),
                       '--threshold', '5.0'])
        assert result.returncode == _FAIL_REGRESSION, (
            f'Expected exit 1, got {result.returncode}\n{result.stdout}\n{result.stderr}'
        )
        assert 'FAIL' in result.stdout, f'Expected FAIL row in output:\n{result.stdout}'
    print('  ✓ Level 2: throughput -20% → FAIL (threshold=5%)')


def test_regression_threshold_override():
    """e2e mean latency +10% but threshold=15 → exit 0 (within tolerance)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        with open(BASEDIR / 'kpi_level2.json') as f:
            current = json.load(f)
        current['e2e_latency_ms']['mean'] = 121.0   # 110 * 1.10 = 121
        curr_path = _write(tmp, current, 'kpi_level2.json')

        result = _run([sys.executable, str(SCRIPT),
                       '--baseline', str(BASEDIR / 'kpi_level2.json'),
                       '--current', str(curr_path),
                       '--threshold', '15.0'])
        assert result.returncode == _PASS, (
            f'Expected exit 0 (within 15% threshold), got {result.returncode}\n'
            f'{result.stdout}\n{result.stderr}'
        )
        assert 'FAIL' not in result.stdout, \
            f'Unexpected FAIL in output at threshold=15%:\n{result.stdout}'
    print('  ✓ Level 2: e2e_mean +10% with threshold=15% → PASS')


def test_regression_fail_level1_latency():
    """Level 1 mean_latency_ms 20% higher → exit 1, FAIL in output."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        with open(BASEDIR / 'kpi.json') as f:
            current = json.load(f)
        current['mean_latency_ms'] = 60.0   # 50 * 1.20 = 60
        curr_path = _write(tmp, current, 'kpi.json')

        result = _run([sys.executable, str(SCRIPT),
                       '--baseline', str(BASEDIR / 'kpi.json'),
                       '--current', str(curr_path),
                       '--threshold', '5.0'])
        assert result.returncode == _FAIL_REGRESSION, (
            f'Expected exit 1, got {result.returncode}\n{result.stdout}\n{result.stderr}'
        )
        assert 'FAIL' in result.stdout, f'Expected FAIL row in output:\n{result.stdout}'
    print('  ✓ Level 1: mean_latency_ms +20% → FAIL (threshold=5%)')


def test_regression_fail_level1_throughput():
    """Level 1 throughput_hz 20% lower → exit 1, FAIL in output."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        with open(BASEDIR / 'kpi.json') as f:
            current = json.load(f)
        current['throughput_hz'] = 16.0   # 20 * 0.80 = 16
        curr_path = _write(tmp, current, 'kpi.json')

        result = _run([sys.executable, str(SCRIPT),
                       '--baseline', str(BASEDIR / 'kpi.json'),
                       '--current', str(curr_path),
                       '--threshold', '5.0'])
        assert result.returncode == _FAIL_REGRESSION, (
            f'Expected exit 1, got {result.returncode}\n{result.stdout}\n{result.stderr}'
        )
        assert 'FAIL' in result.stdout, f'Expected FAIL row in output:\n{result.stdout}'
    print('  ✓ Level 1: throughput_hz -20% → FAIL (threshold=5%)')


def test_regression_report_json():
    """--report flag writes a valid JSON file with expected fields."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        with open(BASEDIR / 'kpi_level2.json') as f:
            current = json.load(f)
        current['e2e_latency_ms']['mean'] = 132.0   # 20% regression
        curr_path = _write(tmp, current, 'kpi_level2.json')
        report_path = tmp / 'report.json'

        _run([sys.executable, str(SCRIPT),
              '--baseline', str(BASEDIR / 'kpi_level2.json'),
              '--current', str(curr_path),
              '--report', str(report_path)])

        assert report_path.exists(), 'Report JSON was not created'
        with open(report_path) as f:
            report = json.load(f)

        assert 'passed' in report
        assert 'regressions' in report
        assert 'threshold' in report
        assert 'results' in report
        assert report['passed'] is False, 'Expected passed=False for 20% regression'
        assert len(report['regressions']) >= 1
    print('  ✓ --report flag writes valid JSON with correct fields')


# ──────────────────────────────────────────────────────────────────────────────
#  Standalone runner (python3 tests/test_regression_check.py)
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import pytest as _pytest
    sys.exit(_pytest.main([__file__, '-v']))
