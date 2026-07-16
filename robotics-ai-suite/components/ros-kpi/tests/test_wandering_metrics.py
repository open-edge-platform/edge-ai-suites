#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Unit tests for wandering_metrics.py pure regex/logic functions.

Covers:
  _extract_goals(text)        — "Goals reached" value extraction
  _extract_elapsed(text)      — "Elapsed" value extraction
  _extract_rtf(text)          — RTF avg/min/max/throttled block extraction
  _extract_hz(text, topic)    — "average rate" value after a topic heading
  _verdict(throttled)         — throttle count → emoji verdict string
"""

import pytest

from wandering_metrics import (
    _extract_goals,
    _extract_elapsed,
    _extract_rtf,
    _extract_hz,
    _verdict,
    _goal_calc_latencies_ms,
    extract_goal_calc_latency,
    _goal_response_latencies_ms,
    extract_goal_response_latency,
)


# ─────────────────────────────────────────────────────────────────────────────
#  _extract_goals
# ─────────────────────────────────────────────────────────────────────────────

GOALS_CASES = [
    ('present',         'Goals reached   : 42',                 '42'),
    ('no_spaces',       'Goals reached:7',                      '7'),
    ('extra_spaces',    'Goals reached    :   99',              '99'),
    ('absent',          'Some other log line',                  'N/A'),
    ('multi_line',      'foo\nGoals reached: 15\nbar',          '15'),
    # Only last occurrence should not confuse — regex returns first match
    ('two_occurrences', 'Goals reached: 5\nGoals reached: 10', '5'),
]


@pytest.mark.parametrize('case_id,text,expected', GOALS_CASES,
                         ids=[c[0] for c in GOALS_CASES])
def test_extract_goals(case_id, text, expected):
    assert _extract_goals(text) == expected


# ─────────────────────────────────────────────────────────────────────────────
#  _extract_elapsed
# ─────────────────────────────────────────────────────────────────────────────

ELAPSED_CASES = [
    ('present',      'Elapsed   : 120s',              '120s'),
    ('no_spaces',    'Elapsed:5m30s',                 '5m30s'),
    ('absent',       'Nothing here',                  'N/A'),
    ('multi_line',   'a\nElapsed: 2m00s\nb',          '2m00s'),
]


@pytest.mark.parametrize('case_id,text,expected', ELAPSED_CASES,
                         ids=[c[0] for c in ELAPSED_CASES])
def test_extract_elapsed(case_id, text, expected):
    assert _extract_elapsed(text) == expected


# ─────────────────────────────────────────────────────────────────────────────
#  _extract_rtf
# ─────────────────────────────────────────────────────────────────────────────

_RTF_BLOCK = (
    'Simulation run complete.\n'
    'avg=0.971  min=0.015  max=1.006  samples=87\n'
    '3 throttled samples detected\n'
)

_RTF_BLOCK_MULTI = (
    'avg=0.500  min=0.100  max=0.800  samples=20\n'
    'avg=0.971  min=0.015  max=1.006  samples=87\n'   # last match wins
    '1 throttled sample\n'
)

RTF_CASES = [
    (
        'full_block',
        _RTF_BLOCK,
        {'avg': '0.971', 'min': '0.015', 'max': '1.006', 'throttled': '3'},
    ),
    (
        'no_throttle',
        'avg=0.990  min=0.800  max=1.010  samples=50\n',
        {'avg': '0.990', 'min': '0.800', 'max': '1.010', 'throttled': '0'},
    ),
    (
        'multiple_blocks_last_wins',
        _RTF_BLOCK_MULTI,
        {'avg': '0.971', 'min': '0.015', 'max': '1.006', 'throttled': '1'},
    ),
    (
        'no_rtf_block',
        'Goals reached: 10\nElapsed: 120s\n',
        {'avg': 'N/A', 'min': 'N/A', 'max': 'N/A', 'throttled': '0'},
    ),
    (
        'empty_text',
        '',
        {'avg': 'N/A', 'min': 'N/A', 'max': 'N/A', 'throttled': '0'},
    ),
]


@pytest.mark.parametrize('case_id,text,expected', RTF_CASES,
                         ids=[c[0] for c in RTF_CASES])
def test_extract_rtf(case_id, text, expected):
    result = _extract_rtf(text)
    assert result == expected


# ─────────────────────────────────────────────────────────────────────────────
#  _extract_hz
# ─────────────────────────────────────────────────────────────────────────────

_HZ_LOG = (
    '/camera/image_raw\n'
    '  average rate: 30.00\n'
    '  min: 0.030s  max: 0.035s\n'
    '/cmd_vel_nav\n'
    '  average rate: 10.00\n'
    '/plan\n'
    '  min: 0.100s\n'          # no average rate line
)

HZ_CASES = [
    ('camera_topic',    _HZ_LOG, '/camera/image_raw', '30.00'),
    ('cmd_vel_topic',   _HZ_LOG, '/cmd_vel_nav',      '10.00'),
    ('plan_no_rate',    _HZ_LOG, '/plan',              'N/A'),
    ('absent_topic',    _HZ_LOG, '/nonexistent',       'N/A'),
    ('empty_text',      '',      '/camera/image_raw',  'N/A'),
    # Multiple sections for same topic — last "average rate" line wins
    (
        'repeated_topic',
        '/camera/image_raw\n  average rate: 20.00\n'
        '/other\n  average rate: 5.00\n'
        '/camera/image_raw\n  average rate: 30.00\n',
        '/camera/image_raw',
        '30.00',
    ),
]


@pytest.mark.parametrize('case_id,text,topic,expected', HZ_CASES,
                         ids=[c[0] for c in HZ_CASES])
def test_extract_hz(case_id, text, topic, expected):
    assert _extract_hz(text, topic) == expected


# ─────────────────────────────────────────────────────────────────────────────
#  _verdict
# ─────────────────────────────────────────────────────────────────────────────

VERDICT_CASES = [
    ('no_throttle',       '0',  '✅ none'),
    ('one_sample',        '1',  '⚠ 1 sample(s)'),
    ('three_samples',     '3',  '⚠ 3 sample(s)'),
    ('large_count',      '99',  '⚠ 99 sample(s)'),
]


@pytest.mark.parametrize('case_id,throttled,expected', VERDICT_CASES,
                         ids=[c[0] for c in VERDICT_CASES])
def test_verdict(case_id, throttled, expected):
    assert _verdict(throttled) == expected


# ─────────────────────────────────────────────────────────────────────────────
#  _goal_calc_latencies_ms / extract_goal_calc_latency
# ─────────────────────────────────────────────────────────────────────────────

# Synthetic log matching the wandering_launch.log format:
#   First "Sending" has no preceding "Result" → excluded
#   result@T=10.000 → send@T=10.100  → 100 ms
#   result@T=20.000 (abort) → send@T=20.050 → 50 ms
#   result@T=30.000 (final, no following send) → excluded
_WANDERING_LOG = (
    '[wandering-21] [INFO] [1000000.100000000] [wandering_mapper]: '
    'Sending target goal [1.0, 2.0, 0.0]\n'
    '[wandering-21] [INFO] [1000010.000000000] [wandering_mapper]: '
    'Result for goal abc123\n'
    '[wandering-21] [INFO] [1000010.100000000] [wandering_mapper]: '
    'Sending target goal [3.0, 4.0, 0.0]\n'
    '[wandering-21] [WARN] [1000020.000000000] [wandering_mapper]: '
    'Result for goal def456\n'
    '[wandering-21] [WARN] [1000020.000010000] [wandering_mapper]: '
    'Goal was aborted. Will add it to the blocked list\n'
    '[wandering-21] [INFO] [1000020.050000000] [wandering_mapper]: '
    'Sending target goal [5.0, 6.0, 0.0]\n'
    '[wandering-21] [INFO] [1000030.000000000] [wandering_mapper]: '
    'Result for goal ghi789\n'
)


def test_goal_calc_latencies_ms_basic():
    lats = _goal_calc_latencies_ms(_WANDERING_LOG)
    assert len(lats) == 2
    assert abs(lats[0] - 100.0) < 1e-3
    assert abs(lats[1] - 50.0) < 1e-3


def test_goal_calc_latencies_ms_empty():
    assert not _goal_calc_latencies_ms('')


def test_goal_calc_latencies_ms_no_result_before_send():
    # Only sends, no results → nothing paired
    log = (
        '[wandering-21] [INFO] [1000001.000000000] [wandering_mapper]: '
        'Sending target goal [1.0, 2.0, 0.0]\n'
    )
    assert not _goal_calc_latencies_ms(log)


def test_extract_goal_calc_latency_stats():
    result = extract_goal_calc_latency(_WANDERING_LOG)
    assert result is not None
    assert result['n'] == 2
    assert abs(result['mean_ms'] - 75.0) < 1e-3
    assert abs(result['p50_ms'] - 75.0) < 1e-3   # midpoint of [50, 100]
    assert abs(result['p90_ms'] - 95.0) < 1e-3   # 0.9*(100-50)+50
    assert abs(result['max_ms'] - 100.0) < 1e-3


def test_extract_goal_calc_latency_too_few_transitions():
    # Zero transitions → returns None
    log = (
        '[wandering-21] [INFO] [1000010.000000000] [wandering_mapper]: '
        'Result for goal abc123\n'
        # No following Sending target goal
    )
    assert extract_goal_calc_latency(log) is None


def test_extract_goal_calc_latency_single_transition():
    # One transition is enough to return data
    log = (
        '[wandering-21] [INFO] [1000010.000000000] [wandering_mapper]: '
        'Result for goal abc123\n'
        '[wandering-21] [INFO] [1000010.100000000] [wandering_mapper]: '
        'Sending target goal [3.0, 4.0, 0.0]\n'
    )
    result = extract_goal_calc_latency(log)
    assert result is not None
    assert result['n'] == 1
    assert abs(result['mean_ms'] - 100.0) < 1e-3
    assert abs(result['max_ms'] - 100.0) < 1e-3


def test_extract_goal_calc_latency_no_data():
    assert extract_goal_calc_latency('nothing relevant here') is None


# ─────────────────────────────────────────────────────────────────────────────
#  _goal_response_latencies_ms / extract_goal_response_latency
# ─────────────────────────────────────────────────────────────────────────────
#
# The function reads /cmd_vel timestamps from a rosbag via _load_bag_timestamps.
# We mock that function to avoid needing a real bag on disk.
#
# _WANDERING_LOG has three "Sending target goal" events at (seconds):
#   T1 = 1000000.100  →  T1_ns = 1_000_000_100_000_000
#   T2 = 1000010.100  →  T2_ns = 1_000_010_100_000_000
#   T3 = 1000020.050  →  T3_ns = 1_000_020_050_000_000
#
# Mock /cmd_vel timestamps (first after each goal):
#   T1_ns + 50  ms = 1_000_000_150_000_000  → 50 ms
#   T2_ns + 100 ms = 1_000_010_200_000_000  → 100 ms
#   T3_ns + 150 ms = 1_000_020_200_000_000  → 150 ms
#
# Expected stats: n=3, mean=100ms, p50=100ms, p90=140ms, max=150ms

_T1_NS = 1_000_000_100_000_000
_T2_NS = 1_000_010_100_000_000
_T3_NS = 1_000_020_050_000_000

_MOCK_CMD_VEL_NS = sorted([
    _T1_NS + 50_000_000,   # 50 ms after T1
    _T2_NS + 100_000_000,  # 100 ms after T2
    _T3_NS + 150_000_000,  # 150 ms after T3
])

# A cmd_vel timestamp that predates all goals (should never be matched)
_EARLY_CMD_VEL_NS = _T1_NS - 1_000_000_000


def _mock_load_timestamps(bag_dir, topics):
    """Fake _load_bag_timestamps returning preset /cmd_vel timestamps."""
    return {'/cmd_vel': _MOCK_CMD_VEL_NS}


def test_goal_response_latencies_ms_basic():
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr('analyze_bag_e2e._load_bag_timestamps', _mock_load_timestamps)
        lats = _goal_response_latencies_ms(_WANDERING_LOG, '/fake/bag')
    assert len(lats) == 3
    assert abs(lats[0] - 50.0) < 1e-3
    assert abs(lats[1] - 100.0) < 1e-3
    assert abs(lats[2] - 150.0) < 1e-3


def test_goal_response_latencies_ms_no_cmd_vel_in_bag():
    def _empty(bag_dir, topics):
        return {}

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr('analyze_bag_e2e._load_bag_timestamps', _empty)
        lats = _goal_response_latencies_ms(_WANDERING_LOG, '/fake/bag')
    assert not lats


def test_goal_response_latencies_ms_no_sends_in_log():
    log_without_sends = (
        '[wandering-21] [INFO] [1000010.000000000] [wandering_mapper]: '
        'Result for goal abc123\n'
    )
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr('analyze_bag_e2e._load_bag_timestamps', _mock_load_timestamps)
        lats = _goal_response_latencies_ms(log_without_sends, '/fake/bag')
    assert not lats


def test_goal_response_latencies_ms_bag_load_error():
    def _raise(bag_dir, topics):
        raise FileNotFoundError('no bag')

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr('analyze_bag_e2e._load_bag_timestamps', _raise)
        lats = _goal_response_latencies_ms(_WANDERING_LOG, '/fake/bag')
    assert not lats


def test_goal_response_latencies_ms_early_cmd_vel_excluded():
    """cmd_vel messages before any goal send should not be counted."""
    def _early(bag_dir, topics):
        return {'/cmd_vel': [_EARLY_CMD_VEL_NS]}

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr('analyze_bag_e2e._load_bag_timestamps', _early)
        lats = _goal_response_latencies_ms(_WANDERING_LOG, '/fake/bag')
    assert not lats


def test_extract_goal_response_latency_stats():
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr('analyze_bag_e2e._load_bag_timestamps', _mock_load_timestamps)
        result = extract_goal_response_latency(_WANDERING_LOG, '/fake/bag')
    assert result is not None
    assert result['n'] == 3
    assert abs(result['mean_ms'] - 100.0) < 1e-3
    assert abs(result['p50_ms'] - 100.0) < 1e-3
    assert abs(result['p90_ms'] - 140.0) < 1e-3
    assert abs(result['max_ms'] - 150.0) < 1e-3


def test_extract_goal_response_latency_no_data():
    def _empty(bag_dir, topics):
        return {}

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr('analyze_bag_e2e._load_bag_timestamps', _empty)
        result = extract_goal_response_latency(_WANDERING_LOG, '/fake/bag')
    assert result is None


if __name__ == '__main__':
    import pytest as _pytest
    import sys
    sys.exit(_pytest.main([__file__, '-v']))
