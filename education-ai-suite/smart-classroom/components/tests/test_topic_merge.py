# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import sys

_SC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SC_ROOT not in sys.path:
    sys.path.insert(0, _SC_ROOT)

from components.segmentation import topic_merge as tm


def _topics(n, *, span=100.0, offset=0.0, title="Topic"):
    return [
        {"topic": f"{title} {i}",
         "start_time": offset + i * span,
         "end_time": offset + (i + 1) * span}
        for i in range(n)
    ]


# ---------------------------------------------------------------------- quota

def test_quota_sums_to_the_target():
    for weights in ([1000, 1000, 1000, 1000], [5000, 1000, 200], [3000] * 7):
        quotas = tm.allocate_quota(weights, 20)
        assert sum(quotas) == 20, (weights, quotas)


def test_quota_is_proportional_to_window_size():
    quotas = tm.allocate_quota([9000, 1000], 20)
    assert quotas[0] > quotas[1]


def test_quota_gives_every_window_at_least_one():
    quotas = tm.allocate_quota([10_000, 10, 10], 20)
    assert all(q >= 1 for q in quotas)
    assert sum(quotas) == 20


def test_quota_handles_degenerate_inputs():
    assert tm.allocate_quota([], 20) == []
    assert tm.allocate_quota([100] * 30, 20) == [1] * 30
    # More windows than topics wanted: one each and let the merge trim, rather
    # than asking some windows for zero topics.
    assert tm.allocate_quota([100] * 20, 20) == [1] * 20
    assert tm.allocate_quota([0, 0, 0], 6) == [2, 2, 2], \
        "windows of unknown size share the target evenly"


def test_quota_floor_is_configurable():
    quotas = tm.allocate_quota([10_000, 10, 10], 20, min_per_window=2)
    assert all(q >= 2 for q in quotas)
    assert sum(quotas) == 20


def test_quota_never_falls_below_the_floor_while_trimming():
    """Rounding up can overshoot; taking the excess back must respect the floor."""
    quotas = tm.allocate_quota([1, 1, 1, 1, 1, 1, 1, 1, 1, 5000], 11)
    assert sum(quotas) == 11
    assert min(quotas) >= 1


# ------------------------------------------------------------------ normalize

def test_normalize_clamps_timestamps_into_the_window():
    raw = [{"topic": "drifted", "start_time": 0.0, "end_time": 9999.0}]
    out = tm.normalize_topics(raw, window_start=1320.0, window_end=2640.0)
    assert out == [{"topic": "drifted", "start_time": 1320.0, "end_time": 2640.0}]


def test_normalize_drops_malformed_entries():
    raw = [
        {"topic": "ok", "start_time": 10, "end_time": 20},
        {"topic": "", "start_time": 20, "end_time": 30},          # no title
        {"topic": "bad times", "start_time": "x", "end_time": 30},  # unparseable
        {"topic": "inverted", "start_time": 50, "end_time": 40},    # zero span
        "not a dict",
    ]
    out = tm.normalize_topics(raw, window_start=0.0, window_end=100.0)
    assert [t["topic"] for t in out] == ["ok"]


def test_normalize_tolerates_non_list_input():
    assert tm.normalize_topics(None, window_start=0, window_end=10) == []
    assert tm.normalize_topics({"topic": "x"}, window_start=0, window_end=10) == []


def test_normalize_clamps_from_below_too():
    """A window is told its range; a model that answers in absolute seconds
    from the start of the lesson must not drag topics before the window."""
    raw = [{"topic": "early", "start_time": -50.0, "end_time": 1500.0}]
    out = tm.normalize_topics(raw, window_start=1320.0, window_end=2640.0)
    assert out == [{"topic": "early", "start_time": 1320.0, "end_time": 1500.0}]


def test_normalize_drops_a_topic_clamped_flat():
    """Wholly outside the window: both ends land on the same edge, so nothing
    is left to describe."""
    raw = [{"topic": "elsewhere", "start_time": 10.0, "end_time": 900.0}]
    assert tm.normalize_topics(raw, window_start=1320.0, window_end=2640.0) == []


def test_normalize_sorts_by_start_time():
    raw = [
        {"topic": "second", "start_time": 60, "end_time": 90},
        {"topic": "first", "start_time": 10, "end_time": 50},
    ]
    out = tm.normalize_topics(raw, window_start=0.0, window_end=100.0)
    assert [t["topic"] for t in out] == ["first", "second"]


def test_normalize_accepts_numeric_strings():
    """json_repair hands back whatever the model wrote, quotes included."""
    raw = [{"topic": "ok", "start_time": "10.5", "end_time": "20"}]
    out = tm.normalize_topics(raw, window_start=0.0, window_end=100.0)
    assert out == [{"topic": "ok", "start_time": 10.5, "end_time": 20.0}]


# ---------------------------------------------------------------------- merge

def test_merge_caps_at_max_and_stays_ordered():
    merged = tm.merge_topics(_topics(60), min_count=15, max_count=25)
    assert len(merged) <= 25
    starts = [t["start_time"] for t in merged]
    assert starts == sorted(starts)


def test_merge_leaves_no_overlaps():
    overlapping = [
        {"topic": "A", "start_time": 0, "end_time": 150},
        {"topic": "B", "start_time": 100, "end_time": 250},
        {"topic": "C", "start_time": 200, "end_time": 350},
    ]
    merged = tm.merge_topics(overlapping, min_count=1, max_count=25)
    for prev, nxt in zip(merged, merged[1:]):
        assert prev["end_time"] <= nxt["start_time"]


def test_merge_collapses_seam_duplicates():
    seam = [
        {"topic": "解释牛顿第三定律在火箭推进中的应用", "start_time": 1200, "end_time": 1400},
        {"topic": "解释牛顿第三定律在火箭推进中的应用及示例", "start_time": 1350, "end_time": 1500},
        {"topic": "讨论动量守恒定律的推导过程", "start_time": 1500, "end_time": 1700},
    ]
    merged = tm.merge_topics(seam, min_count=1, max_count=25)
    assert len(merged) == 2
    assert merged[0]["topic"].endswith("及示例")
    assert merged[0]["end_time"] == 1500


def test_merge_keeps_distinct_topics_that_merely_overlap():
    """Seam folding is for the same topic seen twice, not for two subjects that
    a sloppy timestamp made overlap."""
    overlapping = [
        {"topic": "解释牛顿第三定律在火箭推进中的应用", "start_time": 1200, "end_time": 1400},
        {"topic": "讨论动量守恒定律的推导过程", "start_time": 1350, "end_time": 1600},
    ]
    merged = tm.merge_topics(overlapping, min_count=1, max_count=25)
    assert len(merged) == 2
    assert merged[0]["end_time"] == 1350, "the overlap is trimmed, not folded"


def test_merge_folds_the_shortest_adjacent_pair_first():
    """Over the cap, the pair that costs the least to lose goes first."""
    topics = [
        {"topic": "long A", "start_time": 0, "end_time": 600},
        {"topic": "brief B", "start_time": 600, "end_time": 610},
        {"topic": "brief C", "start_time": 610, "end_time": 620},
        {"topic": "long D", "start_time": 620, "end_time": 1200},
    ]
    merged = tm.merge_topics(topics, min_count=1, max_count=3)
    assert len(merged) == 3
    assert [t["topic"] for t in merged] == ["long A", "brief B", "long D"]
    assert merged[1]["end_time"] == 620, "B absorbed C's span"


def test_merge_does_not_fabricate_topics_when_short():
    few = _topics(4)
    merged = tm.merge_topics(few, min_count=15, max_count=25)
    assert len(merged) == 4


def test_a_short_result_is_reported_rather_than_padded(caplog):
    with caplog.at_level("WARNING"):
        tm.merge_topics(_topics(4), min_count=15, max_count=25)
    assert any("below the 15 minimum" in r.message for r in caplog.records)


def test_a_result_inside_the_range_is_quiet(caplog):
    with caplog.at_level("WARNING"):
        tm.merge_topics(_topics(18), min_count=15, max_count=25)
    assert not caplog.records


def test_merge_preserves_lesson_span():
    topics = _topics(60, span=120.0)
    merged = tm.merge_topics(topics, min_count=15, max_count=25)
    assert merged[0]["start_time"] == topics[0]["start_time"]
    assert merged[-1]["end_time"] == topics[-1]["end_time"]


def test_merge_handles_empty():
    assert tm.merge_topics([]) == []


def test_windows_end_to_end_land_in_range():
    """6 windows of 5 topics each, with seam duplicates."""
    collected = []
    for w in range(6):
        base = w * 1300.0
        collected.extend(
            tm.normalize_topics(
                _topics(5, span=260.0, offset=base, title=f"W{w}"),
                window_start=base, window_end=base + 1300.0,
            )
        )
    merged = tm.merge_topics(collected, min_count=15, max_count=25)
    assert 15 <= len(merged) <= 25
    for prev, nxt in zip(merged, merged[1:]):
        assert prev["end_time"] <= nxt["start_time"]
        assert nxt["end_time"] > nxt["start_time"]
