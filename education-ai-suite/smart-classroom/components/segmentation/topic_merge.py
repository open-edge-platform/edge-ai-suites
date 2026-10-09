# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Assemble per-window topic lists into one ordered lesson-wide segmentation."""

import logging
import re
from difflib import SequenceMatcher
from typing import List

logger = logging.getLogger(__name__)

_SEAM_TITLE_SIMILARITY = 0.75
_PUNCT_RE = re.compile(r"[\s，。、；：,.;:!?！？\-—_/\\'\"“”‘’()（）\[\]]+")


def allocate_quota(window_weights: List[int], total_target: int = 20,
                   min_per_window: int = 1) -> List[int]:
    """Split ``total_target`` topics across windows in proportion to their size.

    Uses largest-remainder rounding so the quotas sum to exactly ``total_target``.
    """
    n = len(window_weights)
    if n == 0:
        return []
    if n >= total_target:
        return [min_per_window] * n

    total = sum(window_weights) or n
    exact = [w / total * total_target for w in window_weights]
    quotas = [max(min_per_window, int(e)) for e in exact]

    while (diff := total_target - sum(quotas)) != 0:
        step = 1 if diff > 0 else -1
        movable = [i for i in range(n) if step > 0 or quotas[i] > min_per_window]
        if not movable:
            break
        movable.sort(key=lambda i: exact[i] - int(exact[i]), reverse=step > 0)
        for i in movable[:abs(diff)]:
            quotas[i] += step
    return quotas


def normalize_topics(topics, *, window_start: float, window_end: float) -> List[dict]:
    """Coerce one window's raw output into topic dicts, clamped into the window.

    Drops entries that are malformed, untitled, or of non-positive duration.
    """
    if not isinstance(topics, list):
        return []

    cleaned = []
    for raw in topics:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("topic") or "").strip()
        if not title:
            continue
        try:
            start = float(raw.get("start_time"))
            end = float(raw.get("end_time"))
        except (TypeError, ValueError):
            continue

        start = min(max(start, window_start), window_end)
        end = min(max(end, window_start), window_end)
        if end <= start:
            continue
        cleaned.append({"topic": title, "start_time": start, "end_time": end})

    cleaned.sort(key=lambda t: t["start_time"])
    return cleaned


def _title_key(title: str) -> str:
    return _PUNCT_RE.sub("", title).lower()


def _similar(a: str, b: str) -> float:
    ka, kb = _title_key(a), _title_key(b)
    if not ka or not kb:
        return 0.0
    if ka in kb or kb in ka:
        return 1.0
    return SequenceMatcher(None, ka, kb).ratio()


def _collapse_seams(topics: List[dict]) -> List[dict]:
    """Fold adjacent topics that overlap in time and have near-identical titles."""
    merged: List[dict] = []
    for topic in topics:
        if merged:
            prev = merged[-1]
            overlaps = topic["start_time"] < prev["end_time"]
            if overlaps and _similar(prev["topic"], topic["topic"]) >= _SEAM_TITLE_SIMILARITY:
                prev["end_time"] = max(prev["end_time"], topic["end_time"])
                if len(topic["topic"]) > len(prev["topic"]):
                    prev["topic"] = topic["topic"]
                continue
        merged.append(dict(topic))
    return merged


def merge_topics(topics: List[dict], *, min_count: int = 15,
                 max_count: int = 25) -> List[dict]:
    """Reduce per-window topics to one ordered, non-overlapping list.

    Sorts by start time, folds seam duplicates, trims overlaps, and fuses the
    shortest adjacent pair until at most ``max_count`` remain. A result below
    ``min_count`` is returned as-is with a warning.

    The fusing criterion is duration alone, which is a deliberate trade: it
    costs no model call, but it will fuse two short unrelated topics while
    leaving a pair that is genuinely one subject if their titles differ enough
    to survive ``_collapse_seams``. Fixing that properly means a reduce call
    over the merged list, which is worth doing only if the arithmetic merge is
    seen to produce visibly wrong chapter boundaries.
    """
    if not topics:
        return []

    ordered = sorted(topics, key=lambda t: (t["start_time"], t["end_time"]))
    ordered = _collapse_seams(ordered)

    for i in range(len(ordered) - 1):
        if ordered[i]["end_time"] > ordered[i + 1]["start_time"]:
            ordered[i]["end_time"] = ordered[i + 1]["start_time"]
    ordered = [t for t in ordered if t["end_time"] > t["start_time"]]

    while len(ordered) > max_count:
        shortest = min(
            range(len(ordered) - 1),
            key=lambda i: (ordered[i + 1]["end_time"] - ordered[i]["start_time"]),
        )
        ordered[shortest]["end_time"] = ordered[shortest + 1]["end_time"]
        del ordered[shortest + 1]

    if len(ordered) < min_count:
        logger.warning(
            "Topic segmentation produced %d topics, below the %d minimum; "
            "returning as-is rather than splitting artificially.",
            len(ordered), min_count,
        )
    return ordered
