#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Unit tests for aggregate_kpi.py pure-logic functions.

Covers:
  _health(mean_ms)       — latency → emoji health indicator
  _consistency(cv_pct)   — coefficient of variation → consistency emoji
  _classify(node,in,out) — node name → pipeline stage label
  aggregate(per_pair, …) — cross-run statistics computation and filtering
"""

import pytest

from aggregate_kpi import _health, _consistency, _classify, aggregate, PIPELINE_ORDER


# ─────────────────────────────────────────────────────────────────────────────
#  _health
# ─────────────────────────────────────────────────────────────────────────────

HEALTH_CASES = [
    ('below_10ms',   9.9,  '✅'),
    ('at_10ms',     10.0,  '🟡'),   # boundary: < 10 is false at exactly 10
    ('below_50ms',  49.9,  '🟡'),
    ('at_50ms',     50.0,  '🟠'),   # boundary: < 50 is false at exactly 50
    ('below_200ms', 199.9, '🟠'),
    ('at_200ms',   200.0,  '🔴'),   # boundary: < 200 is false at exactly 200
    ('above_200ms', 500.0, '🔴'),
]


@pytest.mark.parametrize('case_id,mean_ms,expected', HEALTH_CASES,
                         ids=[c[0] for c in HEALTH_CASES])
def test_health(case_id, mean_ms, expected):
    assert _health(mean_ms) == expected


# ─────────────────────────────────────────────────────────────────────────────
#  _consistency
# ─────────────────────────────────────────────────────────────────────────────

CONSISTENCY_CASES = [
    ('very_consistent',  9.9,  '◆'),
    ('at_10_pct',       10.0,  '◇'),   # boundary: < 10 is false at exactly 10
    ('moderate',        24.9,  '◇'),
    ('at_25_pct',       25.0,  '△'),
    ('high_variance',   49.9,  '△'),
    ('at_50_pct',       50.0,  '✗'),
    ('unstable',        99.0,  '✗'),
]


@pytest.mark.parametrize('case_id,cv_pct,expected', CONSISTENCY_CASES,
                         ids=[c[0] for c in CONSISTENCY_CASES])
def test_consistency(case_id, cv_pct, expected):
    assert _consistency(cv_pct) == expected


# ─────────────────────────────────────────────────────────────────────────────
#  _classify
# ─────────────────────────────────────────────────────────────────────────────

CLASSIFY_CASES = [
    # (case_id, node, inp, out, expected_stage)
    ('sensor_bridge',         'ros_gz_bridge',          '/clock',       '/tf',          'Sensor'),
    ('sensor_state_pub',      'robot_state_publisher',  '/joint_states', '/tf',         'Sensor'),
    ('perception_rtabmap',    'rtabmap',                '/scan',        '/map',          'Perception'),
    ('perception_local_cm',   'local_costmap',          '/scan',        '/local_map',    'Perception'),
    ('perception_global_cm',  'global_costmap',         '/map',         '/global_map',   'Perception'),
    ('planning_bt_nav',       'bt_navigator',           '/goal',        '/cmd_vel',      'Planning'),
    ('planning_planner',      'planner_server',         '/goal',        '/plan',         'Planning'),
    ('planning_behavior',     'behavior_server',        '/goal',        '/cmd_vel',      'Planning'),
    ('planning_route',        'route_server',           '/goal',        '/route',        'Planning'),
    ('control_controller',    'controller_server',      '/plan',        '/cmd_vel',      'Control'),
    ('control_smoother',      'velocity_smoother',      '/cmd_vel_nav', '/cmd_vel',      'Control'),
    ('control_collision_mon', 'collision_monitor',      '/cmd_vel',     '/cmd_vel_safe', 'Control'),
    ('control_docking',       'docking_server',         '/dock_goal',   '/cmd_vel',      'Control'),
    ('other_unknown',         'my_custom_node',         '/in',          '/out',          'Other'),
    # namespaced node — only the last segment is matched
    ('namespaced_control',    '/ns/controller_server',  '/plan',        '/cmd_vel',      'Control'),
    ('namespaced_sensor',     '/robot/ros_gz_bridge',   '/clock',       '/tf',           'Sensor'),
]


@pytest.mark.parametrize('case_id,node,inp,out,expected', CLASSIFY_CASES,
                         ids=[c[0] for c in CLASSIFY_CASES])
def test_classify(case_id, node, inp, out, expected):
    assert _classify(node, inp, out) == expected


# ─────────────────────────────────────────────────────────────────────────────
#  aggregate()
# ─────────────────────────────────────────────────────────────────────────────

def _make_pair(node, inp, out, mean_ms, p90_ms, p50_ms, stdev_ms, n=100, fps=20.0):
    """Build a minimal pair dict matching the kpi.json 'pairs' structure."""
    return {
        'node':     node,
        'input':    inp,
        'output':   out,
        'mean_ms':  mean_ms,
        'p90_ms':   p90_ms,
        'p50_ms':   p50_ms,
        'stdev_ms': stdev_ms,
        'n':        n,
        'fps':      fps,
    }


class TestAggregate:
    """Tests for aggregate(per_pair, total_runs, min_runs, node_filter)."""

    def test_basic_statistics(self):
        """Three runs of one pair → correct cross-run mean, stdev, cv_pct."""
        key = ('controller_server', '/plan', '/cmd_vel')
        runs = [
            _make_pair(*key, mean_ms=40.0, p90_ms=60.0, p50_ms=38.0, stdev_ms=5.0),
            _make_pair(*key, mean_ms=50.0, p90_ms=75.0, p50_ms=48.0, stdev_ms=6.0),
            _make_pair(*key, mean_ms=60.0, p90_ms=90.0, p50_ms=58.0, stdev_ms=7.0),
        ]
        per_pair = {key: runs}

        results = aggregate(per_pair, total_runs=3, min_runs=3)

        assert len(results) == 1
        r = results[0]
        assert r['node']      == 'controller_server'
        assert r['runs_seen'] == 3
        assert r['total_runs'] == 3
        assert r['mean_ms']   == pytest.approx(50.0)
        assert r['mean_p90_ms'] == pytest.approx(75.0)
        assert r['worst_p90_ms'] == 90.0
        assert r['best_p90_ms']  == 60.0
        assert r['mean_fps']  == pytest.approx(20.0)
        # CV% = stdev(40,50,60) / mean(40,50,60) * 100
        import statistics as _st
        expected_cv = _st.stdev([40.0, 50.0, 60.0]) / 50.0 * 100
        assert r['cv_pct'] == pytest.approx(expected_cv)

    def test_min_runs_filters_out_pair(self):
        """Pair with fewer runs than min_runs threshold is excluded."""
        key = ('rtabmap', '/scan', '/map')
        runs = [
            _make_pair(*key, mean_ms=30.0, p90_ms=50.0, p50_ms=28.0, stdev_ms=3.0),
            _make_pair(*key, mean_ms=35.0, p90_ms=55.0, p50_ms=33.0, stdev_ms=4.0),
        ]
        per_pair = {key: runs}

        results = aggregate(per_pair, total_runs=5, min_runs=3)

        assert results == []

    def test_min_runs_includes_pair_at_threshold(self):
        """Pair with exactly min_runs occurrences is included."""
        key = ('rtabmap', '/scan', '/map')
        runs = [
            _make_pair(*key, mean_ms=30.0, p90_ms=50.0, p50_ms=28.0, stdev_ms=3.0),
            _make_pair(*key, mean_ms=35.0, p90_ms=55.0, p50_ms=33.0, stdev_ms=4.0),
            _make_pair(*key, mean_ms=32.0, p90_ms=52.0, p50_ms=30.0, stdev_ms=3.5),
        ]
        per_pair = {key: runs}

        results = aggregate(per_pair, total_runs=5, min_runs=3)

        assert len(results) == 1

    def test_sort_by_pipeline_stage_then_worst_p90(self):
        """Results are sorted by pipeline stage order, then worst_p90 descending."""
        sensor_key     = ('ros_gz_bridge',    '/clock',  '/tf')
        planning_key   = ('bt_navigator',     '/goal',   '/cmd_vel')
        control_key_hi = ('controller_server','/plan',   '/cmd_vel')
        control_key_lo = ('velocity_smoother','/cmd_vel_nav','/cmd_vel')

        def three_runs(key, mean, p90):
            return [_make_pair(*key, mean_ms=mean, p90_ms=p90, p50_ms=mean*0.9,
                               stdev_ms=1.0) for _ in range(3)]

        per_pair = {
            control_key_lo: three_runs(control_key_lo, 10.0, 20.0),   # worst_p90=20
            planning_key:   three_runs(planning_key,   40.0, 80.0),   # stage before Control
            control_key_hi: three_runs(control_key_hi, 20.0, 50.0),   # worst_p90=50
            sensor_key:     three_runs(sensor_key,     5.0,  10.0),   # stage=Sensor (first)
        }

        results = aggregate(per_pair, total_runs=3, min_runs=3)

        stages = [r['category'] for r in results]
        assert stages == sorted(stages, key=lambda s: PIPELINE_ORDER.index(s)
                                if s in PIPELINE_ORDER else len(PIPELINE_ORDER))

        # Within Control: higher worst_p90 comes first
        control_results = [r for r in results if r['category'] == 'Control']
        assert len(control_results) == 2
        assert control_results[0]['worst_p90_ms'] >= control_results[1]['worst_p90_ms']

    def test_node_filter(self):
        """node_filter keyword restricts output to matching node names."""
        key_a = ('controller_server', '/plan',   '/cmd_vel')
        key_b = ('rtabmap',           '/scan',   '/map')
        runs_a = [_make_pair(*key_a, mean_ms=30.0, p90_ms=50.0, p50_ms=28.0, stdev_ms=3.0)] * 3
        runs_b = [_make_pair(*key_b, mean_ms=20.0, p90_ms=40.0, p50_ms=18.0, stdev_ms=2.0)] * 3
        per_pair = {key_a: runs_a, key_b: runs_b}

        results = aggregate(per_pair, total_runs=3, min_runs=3, node_filter='rtabmap')

        assert len(results) == 1
        assert results[0]['node'] == 'rtabmap'

    def test_stage_classification_in_output(self):
        """aggregate() sets 'category' from _classify, not raw node name."""
        key = ('bt_navigator', '/goal', '/cmd_vel')
        runs = [_make_pair(*key, mean_ms=45.0, p90_ms=70.0, p50_ms=43.0, stdev_ms=5.0)] * 3
        per_pair = {key: runs}

        results = aggregate(per_pair, total_runs=3, min_runs=3)

        assert results[0]['category'] == 'Planning'

    def test_single_run_stdev_zero(self):
        """Single run → stdev_of_means = 0.0, cv_pct = 0.0 (no ZeroDivision)."""
        key = ('ros_gz_bridge', '/clock', '/tf')
        runs = [_make_pair(*key, mean_ms=5.0, p90_ms=8.0, p50_ms=4.5, stdev_ms=0.5)]
        per_pair = {key: runs}

        results = aggregate(per_pair, total_runs=1, min_runs=1)

        assert results[0]['stdev_runs'] == pytest.approx(0.0)
        assert results[0]['cv_pct']     == pytest.approx(0.0)


if __name__ == '__main__':
    import pytest as _pytest
    import sys
    sys.exit(_pytest.main([__file__, '-v']))
