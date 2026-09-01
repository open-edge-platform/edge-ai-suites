# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""A lesson too long for one segmentation call is segmented window by window."""

import json
import os
import re
import sys
from unittest.mock import patch

_SC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SC_ROOT not in sys.path:
    sys.path.insert(0, _SC_ROOT)

from components.segmentation import topic_merge
from components.segmentation.content_segmentation import (
    MAX_TOPICS,
    MIN_TOPICS,
    ContentSegmentationComponent,
)
from utils import text_chunker as tc
from utils.transcript_parser import parse_transcript_lines


class FakeTokenizer:
    def encode(self, text):
        return text.split()


def _quota_topics(prompt):
    """Answer a window prompt with exactly its quota, inside its own range."""
    quota = int(re.search(r"EXACTLY (\d+) topic", prompt).group(1))
    lo, hi = (float(x) for x in re.search(r"covering (\d+)s to (\d+)s", prompt).groups())
    span = (hi - lo) / quota
    return [{"topic": f"Explaining the material from {lo + i * span:.0f} seconds on",
             "start_time": lo + i * span,
             "end_time": lo + (i + 1) * span}
            for i in range(quota)]


class FakeSegmenter:
    """Records every generate() call and answers window prompts in range."""

    def __init__(self, reply=None, raise_on_schema=False):
        self.tokenizer = FakeTokenizer()
        self.calls = []
        self._reply = reply
        self._raise_on_schema = raise_on_schema

    def generate(self, *, messages, stream=False, max_new_tokens=None, **kwargs):
        if self._raise_on_schema and "json_schema" in kwargs:
            raise TypeError("generate() got an unexpected keyword 'json_schema'")
        self.calls.append({"messages": messages, "max_new_tokens": max_new_tokens,
                           "json_schema": kwargs.get("json_schema")})
        text = "\n".join(m["content"] for m in messages)
        if self._reply is not None:
            return self._reply(text) if callable(self._reply) else self._reply
        return json.dumps(_quota_topics(text), ensure_ascii=False)

    @property
    def prompts(self):
        return ["\n".join(m["content"] for m in c["messages"]) for c in self.calls]


# 1500 turns of ~22 tokens is ~33k, comfortably past a 24k budget, the way the
# 132-minute recording that motivated windowing was.
_LONG = 1500
_BUDGET = 24_000


def _timestamped(n_lines=_LONG, words=20):
    return "\n".join(
        f"[{i * 10}-{i * 10 + 10}] " + " ".join(f"w{i}x{j}" for j in range(words))
        for i in range(n_lines)
    )


def _speaker_labelled(n_lines=_LONG, words=20):
    """What the dialog transcript looks like: speakers, no timestamps."""
    return "\n".join(
        f"{'Teacher' if i % 3 else 'Student'}: "
        + " ".join(f"w{i}x{j}" for j in range(words))
        for i in range(n_lines)
    )


def _component(handler=None):
    component = ContentSegmentationComponent("s1", temperature=0.2)
    component.model = handler or FakeSegmenter()
    return component


def _windows(transcript, budget=_BUDGET, component=None):
    component = component or _component()
    with patch.object(tc, "resolve_budget", return_value=budget):
        return component._plan_windows(transcript, language="en")


# ------------------------------------------------------------------- planning

def test_a_short_lesson_is_segmented_in_one_call():
    assert _windows(_timestamped(10)) == []


def test_a_long_lesson_is_windowed():
    windows = _windows(_timestamped())
    assert len(windows) > 1
    assert windows[0].start == 0.0
    assert windows[-1].end == float(_LONG * 10)
    assert all(w.total == len(windows) for w in windows)
    assert [w.index for w in windows] == list(range(len(windows)))


def test_windows_cover_the_whole_lesson_without_a_gap():
    """The coverage failure that started this was topics missing the lesson's end."""
    windows = _windows(_timestamped())
    for prev, nxt in zip(windows, windows[1:]):
        assert nxt.start <= prev.end, "a gap here is a stretch nothing describes"


def test_windows_carry_the_transcript_with_its_timestamps():
    """The model is asked for times, so the window text has to show them."""
    windows = _windows(_timestamped())
    assert windows[0].text.startswith("[0-10] ")
    assert all(line.startswith("[") for line in windows[0].text.splitlines())


def test_an_untimestamped_transcript_falls_back_to_one_call(caplog):
    """Nothing to timestamp a topic with, so a window quota would be worthless."""
    with caplog.at_level("INFO"):
        assert _windows(_speaker_labelled()) == []
    assert any("carries no timestamps" in r.message for r in caplog.records)


def test_chunking_disabled_falls_back_to_one_call():
    from utils.config_loader import config

    chunking = config.models.text_gen.chunking
    original = chunking.enabled
    chunking.enabled = False
    try:
        assert _windows(_timestamped()) == []
    finally:
        chunking.enabled = original


def test_a_lone_window_is_refused(caplog):
    """Documented as unreachable; the guard is what keeps it that way."""
    lone = tc.Chunk(text="x", index=0, total=1, tokens=10, start=0.0, end=10.0)
    with patch.object(tc, "chunk_transcript_lines", return_value=[lone]), \
         caplog.at_level("WARNING"):
        assert _windows(_timestamped()) == []
    assert any("segmenting in one call" in r.message for r in caplog.records)


def test_a_tighter_budget_makes_more_windows():
    assert len(_windows(_timestamped(), budget=8_000)) > \
        len(_windows(_timestamped(), budget=_BUDGET))


# -------------------------------------------------------------------- reserves

def test_the_single_call_reserve_covers_the_template_and_the_answer():
    from utils.config_loader import config

    answer_only = int(config.models.text_gen.max_new_tokens)
    assert _component()._call_overhead("en") > answer_only, \
        "the reserve must include the rendered prompt, not just max_new_tokens"


def test_a_window_is_not_charged_for_the_whole_lesson_answer():
    """A window writes ~1024 tokens of topics, not the single call's 5120."""
    component = _component()
    assert 0 < component._stage_reserve() < component._call_overhead("en")


def test_the_reserve_decides_whether_one_call_does():
    """A transcript that fits the raw budget can still be too big for one call."""
    component = _component()
    reserve = component._call_overhead("en")
    # Sized to sit between the raw budget and what is left after the reserve.
    lines = (_BUDGET - reserve // 2) // 22
    assert _windows(_timestamped(lines), component=component), \
        "a transcript under the budget but over the reserve must be windowed"


def test_a_window_is_sized_by_the_cheaper_reserve():
    """Charging each window for the whole-lesson answer would cut it finer."""
    component = _component()
    lines = tc.render_transcript_lines(parse_transcript_lines(_timestamped()))
    weights = [tc.count_tokens(l, FakeTokenizer()) + 1 for l in lines]
    reserve = component._call_overhead("en")
    stage = component._stage_reserve()
    tight = 12_000  # a budget where the two reserves disagree on the count

    assert tc.usable_tokens(tight, stage) > tc.usable_tokens(tight, reserve)

    windowed = tc.plan_line_groups(weights, budget_tokens=tight,
                                   reserve_tokens=reserve,
                                   stage_reserve_tokens=stage, label="window")
    charged_in_full = tc.plan_line_groups(weights, budget_tokens=tight,
                                          reserve_tokens=reserve, label="window")
    assert len(windowed) < len(charged_in_full)

    # And that is the count the component actually plans.
    assert len(_windows(_timestamped(), budget=tight, component=component)) == \
        len(windowed)


# ---------------------------------------------------------------------- prompts

def test_a_window_prompt_states_its_quota_and_its_range():
    component = _component()
    messages = component._build_messages(
        "[100-110] hello", language="en", quota=7,
        window_start=100.0, window_end=1300.0,
    )
    prompt = "\n".join(m["content"] for m in messages)

    assert "EXACTLY 7 topic object(s)" in prompt
    assert "covering 100s to 1300s" in prompt
    assert "all timestamps between 100 and 1300" in prompt
    # The whole-lesson count constraint must not leak into a window prompt.
    assert f"between {MIN_TOPICS} and {MAX_TOPICS} topic objects" not in prompt


def test_a_whole_lesson_prompt_states_the_topic_range_instead():
    prompt = "\n".join(
        m["content"] for m in _component()._build_messages("[0-10] hi", language="en")
    )
    assert f"between {MIN_TOPICS} and {MAX_TOPICS} topic objects" in prompt
    assert "topic object(s)" not in prompt, "a per-window quota must not leak here"
    assert "ONE WINDOW" not in prompt


def test_the_language_choice_survives_both_modes():
    component = _component()
    for kwargs in ({}, {"quota": 3, "window_start": 0.0, "window_end": 60.0}):
        zh = "\n".join(m["content"] for m in
                       component._build_messages("x", language="zh", **kwargs))
        en = "\n".join(m["content"] for m in
                       component._build_messages("x", language="en", **kwargs))
        assert "简体中文" in zh and "简体中文" not in en
        assert "Write all titles in English." in en


def test_the_transcript_is_substituted_not_formatted():
    """The templates hold literal JSON braces, so .format would blow up."""
    prompt = "\n".join(
        m["content"] for m in
        _component()._build_messages("[0-10] {not_a_field}", language="en")
    )
    assert "[0-10] {not_a_field}" in prompt
    assert '"topic": "<descriptive title>"' in prompt


# ------------------------------------------------------------ one window's call

def test_a_window_is_generated_under_its_own_token_cap():
    handler = FakeSegmenter()
    component = _component(handler)
    window = tc.Chunk(text="[100-110] hi", index=0, total=3, tokens=100,
                      start=100.0, end=1300.0)

    topics = component._generate_window(window, quota=5, language="en",
                                        max_new_tokens=1024)

    assert len(topics) == 5
    assert handler.calls[0]["max_new_tokens"] == 1024
    assert handler.calls[0]["json_schema"], "decoding should be schema-constrained"


def test_a_windows_topics_are_clamped_into_the_window():
    """A model that answers in whole-lesson seconds must not drift outside."""
    drifted = json.dumps([{"topic": "Drifted well past the end of this window",
                           "start_time": 0.0, "end_time": 9999.0}])
    component = _component(FakeSegmenter(reply=drifted))
    window = tc.Chunk(text="x", index=1, total=3, tokens=100,
                      start=1320.0, end=2640.0)

    topics = component._generate_window(window, 1, "en", 1024)
    assert topics == [{"topic": "Drifted well past the end of this window",
                       "start_time": 1320.0, "end_time": 2640.0}]


def test_one_bad_window_does_not_sink_the_lesson(caplog):
    component = _component(FakeSegmenter(reply="I am afraid I cannot do that."))
    window = tc.Chunk(text="x", index=2, total=6, tokens=100,
                      start=100.0, end=200.0)

    with caplog.at_level("WARNING"):
        assert component._generate_window(window, 3, "en", 1024) == []
    assert any("3/6" in r.message and "failed to segment" in r.message
               for r in caplog.records)


def test_a_backend_without_json_schema_is_retried_unconstrained():
    handler = FakeSegmenter(raise_on_schema=True)
    component = _component(handler)
    window = tc.Chunk(text="[100-110] hi", index=0, total=2, tokens=100,
                      start=100.0, end=1300.0)

    assert component._generate_window(window, 4, "en", 1024)
    assert handler.calls[0]["json_schema"] is None
    assert len(handler.calls) == 1, "the rejected call never reached the model"


# --------------------------------------------------------------- the whole run

def test_every_window_is_segmented_and_the_results_are_merged():
    handler = FakeSegmenter()
    component = _component(handler)
    windows = _windows(_timestamped(), component=component)

    merged = json.loads(component._generate_topics_windowed(windows, "en"))

    assert len(handler.calls) == len(windows)
    assert MIN_TOPICS <= len(merged) <= MAX_TOPICS
    for prev, nxt in zip(merged, merged[1:]):
        assert prev["end_time"] <= nxt["start_time"]
    assert merged[0]["start_time"] == 0.0
    assert merged[-1]["end_time"] == float(_LONG * 10)


def test_the_quotas_sent_to_the_windows_add_up_to_the_target():
    from utils.config_loader import config

    handler = FakeSegmenter()
    component = _component(handler)
    windows = _windows(_timestamped(), component=component)
    component._generate_topics_windowed(windows, "en")

    quotas = [int(re.search(r"EXACTLY (\d+) topic", p).group(1))
              for p in handler.prompts]
    assert quotas == topic_merge.allocate_quota(
        [w.tokens for w in windows], int(config.models.text_gen.segmentation.topics_target)
    )
    assert sum(quotas) == int(config.models.text_gen.segmentation.topics_target)


def test_a_run_where_no_window_answers_is_an_error():
    component = _component(FakeSegmenter(reply="nothing parseable here"))
    windows = _windows(_timestamped(), component=_component())

    try:
        component._generate_topics_windowed(windows, "en")
    except ValueError as exc:
        assert str(exc) == "INVALID_TOPICS_FORMAT"
    else:
        raise AssertionError("a run that produced no topics must not look like success")


def test_generate_topics_routes_a_long_lesson_through_the_windows():
    handler = FakeSegmenter()
    component = _component(handler)
    with patch.object(tc, "resolve_budget", return_value=_BUDGET):
        topics = json.loads(component.generate_topics(_timestamped(), language="en"))

    assert len(handler.calls) > 1, "a long lesson must not be sent in one call"
    assert all("ONE WINDOW" in p for p in handler.prompts)
    assert MIN_TOPICS <= len(topics) <= MAX_TOPICS


def test_generate_topics_sends_a_short_lesson_whole():
    whole = json.dumps([
        {"topic": f"Explaining part {i} of the lesson in detail here",
         "start_time": float(i * 10), "end_time": float(i * 10 + 10)}
        for i in range(MIN_TOPICS)
    ])
    handler = FakeSegmenter(reply=whole)
    component = _component(handler)

    with patch.object(tc, "resolve_budget", return_value=_BUDGET):
        topics = json.loads(component.generate_topics(_timestamped(10), language="en"))

    assert len(handler.calls) == 1
    assert "ONE WINDOW" not in handler.prompts[0]
    assert handler.calls[0]["max_new_tokens"] is None, "the whole lesson is uncapped"
    assert len(topics) == MIN_TOPICS
