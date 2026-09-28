# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for VLMEngine request and generation behavior."""

from __future__ import annotations

import numpy as np
import pytest

from backend.services import vlm
from backend.services.vlm import VLMEngine


class TestVLMGenerate:
    def test_generate_batches_frame_and_formats_result(self, monkeypatch):
        engine = object.__new__(VLMEngine)
        captured = {}

        class _Tensor:
            def __init__(self, value):
                captured["tensor"] = value

        class _Result:
            texts = ['{"decision": "Yes", "description": "Person near door."}']

        class _Pipe:
            def generate(self, prompt, images, generation_config):
                captured["prompt"] = prompt
                captured["images"] = images
                captured["config"] = generation_config
                return _Result()

        monkeypatch.setattr(vlm.ov, "Tensor", _Tensor)
        monkeypatch.setattr(vlm.utils, "_extract_perf_metrics", lambda result: {"ttft_ms": 4.0})
        engine._pipe = _Pipe()
        engine._gen_config = object()
        engine._metrics_debug_logged = False

        caption, metrics = engine._generate(np.zeros((2, 3, 3), dtype="uint8"), "watch the door")

        assert caption == "Decision: Yes\nDescription: Person near door."
        assert metrics == {"ttft_ms": 4.0}
        assert captured["prompt"] == "watch the door" + vlm._RESPONSE_FORMAT_SUFFIX
        assert captured["tensor"].shape == (1, 2, 3, 3)
        assert captured["images"]

    def test_generate_returns_none_for_malformed_result(self, monkeypatch):
        engine = object.__new__(VLMEngine)
        engine._pipe = type(
            "Pipe",
            (),
            {"generate": lambda self, *args, **kwargs: type("Result", (), {"texts": ["truncated"]})()},
        )()
        engine._gen_config = object()
        engine._metrics_debug_logged = False
        monkeypatch.setattr(vlm.ov, "Tensor", lambda value: value)
        monkeypatch.setattr(vlm.utils, "_extract_perf_metrics", lambda result: {"ttft_ms": 1.0})

        caption, _metrics = engine._generate(np.zeros((1, 1, 3), dtype="uint8"), "prompt")

        assert caption is None

    def test_generate_logs_missing_metrics_only_once(self, monkeypatch):
        engine = object.__new__(VLMEngine)
        engine._pipe = type(
            "Pipe",
            (),
            {"generate": lambda self, *args, **kwargs: type("Result", (), {"texts": ["bad"]})()},
        )()
        engine._gen_config = object()
        engine._metrics_debug_logged = False
        monkeypatch.setattr(vlm.ov, "Tensor", lambda value: value)
        monkeypatch.setattr(vlm.utils, "_extract_perf_metrics", lambda result: {"ttft_ms": None})
        warning = []
        monkeypatch.setattr(vlm.logger, "warning", lambda *args, **kwargs: warning.append(args))

        engine._generate(np.zeros((1, 1, 3), dtype="uint8"), "prompt")
        engine._generate(np.zeros((1, 1, 3), dtype="uint8"), "prompt")

        assert len(warning) == 1


class TestVLMLoading:
    def test_load_rejects_missing_model(self, monkeypatch):
        engine = object.__new__(VLMEngine)
        engine._model_path = "/missing/model"
        monkeypatch.setattr(vlm.os.path, "isdir", lambda path: False)

        with pytest.raises(FileNotFoundError, match="VLM model not found"):
            engine._load()

    @pytest.mark.parametrize("device", ["CPU", "NPU"])
    def test_load_builds_pipeline_for_device(self, monkeypatch, device):
        engine = object.__new__(VLMEngine)
        engine._model_path = "/models/cpu/model"
        calls = {}

        class _Config:
            do_sample = False

        class _Pipeline:
            def __init__(self, *args, **kwargs):
                calls["args"] = args
                calls["kwargs"] = kwargs

        class _Structured:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        monkeypatch.setattr(vlm.os.path, "isdir", lambda path: True)
        monkeypatch.setattr(vlm.settings, "ALERT_VLM_DEVICE", device)
        monkeypatch.setattr(vlm.settings, "ALERT_VLM_MODEL", "model")
        monkeypatch.setattr(vlm.settings, "ALERT_VLM_MAX_TOKENS", 32)
        monkeypatch.setattr(vlm.settings, "ALERT_VLM_DO_SAMPLE", True)
        monkeypatch.setattr(vlm.settings, "NPU_MAX_PROMPT_LEN", 100)
        monkeypatch.setattr(vlm.settings, "NPU_MIN_RESPONSE_LEN", 10)
        monkeypatch.setattr(vlm.ov_genai, "VLMPipeline", _Pipeline)
        monkeypatch.setattr(vlm.ov_genai, "GenerationConfig", _Config)
        monkeypatch.setattr(vlm.ov_genai, "StructuredOutputConfig", _Structured)

        engine._load()

        assert calls["args"] == (engine._model_path, device)
        if device == "CPU":
            assert calls["kwargs"] == {}
        else:
            assert calls["kwargs"] == {"MAX_PROMPT_LEN": 100, "MIN_RESPONSE_LEN": 10}
        assert engine._gen_config.max_new_tokens == 32
        assert engine._gen_config.do_sample is True

    def test_constructor_loads_and_starts_dispatcher(self, monkeypatch):
        loaded = []
        started = []
        monkeypatch.setattr(VLMEngine, "_load", lambda self: loaded.append(True))

        class _Thread:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def start(self):
                started.append(self.kwargs["name"])

        monkeypatch.setattr(vlm.threading, "Thread", _Thread)

        engine = VLMEngine()

        assert loaded == [True]
        assert started == ["vlm-dispatch"]
        assert engine._metrics_debug_logged is False

    def test_get_vlm_engine_returns_cached_instance(self, monkeypatch):
        sentinel = object()
        monkeypatch.setattr(vlm, "_engine", sentinel)

        assert vlm.get_vlm_engine() is sentinel


class TestVLMRequestAPI:
    def test_caption_with_metrics_rejects_blank_prompt(self):
        engine = object.__new__(VLMEngine)

        with pytest.raises(ValueError, match="prompt is required"):
            engine.caption_with_metrics(np.zeros((1, 1, 3), dtype="uint8"), prompt="  ")

    def test_caption_delegates_to_caption_with_metrics(self, monkeypatch):
        engine = object.__new__(VLMEngine)
        captured = {}

        def fake_caption(frame, prompt=None):
            captured["frame"] = frame
            captured["prompt"] = prompt
            return "Decision: No\nDescription: Quiet. ", {"ttft_ms": 2.0}

        monkeypatch.setattr(engine, "caption_with_metrics", fake_caption)
        frame = np.zeros((2, 2, 3), dtype="uint8")

        assert engine.caption(frame, prompt=" scene ") == "Decision: No\nDescription: Quiet. "
        assert captured == {"frame": frame, "prompt": " scene "}

    def test_caption_with_metrics_queues_priority_request(self, monkeypatch):
        engine = object.__new__(VLMEngine)
        captured = {}

        class _Queue:
            def put(self, item):
                captured["item"] = item
                item[2].result = ("Decision: Yes\nDescription: Alert.", {"ttft_ms": 1.0})
                item[2].event.set()

        engine._queue = _Queue()
        engine._seq_counter = iter([7])
        frame = np.zeros((1, 1, 3), dtype="uint8")

        result = engine.caption_with_metrics(frame, prompt=" prompt ", priority=True)

        assert result[0].startswith("Decision: Yes")
        assert captured["item"][:2] == (0, 7)

    def test_dispatch_loop_records_generation_error(self):
        engine = object.__new__(VLMEngine)

        class _Request:
            rgb_frame = "frame"
            prompt = "prompt"
            result = None
            error = None

            class _Event:
                def __init__(self):
                    self.was_set = False

                def set(self):
                    self.was_set = True

            event = _Event()

        request = _Request()

        class _Queue:
            def __init__(self):
                self.calls = 0

            def get(self):
                self.calls += 1
                if self.calls == 1:
                    return 0, 0, request
                raise KeyboardInterrupt

        engine._queue = _Queue()
        engine._generate = lambda frame, prompt: (_ for _ in ()).throw(RuntimeError("generation failed"))

        with pytest.raises(KeyboardInterrupt):
            engine._dispatch_loop()

        assert isinstance(request.error, RuntimeError)
        assert request.event.was_set is True