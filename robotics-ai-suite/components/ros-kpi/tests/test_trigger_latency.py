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
"""

import pytest

from analyze_trigger_latency import _is_internal, find_trigger


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


if __name__ == '__main__':
    import pytest as _pytest
    import sys
    sys.exit(_pytest.main([__file__, '-v']))
