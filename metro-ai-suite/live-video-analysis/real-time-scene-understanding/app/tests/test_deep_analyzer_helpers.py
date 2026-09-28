# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for pure helpers in backend.services.deep_analyzer.

DeepAnalyzerEngine.__init__ loads a real VLM pipeline, so these tests only
exercise the module-level function and static method that don't require
instantiating the engine.
"""

from __future__ import annotations

import json
import queue
import threading
import uuid
from collections import OrderedDict

import pytest
from backend.services import deep_analyzer as deep_analyzer_module
from backend.services.deep_analyzer import DeepAnalyzerEngine
from backend.services.deep_analyzer import _AnalysisJob
from backend.services.deep_analyzer import _next_segment_path


class TestNextSegmentPath:
    def test_increments_the_trailing_index(self):
        assert _next_segment_path("segments/default_segment_0001.mp4") == "segments/default_segment_0002.mp4"

    def test_preserves_zero_padding_width(self):
        assert _next_segment_path("segments/default_segment_0009.mp4") == "segments/default_segment_0010.mp4"

    def test_does_not_truncate_when_index_grows_a_digit(self):
        assert _next_segment_path("segments/default_segment_9999.mp4") == "segments/default_segment_10000.mp4"

    def test_returns_none_when_path_has_no_digits(self):
        assert _next_segment_path("segments/default_segment.mp4") is None


class TestMarkBoundedCache:
    def test_adds_key_to_cache(self):
        cache: "OrderedDict[str, None]" = OrderedDict()
        DeepAnalyzerEngine._mark(cache, "segment-1")
        assert list(cache.keys()) == ["segment-1"]

    def test_evicts_oldest_key_once_over_capacity(self, monkeypatch):
        monkeypatch.setattr(deep_analyzer_module.settings, "DEEP_ANALYZER_DEDUP_CACHE_SIZE", 2)
        cache: "OrderedDict[str, None]" = OrderedDict()

        DeepAnalyzerEngine._mark(cache, "segment-1")
        DeepAnalyzerEngine._mark(cache, "segment-2")
        DeepAnalyzerEngine._mark(cache, "segment-3")

        assert list(cache.keys()) == ["segment-2", "segment-3"]

    @pytest.mark.parametrize("capacity", [1, 5])
    def test_never_exceeds_configured_capacity(self, monkeypatch, capacity):
        monkeypatch.setattr(deep_analyzer_module.settings, "DEEP_ANALYZER_DEDUP_CACHE_SIZE", capacity)
        cache: "OrderedDict[str, None]" = OrderedDict()

        for i in range(capacity + 10):
            DeepAnalyzerEngine._mark(cache, f"segment-{i}")

        assert len(cache) == capacity


class TestDeepAnalyzerSubmitFlow:
    def test_structured_output_requires_confirmation(self):
        schema = json.loads(
            deep_analyzer_module.DeepAnalyzerEngine._structured_output_config().json_schema
        )

        assert schema["required"] == ["confirmed", "summary"]
        assert schema["properties"]["confirmed"] == {"type": "boolean"}

    def test_parse_analysis_result_returns_confirmation_and_summary(self):
        assert DeepAnalyzerEngine._parse_analysis_result(
            '{"confirmed": true, "summary": "Fire remains visible."}'
        ) == (True, "Fire remains visible.")

        assert DeepAnalyzerEngine._parse_analysis_result(
            '{"confirmed": false, "summary": "No fire is visible."}'
        ) == (False, "No fire is visible.")

    def test_submit_defers_job_until_segment_finalizes(self):
        engine = object.__new__(DeepAnalyzerEngine)
        engine._lock = threading.Lock()
        engine._dedup = OrderedDict()
        engine._finalized = OrderedDict()
        engine._pending = {}
        engine._active = set()
        engine._stats = {}
        engine._queue = queue.Queue()

        segment_path = "segments/default_segment_0003.mp4"
        engine.submit("stream-7", segment_path, "fire", uuid.uuid4())

        assert segment_path in engine._pending
        assert segment_path in engine._active
        assert engine._queue.empty()
        assert engine._stream_stats("stream-7")["submitted"] == 1
        assert engine._stream_stats("stream-7")["queued"] == 1

    def test_on_segment_finalized_queues_pending_job(self):
        engine = object.__new__(DeepAnalyzerEngine)
        engine._lock = threading.Lock()
        engine._dedup = OrderedDict()
        engine._finalized = OrderedDict()
        engine._pending = {}
        engine._active = set()
        engine._stats = {}
        engine._queue = queue.Queue()

        segment_path = "segments/default_segment_0004.mp4"
        job = _AnalysisJob(
            stream_id="stream-8",
            segment_path=segment_path,
            alert_event="fire",
            frame_id=uuid.uuid4(),
        )
        engine._pending[segment_path] = job
        engine._finalized[segment_path] = None

        engine.on_segment_finalized(segment_path)

        assert segment_path not in engine._pending
        queued_job = engine._queue.get_nowait()
        assert queued_job.segment_path == segment_path
        assert queued_job.stream_id == "stream-8"

    def test_submit_ignores_duplicates(self):
        engine = object.__new__(DeepAnalyzerEngine)
        engine._lock = threading.Lock()
        engine._dedup = OrderedDict({"segments/default_segment_0005.mp4": None})
        engine._finalized = OrderedDict()
        engine._pending = {}
        engine._active = set()
        engine._stats = {}
        engine._queue = queue.Queue()

        engine.submit("stream-9", "segments/default_segment_0005.mp4", "smoke", uuid.uuid4())

        assert engine._queue.empty()
        assert engine._pending == {}
        assert engine._active == set()

    def test_build_generation_config_uses_model_defaults(self):
        engine = object.__new__(DeepAnalyzerEngine)

        class _FakeConfig:
            def __init__(self):
                self.max_new_tokens = 0
                self.min_new_tokens = 0
                self.num_beams = 0
                self.do_sample = False
                self.temperature = 0.0
                self.top_p = 0.0
                self.top_k = 0
                self.repetition_penalty = 0.0
                self.no_repeat_ngram_size = 0
                self.apply_chat_template = False

        class _FakePipe:
            def get_generation_config(self):
                return _FakeConfig()

        engine._pipe = _FakePipe()

        cfg = engine._build_generation_config()

        assert cfg.max_new_tokens == deep_analyzer_module.settings.DEEP_ANALYZER_MAX_TOKENS
        assert cfg.min_new_tokens == min(
            deep_analyzer_module.settings.DEEP_ANALYZER_MIN_TOKENS,
            deep_analyzer_module.settings.DEEP_ANALYZER_MAX_TOKENS,
        )
        assert cfg.apply_chat_template is True

    def test_read_segment_frames_uses_sampling_helper(self, monkeypatch):
        engine = object.__new__(DeepAnalyzerEngine)

        def fake_wait(_job):
            return None

        captured = {"called": False}

        def fake_sample(path, max_frames):
            captured["called"] = True
            assert path == "segments/s1.mp4"
            assert max_frames == deep_analyzer_module.settings.DEEP_ANALYZER_MAX_FRAMES
            return __import__("numpy").array([[1, 2], [3, 4]])

        monkeypatch.setattr(engine, "_wait_for_next_segment", fake_wait)
        monkeypatch.setattr(deep_analyzer_module, "_sample_segment_frames", fake_sample)

        frames = engine._read_segment_frames(_AnalysisJob(stream_id="s", segment_path="segments/s1.mp4", alert_event="fire", frame_id=uuid.uuid4()))

        assert captured["called"] is True
        assert frames.shape == (2, 2)

    def test_analyze_uploads_and_logs_result(self, monkeypatch):
        engine = object.__new__(DeepAnalyzerEngine)
        class _FakeGenConfig:
            structured_output_config = None

        engine._gen_config = _FakeGenConfig()
        engine._pipe = type("Pipe", (), {"generate": lambda self, *args, **kwargs: type("Result", (), {"texts": ["Visible fire in the scene"]})()})()
        engine._object_storage = type("Storage", (), {"upload_segment_and_metadata": lambda self, **kwargs: {"stream_id": kwargs["stream_id"]}})()

        monkeypatch.setattr(engine, "_read_segment_frames", lambda job: __import__("numpy").array([[[0, 0, 0]], [[1, 1, 1]]], dtype="uint8"))
        monkeypatch.setattr(deep_analyzer_module, "get_alert_index", lambda: type("Index", (), {"add": lambda self, payload: None})())
        monkeypatch.setattr(deep_analyzer_module.settings, "DEEP_ANALYZER_STRUCTURED_OUTPUT", True)
        monkeypatch.setattr(deep_analyzer_module, "logger", type("Logger", (), {"info": lambda *args, **kwargs: None, "warning": lambda *args, **kwargs: None})())

        job = _AnalysisJob(stream_id="stream-1", segment_path="segments/seg_0001.mp4", alert_event="fire", frame_id=uuid.uuid4())
        engine._analyze(job)

        assert True

    def test_analyze_appends_description_to_deep_prompt(self, monkeypatch):
        engine = object.__new__(DeepAnalyzerEngine)

        class _FakeGenConfig:
            structured_output_config = None

        captured = {}

        class _FakePipe:
            def generate(self, prompt, *args, **kwargs):
                captured["prompt"] = prompt
                return type("Result", (), {"texts": ["ok"]})()

        engine._gen_config = _FakeGenConfig()
        engine._pipe = _FakePipe()
        engine._object_storage = None

        monkeypatch.setattr(
            engine,
            "_read_segment_frames",
            lambda job: __import__("numpy").array([[[0, 0, 0]]], dtype="uint8"),
        )
        monkeypatch.setattr(deep_analyzer_module.settings, "DEEP_ANALYZER_STRUCTURED_OUTPUT", False)
        monkeypatch.setattr(
            deep_analyzer_module,
            "logger",
            type("Logger", (), {"info": lambda *args, **kwargs: None, "warning": lambda *args, **kwargs: None})(),
        )

        job = _AnalysisJob(
            stream_id="stream-1",
            segment_path="segments/seg_0002.mp4",
            alert_event="fire",
            frame_id=uuid.uuid4(),
            deep_prompt=(
                "Analyze the provided sequence of video frames chronologically for the threat."
            ),
            trigger_caption="Threat: Yes\nDescription: Visible smoke near the ATM.",
        )
        engine._analyze(job)

        assert "confirmed` field" in captured["prompt"]
        assert captured["prompt"].startswith("Return JSON with a boolean")
        assert "Threat Context: Visible smoke near the ATM." in captured["prompt"]
        assert "Analyze the provided sequence of video frames chronologically for the threat." in captured["prompt"]
