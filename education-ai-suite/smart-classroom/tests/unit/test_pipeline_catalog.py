# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Invariants of utils/pipeline_catalog.py: that both graphs point at things
that exist, that the derived stage order matches what is already written into
session rows on disk, and that config.yaml names the same features."""

import re
from pathlib import Path

import pytest

from utils.pipeline_catalog import (
    ALL_STAGES,
    CATALOG,
    FEATURE_IDS,
    FEATURE_STAGE,
    REQUIRED_BY,
    SETTLED_STAGE_STATUSES,
    STAGE_RUN_AFTER,
    STAGE_STATUSES,
    TERMINAL_SESSION_STATES,
    SESSION_STATES,
    topo_sort,
)

_ROOT = Path(__file__).resolve().parents[2]

# The order every existing sessions.db row was written with. ALL_STAGES is
# derived, so this is what stops the derivation reordering it.
_STAGE_ORDER = ("transcribe", "summarize", "mindmap", "va", "segmentation", "report")


def test_stage_order_is_unchanged():
    assert ALL_STAGES == _STAGE_ORDER


def test_every_dependency_is_a_known_feature():
    for spec in CATALOG:
        unknown = [dep for dep in spec.depends_on if dep not in FEATURE_IDS]
        assert not unknown, f"{spec.id} depends on unknown feature(s): {unknown}"


def test_every_run_after_is_a_known_stage():
    for stage, prereqs in STAGE_RUN_AFTER.items():
        unknown = [p for p in prereqs if p not in ALL_STAGES]
        assert not unknown, f"stage {stage} runs after unknown stage(s): {unknown}"


def test_feature_graph_is_acyclic():
    # topo_sort raises on a cycle; computing ALL_STAGES proves it for `run_after`.
    order = topo_sort(list(FEATURE_IDS), lambda fid: CATALOG[FEATURE_IDS.index(fid)].depends_on)
    assert set(order) == set(FEATURE_IDS)


def test_stages_are_unique_per_feature():
    stages = [spec.stage for spec in CATALOG if spec.stage]
    assert len(stages) == len(set(stages)), "two features claim the same stage"


def test_a_stage_needs_an_input_and_an_input_needs_a_stage():
    """sessionStages.ts pairs the two to decide what a session declares."""
    for spec in CATALOG:
        assert bool(spec.stage) == bool(spec.input), (
            f"{spec.id} has stage={spec.stage!r} but input={spec.input!r}"
        )


def test_required_by_is_the_reverse_of_depends_on():
    for spec in CATALOG:
        for dep in spec.depends_on:
            assert spec.id in REQUIRED_BY[dep], (
                f"{spec.id} depends on {dep}, but REQUIRED_BY[{dep!r}] omits it"
            )


def test_required_by_is_transitive():
    # report -> topic_segmentation -> content_search. registry.cjs relies on it.
    assert "report" in REQUIRED_BY["content_search"]


def test_settled_and_terminal_are_subsets():
    assert set(SETTLED_STAGE_STATUSES) <= set(STAGE_STATUSES)
    assert set(TERMINAL_SESSION_STATES) <= set(SESSION_STATES)


def test_config_yaml_names_exactly_the_catalog_features():
    """feature_bootstrap drops any id config.yaml names that is not in here."""
    text = (_ROOT / "config.yaml").read_text(encoding="utf-8")
    block = re.search(r"^features:\n((?:[ \t]+\S.*\n|\s*\n)*)", text, re.MULTILINE)
    assert block, "no `features:` block in config.yaml"
    named = re.findall(r"^\s+(\w+):", block.group(1), re.MULTILINE)
    assert named == list(FEATURE_IDS)


@pytest.mark.parametrize("stage", _STAGE_ORDER)
def test_every_stage_belongs_to_a_feature(stage):
    assert stage in FEATURE_STAGE.values()
