# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for pure helpers in backend.services.deep_analyzer.

DeepAnalyzerEngine.__init__ loads a real VLM pipeline, so these tests only
exercise the module-level function and static method that don't require
instantiating the engine.
"""

from __future__ import annotations

import json
import os
import queue
import threading
import uuid
from collections import OrderedDict
from types import SimpleNamespace

import numpy as np
import pytest
from backend.services import deep_analyzer as deep_analyzer_module
from backend.services import vlm as vlm_module
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
        assert schema["properties"]["confirmed"]["type"] == "boolean"
        assert schema["properties"]["confirmed"]["description"]
        assert schema["properties"]["summary"]["type"] == "string"
        assert schema["properties"]["summary"]["description"]
        assert schema["properties"]["summary"]["minLength"] == 1
        expected_max = max(
            deep_analyzer_module.settings.DEEP_ANALYZER_MAX_TOKENS - vlm_module._JSON_OVERHEAD_TOKENS,
            5,
        ) * vlm_module._CHARS_PER_TOKEN
        assert schema["properties"]["summary"]["maxLength"] == expected_max

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
        assert "Context Event: Visible smoke near the ATM." in captured["prompt"]
        assert "Analyze the provided sequence of video frames chronologically for the threat." in captured["prompt"]

    def test_sample_segment_frames_with_known_total_uses_uniform_indices(self, monkeypatch):
        class _Frame:
            def __init__(self, idx):
                self.idx = idx

            def to_ndarray(self, format="rgb24"):
                assert format == deep_analyzer_module.settings.DEEP_ANALYZER_FRAME_FORMAT
                return np.array([[self.idx]], dtype="uint8")

        class _Container:
            def __init__(self):
                self.streams = SimpleNamespace(video=[SimpleNamespace(frames=5)])
                self.closed = False

            def decode(self, _stream):
                return [_Frame(i) for i in range(5)]

            def close(self):
                self.closed = True

        container = _Container()
        monkeypatch.setattr(deep_analyzer_module.av, "open", lambda _path: container)

        sampled = deep_analyzer_module._sample_segment_frames("segments/s.mp4", max_frames=3)

        assert sampled.shape == (3, 1, 1)
        assert {int(v[0][0]) for v in sampled.tolist()} == {0, 1, 3}
        assert container.closed is True

    def test_sample_segment_frames_without_metadata_decodes_all_then_trims(self, monkeypatch):
        class _Frame:
            def __init__(self, idx):
                self.idx = idx

            def to_ndarray(self, format="rgb24"):
                assert format == deep_analyzer_module.settings.DEEP_ANALYZER_FRAME_FORMAT
                return np.array([[self.idx]], dtype="uint8")

        class _Container:
            def __init__(self):
                self.streams = SimpleNamespace(video=[SimpleNamespace(frames=0)])

            def decode(self, _stream):
                return [_Frame(i) for i in range(6)]

            def close(self):
                return None

        monkeypatch.setattr(deep_analyzer_module.av, "open", lambda _path: _Container())

        sampled = deep_analyzer_module._sample_segment_frames("segments/s.mp4", max_frames=3)

        assert sampled.shape == (3, 1, 1)
        assert {int(v[0][0]) for v in sampled.tolist()} == {0, 2, 5}

    def test_sample_segment_frames_raises_when_empty(self, monkeypatch):
        class _Container:
            def __init__(self):
                self.streams = SimpleNamespace(video=[SimpleNamespace(frames=0)])

            def decode(self, _stream):
                return []

            def close(self):
                return None

        monkeypatch.setattr(deep_analyzer_module.av, "open", lambda _path: _Container())

        with pytest.raises(ValueError):
            deep_analyzer_module._sample_segment_frames("segments/empty.mp4", max_frames=3)

    def test_engine_init_initializes_dispatch_and_storage(self, monkeypatch):
        monkeypatch.setattr(DeepAnalyzerEngine, "_load", lambda self: None)
        started = {"called": False}

        class _Thread:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def start(self):
                started["called"] = True

        monkeypatch.setattr(deep_analyzer_module.threading, "Thread", _Thread)
        monkeypatch.setattr(deep_analyzer_module, "SeaweedFSStorage", lambda: "storage")

        engine = DeepAnalyzerEngine()

        assert started["called"] is True
        assert engine._dispatch_thread.kwargs["name"] == "deep-analyzer-dispatch"
        assert engine._object_storage == "storage"

    def test_load_raises_when_model_path_missing(self, monkeypatch):
        engine = object.__new__(DeepAnalyzerEngine)
        monkeypatch.setattr(deep_analyzer_module.DeepAnalyzerVLMRuntime, "model_path", lambda: "/missing/model")
        monkeypatch.setattr(deep_analyzer_module.os.path, "isdir", lambda _path: False)

        with pytest.raises(FileNotFoundError):
            engine._load()

    def test_load_builds_pipeline_and_generation_config(self, monkeypatch):
        engine = object.__new__(DeepAnalyzerEngine)
        monkeypatch.setattr(deep_analyzer_module.DeepAnalyzerVLMRuntime, "model_path", lambda: "/ok/model")
        monkeypatch.setattr(deep_analyzer_module.os.path, "isdir", lambda _path: True)
        monkeypatch.setattr(
            deep_analyzer_module.DeepAnalyzerVLMRuntime,
            "build_pipeline",
            lambda _path: "pipe",
        )
        monkeypatch.setattr(engine, "_build_generation_config", lambda: "cfg")

        engine._load()

        assert engine._pipe == "pipe"
        assert engine._gen_config == "cfg"

    def test_get_metrics_adds_active_count(self):
        engine = object.__new__(DeepAnalyzerEngine)
        engine._lock = threading.Lock()
        engine._stats = {"stream-1": {"submitted": 1, "queued": 2, "in_flight": 3, "completed": 4, "failed": 5, "max_in_flight": 3}}

        metrics = engine.get_metrics("stream-1")

        assert metrics["active"] == 5
        assert metrics["submitted"] == 1

    def test_submit_queues_immediately_when_segment_already_finalized(self):
        engine = object.__new__(DeepAnalyzerEngine)
        engine._lock = threading.Lock()
        engine._dedup = OrderedDict()
        engine._finalized = OrderedDict({"segments/default_segment_0006.mp4": None})
        engine._pending = {}
        engine._active = set()
        engine._stats = {}
        engine._queue = queue.Queue()

        engine.submit("stream-10", "segments/default_segment_0006.mp4", "smoke", uuid.uuid4())

        queued = engine._queue.get_nowait()
        assert queued.segment_path == "segments/default_segment_0006.mp4"
        assert not engine._pending

    def test_is_segment_active_reflects_active_set(self):
        engine = object.__new__(DeepAnalyzerEngine)
        engine._lock = threading.Lock()
        engine._active = {"segments/a.mp4"}

        assert engine.is_segment_active("segments/a.mp4") is True
        assert engine.is_segment_active("segments/b.mp4") is False

    def test_dispatch_loop_success_updates_stats_and_clears_active(self):
        engine = object.__new__(DeepAnalyzerEngine)
        engine._lock = threading.Lock()
        engine._stats = {"stream-1": {"submitted": 0, "queued": 1, "in_flight": 0, "completed": 0, "failed": 0, "max_in_flight": 0}}
        job = _AnalysisJob("stream-1", "segments/s1.mp4", "fire", uuid.uuid4())
        engine._active = {job.segment_path}

        class _Queue:
            def __init__(self):
                self.calls = 0

            def get(self):
                self.calls += 1
                if self.calls == 1:
                    return job
                raise StopIteration()

        engine._queue = _Queue()
        monkeypatch = pytest.MonkeyPatch()
        try:
            monkeypatch.setattr(engine, "_analyze", lambda _job: None)
            with pytest.raises(StopIteration):
                engine._dispatch_loop()
        finally:
            monkeypatch.undo()

        stats = engine._stream_stats("stream-1")
        assert stats["queued"] == 0
        assert stats["completed"] == 1
        assert stats["failed"] == 0
        assert stats["in_flight"] == 0
        assert stats["max_in_flight"] == 1
        assert job.segment_path not in engine._active

    def test_dispatch_loop_failure_tracks_failed_jobs(self):
        engine = object.__new__(DeepAnalyzerEngine)
        engine._lock = threading.Lock()
        engine._stats = {"stream-2": {"submitted": 0, "queued": 1, "in_flight": 0, "completed": 0, "failed": 0, "max_in_flight": 0}}
        job = _AnalysisJob("stream-2", "segments/s2.mp4", "fire", uuid.uuid4())
        engine._active = {job.segment_path}

        class _Queue:
            def __init__(self):
                self.calls = 0

            def get(self):
                self.calls += 1
                if self.calls == 1:
                    return job
                raise StopIteration()

        engine._queue = _Queue()
        monkeypatch = pytest.MonkeyPatch()
        try:
            monkeypatch.setattr(engine, "_analyze", lambda _job: (_ for _ in ()).throw(RuntimeError("boom")))
            with pytest.raises(StopIteration):
                engine._dispatch_loop()
        finally:
            monkeypatch.undo()

        stats = engine._stream_stats("stream-2")
        assert stats["completed"] == 0
        assert stats["failed"] == 1
        assert stats["in_flight"] == 0
        assert job.segment_path not in engine._active

    def test_read_segment_frames_retries_then_succeeds(self, monkeypatch):
        engine = object.__new__(DeepAnalyzerEngine)
        monkeypatch.setattr(engine, "_wait_for_next_segment", lambda _job: None)
        monkeypatch.setattr(deep_analyzer_module.settings, "DEEP_ANALYZER_SEGMENT_READ_MAX_RETRIES", 3)
        monkeypatch.setattr(deep_analyzer_module.settings, "DEEP_ANALYZER_SEGMENT_READ_RETRY_DELAY", 0.01)

        calls = {"n": 0}

        def fake_sample(_path, _max_frames):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("not ready")
            return np.array([[1]], dtype="uint8")

        sleeps = []
        monkeypatch.setattr(deep_analyzer_module, "_sample_segment_frames", fake_sample)
        monkeypatch.setattr(deep_analyzer_module.time, "sleep", lambda delay: sleeps.append(delay))

        frames = engine._read_segment_frames(
            _AnalysisJob("stream-1", "segments/s.mp4", "fire", uuid.uuid4())
        )

        assert frames.shape == (1, 1)
        assert calls["n"] == 3
        assert sleeps == [0.01, 0.01]

    def test_read_segment_frames_raises_after_max_retries(self, monkeypatch):
        engine = object.__new__(DeepAnalyzerEngine)
        monkeypatch.setattr(engine, "_wait_for_next_segment", lambda _job: None)
        monkeypatch.setattr(deep_analyzer_module.settings, "DEEP_ANALYZER_SEGMENT_READ_MAX_RETRIES", 2)
        monkeypatch.setattr(deep_analyzer_module.settings, "DEEP_ANALYZER_SEGMENT_READ_RETRY_DELAY", 0.01)
        monkeypatch.setattr(
            deep_analyzer_module,
            "_sample_segment_frames",
            lambda _path, _max_frames: (_ for _ in ()).throw(RuntimeError("bad segment")),
        )

        with pytest.raises(RuntimeError):
            engine._read_segment_frames(_AnalysisJob("stream-1", "segments/s.mp4", "fire", uuid.uuid4()))

    def test_wait_for_next_segment_returns_when_path_unavailable(self, monkeypatch):
        engine = object.__new__(DeepAnalyzerEngine)
        monkeypatch.setattr(deep_analyzer_module, "_next_segment_path", lambda _path: None)

        engine._wait_for_next_segment(_AnalysisJob("stream-1", "segments/s.mp4", "fire", uuid.uuid4()))

    def test_wait_for_next_segment_retries_then_gives_up(self, monkeypatch):
        engine = object.__new__(DeepAnalyzerEngine)
        monkeypatch.setattr(deep_analyzer_module, "_next_segment_path", lambda _path: "segments/s2.mp4")
        monkeypatch.setattr(deep_analyzer_module.settings, "DEEP_ANALYZER_SEGMENT_READ_MAX_RETRIES", 3)
        monkeypatch.setattr(deep_analyzer_module.settings, "DEEP_ANALYZER_SEGMENT_READ_RETRY_DELAY", 0.02)
        monkeypatch.setattr(deep_analyzer_module.os.path, "exists", lambda _path: False)
        sleeps = []
        monkeypatch.setattr(deep_analyzer_module.time, "sleep", lambda delay: sleeps.append(delay))

        engine._wait_for_next_segment(_AnalysisJob("stream-1", "segments/s1.mp4", "fire", uuid.uuid4()))

        assert sleeps == [0.02, 0.02]

    def test_wait_for_next_segment_returns_when_next_exists(self, monkeypatch):
        engine = object.__new__(DeepAnalyzerEngine)
        monkeypatch.setattr(deep_analyzer_module, "_next_segment_path", lambda _path: "segments/s2.mp4")
        monkeypatch.setattr(deep_analyzer_module.settings, "DEEP_ANALYZER_SEGMENT_READ_MAX_RETRIES", 3)
        monkeypatch.setattr(deep_analyzer_module.os.path, "exists", lambda _path: True)

        engine._wait_for_next_segment(_AnalysisJob("stream-1", "segments/s1.mp4", "fire", uuid.uuid4()))

    def test_get_deep_analyzer_lazy_singleton(self, monkeypatch):
        class _FakeEngine:
            pass

        deep_analyzer_module._engine = None
        monkeypatch.setattr(deep_analyzer_module, "DeepAnalyzerEngine", _FakeEngine)

        first = deep_analyzer_module.get_deep_analyzer()
        second = deep_analyzer_module.get_deep_analyzer()

        assert isinstance(first, _FakeEngine)
        assert first is second
