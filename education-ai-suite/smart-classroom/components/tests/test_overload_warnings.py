# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""An overload the budget cannot fix must reach the user, and change nothing."""

import json
import os
import sys
from unittest.mock import patch

_SC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SC_ROOT not in sys.path:
    sys.path.insert(0, _SC_ROOT)

from components.segmentation.content_segmentation import ContentSegmentationComponent
from components.summarizer_component import SummarizerComponent
from utils import overload_warnings as ow
from utils import text_chunker as tc

from test_summarizer_mapreduce import (FakeHandler, _long_note, _run, _tokens,
                                       _transcript)


def _warnings(items):
    return [i for i in items
            if isinstance(i, dict) and i.get("event") == "warning"]


def _codes(items):
    return [w["code"] for w in _warnings(items)]


# ------------------------------------------------------------ the collector

def test_a_warning_is_written_as_one_json_line_per_record(tmp_path, monkeypatch):
    path = tmp_path / "warnings.jsonl"
    monkeypatch.setattr(ow, "warnings_path", lambda session_id: path)

    collector = ow.OverloadWarnings("s1", "summary")
    collector.on_cap(budget=4_000, reserve=5_000, cap=2_000)
    collector.on_oversize(largest=900, ceiling=800, label="segment")

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert [json.loads(l)["code"] for l in lines] == [ow.RESERVE_CAPPED,
                                                      ow.LINE_OVERSIZE]
    # The numbers are fields, not prose: the UI and the analysis read the same
    # values without parsing a sentence.
    first = json.loads(lines[0])
    assert (first["budget"], first["reserve"], first["cap"]) == (4_000, 5_000, 2_000)
    assert first["stage"] == "summary"

    assert [w["code"] for w in ow.read("s1")] == [ow.RESERVE_CAPPED, ow.LINE_OVERSIZE]


def test_the_same_condition_is_recorded_once(tmp_path, monkeypatch):
    """One planning pass asks usable_tokens twice; the user has one problem."""
    path = tmp_path / "warnings.jsonl"
    monkeypatch.setattr(ow, "warnings_path", lambda session_id: path)

    collector = ow.OverloadWarnings("s1", "summary")
    for _ in range(3):
        collector.on_cap(budget=4_000, reserve=5_000, cap=2_000)
    collector.on_cap(budget=8_000, reserve=5_000, cap=4_000)   # different numbers

    assert len(collector.records) == 2
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_recording_never_breaks_the_run_it_describes(monkeypatch):
    """Observability is not allowed to raise into the pipeline."""
    def explode(session_id):
        raise OSError("disk full")

    monkeypatch.setattr(ow, "warnings_path", explode)
    entry = ow.OverloadWarnings("s1", "summary").record(ow.MEMORY_SHORT, "...")

    assert entry["code"] == ow.MEMORY_SHORT  # still returned to the caller


def test_a_malformed_line_does_not_discard_the_others(tmp_path, monkeypatch):
    path = tmp_path / "warnings.jsonl"
    path.write_text('{"code": "memory_short"}\nnot json\n\n{"code": "line_oversize"}\n',
                    encoding="utf-8")
    monkeypatch.setattr(ow, "warnings_path", lambda session_id: path)

    assert [w["code"] for w in ow.read("s")] == [ow.MEMORY_SHORT, ow.LINE_OVERSIZE]


def test_no_session_means_no_file(tmp_path, monkeypatch):
    """A component built without a session still collects, in memory only."""
    monkeypatch.setattr(ow, "warnings_path",
                        lambda session_id: tmp_path / "should-not-exist.jsonl")

    collector = ow.OverloadWarnings(None, "summary")
    collector.on_cap(budget=4_000, reserve=5_000, cap=2_000)

    assert len(collector.records) == 1
    assert not (tmp_path / "should-not-exist.jsonl").exists()


# ------------------------------------------------------- text_chunker hooks

def test_the_reserve_cap_reports_the_numbers_that_caused_it():
    seen = []
    tc.usable_tokens(4_000, 5_000, on_cap=lambda b, r, c: seen.append((b, r, c)))

    assert seen == [(4_000, 5_000, 2_000)]


def test_a_healthy_reserve_reports_nothing():
    seen = []
    assert tc.usable_tokens(24_000, 5_329, on_cap=lambda *a: seen.append(a)) == 18_671
    assert seen == []


def test_the_cap_callback_fires_even_when_the_log_line_is_deduped():
    """The log dedupes across a planning pass; a caller collecting must not."""
    tc._CAP_WARNED.clear()
    seen = []
    for _ in range(3):
        tc.usable_tokens(4_000, 5_000, on_cap=lambda *a: seen.append(a))

    assert len(seen) == 3


def test_an_unpackable_line_reports_its_size_against_the_ceiling():
    seen = []
    # One line far larger than any chunk may be, among lines that pack fine.
    weights = [10] * 20 + [5_000] + [10] * 20
    tc.plan_line_groups(weights, budget_tokens=2_000, reserve_tokens=0,
                        stage_reserve_tokens=0, label="segment",
                        on_oversize=lambda *a: seen.append(a))

    assert seen, "a line larger than the ceiling must be reported"
    largest, ceiling, label = seen[0]
    assert largest > ceiling and label == "segment"


def test_a_packable_transcript_reports_nothing():
    seen = []
    tc.plan_line_groups([10] * 400, budget_tokens=2_000, reserve_tokens=0,
                        stage_reserve_tokens=0, label="segment",
                        on_cap=lambda *a: seen.append(a),
                        on_oversize=lambda *a: seen.append(a))

    assert seen == []


# --------------------------------------------------------- the summary path

def test_a_healthy_summary_warns_about_nothing():
    _, _, items, _ = _run(_transcript(10), budget=100_000)

    assert _warnings(items) == []


def test_the_reserve_cap_reaches_the_client():
    """A budget that the instructions alone overrun is the user's to fix."""
    _, _, items, _ = _run(_transcript(400), budget=2_000)

    capped = [w for w in _warnings(items) if w["code"] == ow.RESERVE_CAPPED]
    assert capped, "the answer may be truncated; saying so is the whole point"
    assert capped[0]["stage"] == "summary"
    assert capped[0]["cap"] == 1_000
    assert str(capped[0]["budget"]) in capped[0]["detail"]


def test_a_warning_never_costs_the_summary_a_token():
    """The call a warning describes still runs; the summary must be intact."""
    _, handler, items, saved = _run(_transcript(400), budget=2_000)

    assert _warnings(items), "this budget must trip the reserve cap"
    assert _tokens(items) == FakeHandler.SUMMARY_TOKENS
    assert saved == "".join(FakeHandler.SUMMARY_TOKENS)
    assert handler.stream_calls, "the reduce call still ran"


def test_a_warning_is_never_written_into_the_summary():
    _, _, items, saved = _run(_transcript(400), budget=2_000)

    for warning in _warnings(items):
        assert warning["detail"] not in saved
        assert warning["code"] not in saved


def test_planning_warnings_arrive_before_the_first_call():
    """They describe the calls that follow, so they cannot trail them."""
    _, handler, _, _ = _run(_transcript(400), budget=2_000)

    kinds = [k for k, p in handler.timeline
             if k == "generate" or (isinstance(p, dict)
                                    and p.get("code") == ow.RESERVE_CAPPED)]
    assert kinds[0] != "generate", "the warning came after work had started"


def test_a_fold_that_gives_up_says_so_before_the_reduce_call():
    """Two rounds is a cap: the run continues over budget, and admits it."""
    _, handler, items, _ = _run(_transcript(400), budget=2_000, note=_long_note())

    fold = [w for w in _warnings(items) if w["code"] == ow.FOLD_INCOMPLETE]
    assert fold, "notes still over budget after two rounds must be reported"
    assert fold[0]["rounds"] == 2
    assert fold[0]["notes_tokens"] > fold[0]["reduce_budget"]

    # Before the reduce call, which is the one it warns about.
    order = [p for k, p in handler.timeline if k == "yield" and isinstance(p, dict)]
    codes = [i for i, p in enumerate(order) if p.get("code") == ow.FOLD_INCOMPLETE]
    reduces = [i for i, p in enumerate(order) if p.get("stage") == "reduce"
               and p.get("event") == "progress"]
    assert codes and reduces and codes[0] < reduces[0]


def test_a_busy_machine_is_reported_but_the_plan_is_not_changed():
    """The backstop reports; changing the plan would make a summary irreproducible."""
    def short(tokens, device="GPU", model_dir=None, what="call", *, on_short=None):
        if on_short is not None:
            on_short(tokens, 8 * 1024 ** 3, 2 * 1024 ** 3, what)
        return True

    with patch.object(tc, "warn_if_short_of_memory", side_effect=short):
        _, handler, items, saved = _run(_transcript(400), budget=100_000)

    short_warnings = [w for w in _warnings(items) if w["code"] == ow.MEMORY_SHORT]
    assert short_warnings
    assert short_warnings[0]["free_gb"] == 2.0 and short_warnings[0]["need_gb"] == 8.0
    # 100k budget holds this transcript in one call, and the warning left it there.
    assert len(handler.calls) == 1
    assert saved == "".join(FakeHandler.SUMMARY_TOKENS)


# ---------------------------------------------------- the segmentation path

def _segmentation(session_id="s1"):
    component = ContentSegmentationComponent(session_id=session_id)
    component.model = FakeHandler()
    return component


def test_segmentation_collects_its_warnings_under_its_own_stage():
    component = _segmentation()
    component.warnings.on_cap(budget=4_000, reserve=5_000, cap=2_000)

    assert [w["stage"] for w in component.warnings.records] == ["segmentation"]


def test_the_two_consumers_do_not_share_a_collector():
    """One session's summary and segmentation warn about different calls."""
    with patch("components.summarizer_component.ModelManager") as mock_mm:
        mock_mm.instance.return_value.text_gen.return_value = FakeHandler()
        summarizer = SummarizerComponent(session_id="s1", mode="dialog")
    segmentation = _segmentation()

    summarizer.warnings.on_cap(budget=4_000, reserve=5_000, cap=2_000)

    assert summarizer.warnings.records and segmentation.warnings.records == []
