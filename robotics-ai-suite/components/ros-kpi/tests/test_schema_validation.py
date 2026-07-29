#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
Table-driven schema validation tests for Level 1 and Level 2 KPI JSON output.

Each test case is a row in LEVEL1_CASES / LEVEL2_CASES describing:
  - id          : short label printed in results
  - mutate      : callable that deep-copies the base fixture and modifies it
                  (None = use fixture as-is)
  - expect_valid: True  → validation must return zero errors
                  False → validation must return one or more errors

No ROS install required — validation functions are called directly.

Run:
    python3 tests/test_schema_validation.py
"""

import copy

import pytest

from analyze_trigger_latency import validate_kpi_json
from analyze_pipeline_latency import validate_level2_json
from fixtures import LEVEL1_KPI, LEVEL2_KPI

# ──────────────────────────────────────────────────────────────────────────────
#  Test tables
#
#  Each row: (id, mutate_fn, expect_valid)
#    id           — label printed in results
#    mutate_fn    — callable(dict) -> dict, applied to a deep copy of the base
#                   fixture; None means use the base fixture unchanged
#    expect_valid — True: validation must return zero errors
#                   False: validation must return one or more errors
# ──────────────────────────────────────────────────────────────────────────────

def _del(keys):
    """Return a mutator that deletes a nested key path (list of keys)."""
    def _mutate(d):
        target = d
        for k in keys[:-1]:
            target = target[k]
        del target[keys[-1]]
        return d
    return _mutate


def _set(keys, value):
    """Return a mutator that sets a nested key path to value."""
    def _mutate(d):
        target = d
        for k in keys[:-1]:
            target = target[k]
        target[keys[-1]] = value
        return d
    return _mutate


LEVEL1_CASES = [
    # id                                  mutate_fn                                   expect_valid
    ('valid payload',                     None,                                        True),
    ('missing schema_version',            _del(['schema_version']),                    False),
    ('missing throughput_hz',             _del(['throughput_hz']),                     False),
    ('missing metadata.hardware',         _del(['metadata', 'hardware']),              False),
    ('wrong schema_version value',        _set(['schema_version'], 'level2_v1'),       False),
    ('null cpu_mean_pct (allowed)',        _set(['cpu_mean_pct'], None),               True),
    ('negative throughput_hz',            _set(['throughput_hz'], -1.0),              False),
]

LEVEL2_CASES = [
    # id                                  mutate_fn                                   expect_valid
    ('valid payload',                     None,                                        True),
    ('missing e2e_latency_ms',            _del(['e2e_latency_ms']),                   False),
    ('missing pipeline.stage_sequence',   _del(['pipeline', 'stage_sequence']),       False),
    ('missing metadata',                  _del(['metadata']),                          False),
    ('wrong schema_version value',        _set(['schema_version'], 'level1_v1'),       False),
    ('null cpu_mean_pct (allowed)',        _set(['cpu_mean_pct'], None),               True),
    ('invalid bottleneck_stage value',    _set(['bottleneck_stage'], 'InvalidStage'), False),
]

# ──────────────────────────────────────────────────────────────────────────────
#  pytest parametrize
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('case_id,mutate_fn,expect_valid', LEVEL1_CASES,
                         ids=[c[0] for c in LEVEL1_CASES])
def test_level1_schema(case_id, mutate_fn, expect_valid):
    payload = copy.deepcopy(LEVEL1_KPI)
    if mutate_fn is not None:
        payload = mutate_fn(payload)
    errors = validate_kpi_json(payload)
    is_valid = len(errors) == 0
    assert is_valid == expect_valid, (
        f'expect_valid={expect_valid} but got {len(errors)} error(s): {errors[:1]}'
    )


@pytest.mark.parametrize('case_id,mutate_fn,expect_valid', LEVEL2_CASES,
                         ids=[c[0] for c in LEVEL2_CASES])
def test_level2_schema(case_id, mutate_fn, expect_valid):
    payload = copy.deepcopy(LEVEL2_KPI)
    if mutate_fn is not None:
        payload = mutate_fn(payload)
    errors = validate_level2_json(payload)
    is_valid = len(errors) == 0
    assert is_valid == expect_valid, (
        f'expect_valid={expect_valid} but got {len(errors)} error(s): {errors[:1]}'
    )

