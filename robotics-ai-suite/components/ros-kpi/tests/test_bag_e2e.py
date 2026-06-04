#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Unit and integration tests for src/analyze_bag_e2e.py.

Pure-Python unit tests run in CI without ROS.
The integration test (derive_traced against the reference .mcap bag) is guarded
with pytest.importorskip('rosbag2_py') and will be skipped when ROS is not sourced.

Run:
    uv run pytest tests/test_bag_e2e.py -v
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))

from analyze_bag_e2e import (  # noqa: E402
    _correlate_e2e,
    _latency_stats,
    _pick_entry_exit_topics,
)

# ──────────────────────────────────────────────────────────────────────────────
#  _correlate_e2e
# ──────────────────────────────────────────────────────────────────────────────


class TestCorrelateE2e:
    """Unit tests for the timestamp correlation function."""

    def test_perfect_match(self):
        """Every entry has a corresponding exit exactly 100 ms later."""
        entry = [0, 100_000_000, 200_000_000]   # 0, 100 ms, 200 ms in ns
        exit_ = [100_000_000, 200_000_000, 300_000_000]
        result = _correlate_e2e(entry, exit_, tol_ns=500_000_000)
        assert result['drop_count'] == 0
        assert result['n_entry'] == 3
        assert len(result['latencies_ms']) == 3
        assert all(abs(lat - 100.0) < 0.001 for lat in result['latencies_ms'])

    def test_all_dropped_exit_too_late(self):
        """Exit timestamps are all 1 s after entry — beyond 500 ms tolerance."""
        entry = [0, 100_000_000, 200_000_000]
        exit_ = [1_000_000_000, 1_100_000_000, 1_200_000_000]
        result = _correlate_e2e(entry, exit_, tol_ns=500_000_000)
        assert result['drop_count'] == 3
        assert not result['latencies_ms']

    def test_partial_drop(self):
        """Two matched, one dropped (no exit within window)."""
        entry = [0, 100_000_000, 10_000_000_000]   # third entry is 10 s in
        exit_ = [100_000_000, 200_000_000]           # only covers first two
        result = _correlate_e2e(entry, exit_, tol_ns=500_000_000)
        assert result['drop_count'] == 1
        assert len(result['latencies_ms']) == 2

    def test_empty_entry(self):
        """Empty entry list → no matches, no drops."""
        result = _correlate_e2e([], [100_000_000], tol_ns=500_000_000)
        assert result['drop_count'] == 0
        assert not result['latencies_ms']
        assert result['n_entry'] == 0

    def test_empty_exit(self):
        """Empty exit list → all entries dropped."""
        entry = [0, 100_000_000]
        result = _correlate_e2e(entry, [], tol_ns=500_000_000)
        assert result['drop_count'] == 2
        assert not result['latencies_ms']

    def test_custom_tolerance(self):
        """Custom 1 s tolerance allows a match that 500 ms would miss."""
        entry = [0]
        exit_ = [800_000_000]   # 800 ms delay
        result_tight = _correlate_e2e(entry, exit_, tol_ns=500_000_000)
        result_wide  = _correlate_e2e(entry, exit_, tol_ns=1_000_000_000)
        assert result_tight['drop_count'] == 1
        assert result_wide['drop_count'] == 0
        assert abs(result_wide['latencies_ms'][0] - 800.0) < 0.001

    def test_n_exit_counted(self):
        """n_exit reflects the number of exit timestamps supplied."""
        entry = [0]
        exit_ = [50_000_000, 60_000_000, 70_000_000]
        result = _correlate_e2e(entry, exit_, tol_ns=500_000_000)
        assert result['n_exit'] == 3


# ──────────────────────────────────────────────────────────────────────────────
#  _latency_stats
# ──────────────────────────────────────────────────────────────────────────────

class TestLatencyStats:
    """Unit tests for percentile statistics helper."""

    def test_empty_returns_nones(self):
        stats = _latency_stats([])
        assert stats == {'mean': None, 'p50': None, 'p90': None, 'p99': None, 'max': None}

    def test_single_value(self):
        stats = _latency_stats([42.0])
        assert stats['mean'] == 42.0
        assert stats['p50'] == 42.0
        assert stats['p90'] == 42.0
        assert stats['p99'] == 42.0
        assert stats['max'] == 42.0

    def test_known_distribution(self):
        """100 evenly-spaced values 1..100 ms."""
        vals = [float(i) for i in range(1, 101)]
        stats = _latency_stats(vals)
        assert abs(stats['mean'] - 50.5) < 0.1
        assert abs(stats['p50'] - 50.5) < 1.0
        assert abs(stats['p90'] - 90.1) < 1.0
        assert stats['max'] == 100.0

    def test_rounding(self):
        """Values are rounded to 3 decimal places."""
        stats = _latency_stats([1.0 / 3.0])
        assert stats['mean'] == round(1.0 / 3.0, 3)


# ──────────────────────────────────────────────────────────────────────────────
#  _pick_entry_exit_topics
# ──────────────────────────────────────────────────────────────────────────────

class TestPickEntryExitTopics:
    """Unit tests for pipeline entry/exit topic selection."""

    def _make_kpi1(self, sensor_nodes: dict, control_nodes: dict) -> dict:
        per_node = {}
        per_node.update({
            n: {'pipeline_stage': 'Sensor', 'throughput_hz': v[0],
                'primary_input': v[1], 'primary_output': v[2]}
            for n, v in sensor_nodes.items()
        })
        per_node.update({
            n: {'pipeline_stage': 'Control', 'throughput_hz': v[0],
                'primary_input': v[1], 'primary_output': v[2]}
            for n, v in control_nodes.items()
        })
        return {'per_node': per_node}

    def test_picks_highest_throughput_sensor(self):
        kpi1 = self._make_kpi1(
            sensor_nodes={
                '/slow_sensor': (1.0,  '/raw_slow',  '/out_slow'),
                '/fast_sensor': (30.0, '/joint_states', '/tf'),
            },
            control_nodes={
                '/controller': (20.0, '/odom', '/cmd_vel'),
            },
        )
        entry, exit_ = _pick_entry_exit_topics(kpi1)
        assert entry == '/joint_states'
        assert exit_  == '/cmd_vel'

    def test_no_sensor_raises(self):
        kpi1 = {'per_node': {
            '/controller': {'pipeline_stage': 'Control', 'throughput_hz': 10.0,
                            'primary_input': '/odom', 'primary_output': '/cmd_vel'},
        }}
        with pytest.raises(ValueError, match='No Sensor-stage nodes'):
            _pick_entry_exit_topics(kpi1)

    def test_no_control_raises(self):
        kpi1 = {'per_node': {
            '/sensor': {'pipeline_stage': 'Sensor', 'throughput_hz': 10.0,
                        'primary_input': '/scan', 'primary_output': '/tf'},
        }}
        with pytest.raises(ValueError, match='No Control-stage nodes'):
            _pick_entry_exit_topics(kpi1)

    def test_empty_per_node_raises(self):
        with pytest.raises(ValueError, match='no per_node'):
            _pick_entry_exit_topics({})

    def test_reference_kpi_json(self):
        """Smoke test against the fixture kpi.json — must not raise."""
        kpi1_path = ROOT / 'monitoring_sessions' / 'wandering' / '20260430_145545' / 'kpi.json'
        if not kpi1_path.exists():
            pytest.skip('Reference kpi.json not present')
        with open(kpi1_path) as f:
            kpi1 = json.load(f)
        entry, exit_ = _pick_entry_exit_topics(kpi1)
        assert entry.startswith('/')
        assert exit_.startswith('/')


# ──────────────────────────────────────────────────────────────────────────────
#  Integration: derive_traced against reference .mcap bag
# ──────────────────────────────────────────────────────────────────────────────

class TestDeriveTraced:
    """Integration tests — skipped when rosbag2_py is not available."""

    @pytest.fixture(autouse=True)
    def _require_rosbag2(self):
        pytest.importorskip('rosbag2_py')

    @pytest.fixture
    def reference_session(self):
        session = ROOT / 'monitoring_sessions' / 'wandering' / '20260430_145545'
        if not session.exists():
            pytest.skip('Reference session not present')
        return session

    def test_derive_traced_returns_valid_schema(self, reference_session):
        """derive_traced output must validate against kpi_level2_v1.json."""
        from analyze_bag_e2e import derive_traced  # noqa: PLC0415
        from analyze_pipeline_latency import validate_level2_json  # noqa: PLC0415

        bag_dir   = reference_session / 'bag'
        kpi1_path = reference_session / 'kpi.json'
        kpi2 = derive_traced(bag_dir, kpi1_path)

        errors = validate_level2_json(kpi2)
        assert errors == [], 'Schema validation failed:\n' + '\n'.join(errors)

    def test_derive_traced_method_is_traced(self, reference_session):
        """method field must be 'traced', not 'chained'."""
        from analyze_bag_e2e import derive_traced  # noqa: PLC0415

        bag_dir   = reference_session / 'bag'
        kpi1_path = reference_session / 'kpi.json'
        kpi2 = derive_traced(bag_dir, kpi1_path)

        assert kpi2['e2e_latency_ms']['method'] == 'traced'

    def test_derive_traced_bag_source_present(self, reference_session):
        """bag_source field must be set to the resolved bag directory path."""
        from analyze_bag_e2e import derive_traced  # noqa: PLC0415

        bag_dir   = reference_session / 'bag'
        kpi1_path = reference_session / 'kpi.json'
        kpi2 = derive_traced(bag_dir, kpi1_path)

        assert 'bag_source' in kpi2
        assert kpi2['bag_source'] == str(bag_dir.resolve())

    def test_derive_traced_plausible_latency(self, reference_session):
        """e2e mean latency should be positive and below 60 seconds."""
        from analyze_bag_e2e import derive_traced  # noqa: PLC0415

        bag_dir   = reference_session / 'bag'
        kpi1_path = reference_session / 'kpi.json'
        kpi2 = derive_traced(bag_dir, kpi1_path)

        e2e = kpi2['e2e_latency_ms']
        n = e2e.get('n', 0)
        if n == 0:
            pytest.skip('No matched pairs in reference bag — topic mismatch likely')
        assert e2e['mean'] is not None
        assert 0 < e2e['mean'] < 60_000, f"Suspicious mean latency: {e2e['mean']} ms"

    def test_derive_traced_drop_rate_range(self, reference_session):
        """drop_rate_pct must be in [0, 100]."""
        from analyze_bag_e2e import derive_traced  # noqa: PLC0415

        bag_dir   = reference_session / 'bag'
        kpi1_path = reference_session / 'kpi.json'
        kpi2 = derive_traced(bag_dir, kpi1_path)

        dr = kpi2.get('drop_rate_pct')
        if dr is not None:
            assert 0.0 <= dr <= 100.0, f'drop_rate_pct out of range: {dr}'
