#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Unit tests for analyze_trigger_latency.py pure-logic functions.

Covers:
  _is_internal(topic)              — regex filter for ROS 2 bookkeeping topics
  find_trigger(out_ts, in_times)   — binary-search for most-recent prior timestamp
  build_performance_kpi            — Level 1 KPI construction, including wandering
                                     goal-calc latency integration and schema validation
"""

import tempfile
from pathlib import Path

import pytest

from analyze_trigger_latency import (
    _is_internal,
    build_performance_kpi,
    find_trigger,
    validate_kpi_json,
)


# ─────────────────────────────────────────────────────────────────────────────
#  _is_internal
# ─────────────────────────────────────────────────────────────────────────────

INTERNAL_CASES = [
    # (case_id, topic, expected_is_internal)

    # --- topics that SHOULD be filtered ---
    ('rosout',              '/rosout',                                  True),
    ('parameter_events',    '/parameter_events',                        True),
    ('describe_parameters', '/some_node/describe_parameters',           True),
    ('get_parameters',      '/some_node/get_parameters',                True),
    ('list_parameters',     '/some_node/list_parameters',               True),
    ('set_parameters',      '/some_node/set_parameters',                True),
    ('rcl_interfaces',      '/some_node/rcl_interfaces/something',      True),
    ('bond',                '/some_node/bond',                          True),
    ('action_feedback',     '/navigate//_action/feedback',              True),
    ('action_status',       '/navigate//_action/status',                True),
    ('transition_event',    '/lifecycle_node/transition_event',         True),
    ('tf_static',           '/tf_static',                               True),
    ('clock',               '/clock',                                   True),

    # --- topics that SHOULD pass through ---
    ('camera_raw',          '/camera/image_raw',                        False),
    ('cmd_vel',             '/cmd_vel',                                 False),
    ('scan',                '/scan',                                    False),
    ('map',                 '/map',                                     False),
    ('plan',                '/plan',                                    False),
    ('detections',          '/detections',                              False),
    ('tf',                  '/tf',                                      False),
    ('odom',                '/odom',                                    False),
]


@pytest.mark.parametrize('case_id,topic,expected', INTERNAL_CASES,
                         ids=[c[0] for c in INTERNAL_CASES])
def test_is_internal(case_id, topic, expected):
    assert _is_internal(topic) == expected


# ─────────────────────────────────────────────────────────────────────────────
#  find_trigger
# ─────────────────────────────────────────────────────────────────────────────

FIND_TRIGGER_CASES = [
    # (case_id, out_ts, in_times, expected_trigger)

    # Normal: picks largest in_time <= out_ts
    ('normal_mid',         1.5,  [1.0, 1.2, 1.8],   1.2),
    # Exact match on boundary
    ('exact_match',        1.2,  [1.0, 1.2, 1.8],   1.2),
    # out_ts before all inputs → None
    ('before_all',         0.5,  [1.0, 1.2, 1.8],   None),
    # Empty list → None
    ('empty_list',         1.0,  [],                  None),
    # out_ts after all inputs → last element
    ('after_all',          5.0,  [1.0, 2.0, 3.0],   3.0),
    # Single-element list, out_ts matches
    ('single_hit',         2.0,  [2.0],               2.0),
    # Single-element list, out_ts before it
    ('single_miss',        1.9,  [2.0],               None),
    # out_ts exactly equals first element in a multi-element list
    ('exact_first',        1.0,  [1.0, 2.0, 3.0],   1.0),
    # Dense timestamps — picks the immediately preceding one
    ('dense',              1.05, [1.0, 1.1, 1.2],   1.0),
]


@pytest.mark.parametrize('case_id,out_ts,in_times,expected', FIND_TRIGGER_CASES,
                         ids=[c[0] for c in FIND_TRIGGER_CASES])
def test_find_trigger(case_id, out_ts, in_times, expected):
    result = find_trigger(out_ts, in_times)
    assert result == expected


# ─────────────────────────────────────────────────────────────────────────────
#  build_performance_kpi — wandering goal-calc latency integration
# ─────────────────────────────────────────────────────────────────────────────

# Minimal single-pair result that satisfies build_performance_kpi's key accesses
_MINIMAL_RESULT = {
    'node':          'controller_server',
    'input':         '/cmd_vel',
    'output':        '/odom',
    'n':             50,
    'mean_ms':       20.0,
    'stdev_ms':      2.0,
    'min_ms':        15.0,
    'p50_ms':        20.0,
    'p90_ms':        25.0,
    'p99_ms':        30.0,
    'max_ms':        35.0,
    'trigger_count': 50,
    'fps':           10.0,
}

# Synthetic wandering log content (same pattern as test_wandering_metrics.py)
_WANDERING_LOG = (
    '[wandering-21] [INFO] [1000010.000000000] [wandering_mapper]: '
    'Result for goal abc123\n'
    '[wandering-21] [INFO] [1000010.100000000] [wandering_mapper]: '
    'Sending target goal [3.0, 4.0, 0.0]\n'
    '[wandering-21] [WARN] [1000020.000000000] [wandering_mapper]: '
    'Result for goal def456\n'
    '[wandering-21] [INFO] [1000020.050000000] [wandering_mapper]: '
    'Sending target goal [5.0, 6.0, 0.0]\n'
    '[wandering-21] [INFO] [1000030.000000000] [wandering_mapper]: '
    'Result for goal ghi789\n'
)


def test_build_performance_kpi_includes_wandering_gcl():
    """KPI payload contains wandering.goal_calc_latency_ms when wandering_launch.log exists."""
    with tempfile.TemporaryDirectory() as tmp:
        session_dir = Path(tmp) / '20260101_120000'
        session_dir.mkdir()
        (session_dir / 'wandering_launch.log').write_text(_WANDERING_LOG)

        payload = build_performance_kpi([_MINIMAL_RESULT], session_dir, {})

        assert 'wandering' in payload, 'wandering key missing from payload'
        gcl = payload['wandering'].get('goal_calc_latency_ms')
        assert gcl is not None, 'goal_calc_latency_ms missing from wandering section'
        assert gcl['n'] == 2
        assert abs(gcl['mean_ms'] - 75.0) < 1e-3
        assert abs(gcl['max_ms'] - 100.0) < 1e-3


def test_build_performance_kpi_no_wandering_log():
    """KPI payload has no wandering key when wandering_launch.log is absent."""
    with tempfile.TemporaryDirectory() as tmp:
        session_dir = Path(tmp) / '20260101_120000'
        session_dir.mkdir()

        payload = build_performance_kpi([_MINIMAL_RESULT], session_dir, {})

        assert 'wandering' not in payload


def test_build_performance_kpi_with_wandering_schema_validates():
    """Payload including wandering goal-calc latency passes Level 1 KPI schema validation."""
    with tempfile.TemporaryDirectory() as tmp:
        session_dir = Path(tmp) / '20260101_120000'
        session_dir.mkdir()
        (session_dir / 'wandering_launch.log').write_text(_WANDERING_LOG)

        payload = build_performance_kpi([_MINIMAL_RESULT], session_dir, {})

        errors = validate_kpi_json(payload)
        assert errors == [], f'Schema validation errors: {errors}'


def test_build_performance_kpi_without_wandering_schema_validates():
    """Payload without wandering data also passes Level 1 KPI schema validation."""
    with tempfile.TemporaryDirectory() as tmp:
        session_dir = Path(tmp) / '20260101_120000'
        session_dir.mkdir()

        payload = build_performance_kpi([_MINIMAL_RESULT], session_dir, {})

        errors = validate_kpi_json(payload)
        assert errors == [], f'Schema validation errors: {errors}'


# ─────────────────────────────────────────────────────────────────────────────
#  build_performance_kpi — wandering goal-response latency integration
# ─────────────────────────────────────────────────────────────────────────────

# Mock /cmd_vel timestamps: one per goal-send in _WANDERING_LOG.
# Sends are at T=1000010.100 and T=1000020.050 (seconds).
_T2_NS = 1_000_010_100_000_000
_T3_NS = 1_000_020_050_000_000

_MOCK_CMD_VEL_NS = sorted([
    _T2_NS + 60_000_000,   # 60 ms after second send
    _T3_NS + 40_000_000,   # 40 ms after third send
])


def _mock_load_bag_timestamps(bag_dir, topics):
    return {'/cmd_vel': _MOCK_CMD_VEL_NS}


def test_build_performance_kpi_includes_wandering_grl(monkeypatch):
    """KPI payload contains wandering.goal_response_latency_ms when log + bag are present."""
    monkeypatch.setattr('analyze_bag_e2e._load_bag_timestamps', _mock_load_bag_timestamps)

    with tempfile.TemporaryDirectory() as tmp:
        session_dir = Path(tmp) / '20260101_120000'
        session_dir.mkdir()
        (session_dir / 'wandering_launch.log').write_text(_WANDERING_LOG)
        (session_dir / 'bag').mkdir()   # bag dir must exist for the check to proceed

        payload = build_performance_kpi([_MINIMAL_RESULT], session_dir, {})

    assert 'wandering' in payload
    grl = payload['wandering'].get('goal_response_latency_ms')
    assert grl is not None, 'goal_response_latency_ms missing from wandering section'
    assert grl['n'] == 2
    assert abs(grl['mean_ms'] - 50.0) < 1e-3   # mean of 60 and 40
    assert abs(grl['max_ms'] - 60.0) < 1e-3


def test_build_performance_kpi_grl_absent_without_bag(monkeypatch):
    """goal_response_latency_ms is absent when the bag directory does not exist."""
    monkeypatch.setattr('analyze_bag_e2e._load_bag_timestamps', _mock_load_bag_timestamps)

    with tempfile.TemporaryDirectory() as tmp:
        session_dir = Path(tmp) / '20260101_120000'
        session_dir.mkdir()
        (session_dir / 'wandering_launch.log').write_text(_WANDERING_LOG)
        # No bag/ directory created

        payload = build_performance_kpi([_MINIMAL_RESULT], session_dir, {})

    wandering = payload.get('wandering', {})
    assert 'goal_response_latency_ms' not in wandering


def test_build_performance_kpi_with_grl_schema_validates(monkeypatch):
    """Payload including goal_response_latency_ms passes Level 1 KPI schema validation."""
    monkeypatch.setattr('analyze_bag_e2e._load_bag_timestamps', _mock_load_bag_timestamps)

    with tempfile.TemporaryDirectory() as tmp:
        session_dir = Path(tmp) / '20260101_120000'
        session_dir.mkdir()
        (session_dir / 'wandering_launch.log').write_text(_WANDERING_LOG)
        (session_dir / 'bag').mkdir()

        payload = build_performance_kpi([_MINIMAL_RESULT], session_dir, {})

    errors = validate_kpi_json(payload)
    assert errors == [], f'Schema validation errors: {errors}'


if __name__ == '__main__':
    import pytest as _pytest
    import sys
    sys.exit(_pytest.main([__file__, '-v']))
