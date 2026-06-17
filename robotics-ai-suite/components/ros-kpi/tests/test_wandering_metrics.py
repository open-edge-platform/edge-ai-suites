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


if __name__ == '__main__':
    import pytest as _pytest
    import sys
    sys.exit(_pytest.main([__file__, '-v']))
