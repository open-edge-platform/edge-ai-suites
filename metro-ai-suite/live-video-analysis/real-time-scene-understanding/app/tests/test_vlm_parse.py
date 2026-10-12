# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for backend.services.vlm helpers."""

from __future__ import annotations

import pytest
from backend.services import utils
from backend.services import vlm
from backend.services.vlm import _build_alert_verdict_schema
from backend.services.vlm import _parse_alert_verdict
from backend.services.vlm import DeepAnalyzerVLMRuntime
from backend.services.vlm import VLMEngine
from backend.services.vlm import parse_yes_no


class _Stat:
    def __init__(self, mean):
        self.mean = mean
        self.std = 0.0


class _FakePerfMetrics:
    def __init__(self, ttft=1.0, tpot=2.0, throughput=3.0):
        self._ttft = ttft
        self._tpot = tpot
        self._throughput = throughput

    def get_load_time(self):
        return 0.0

    def get_num_generated_tokens(self):
        return 10

    def get_num_input_tokens(self):
        return 5

    def get_ttft(self):
        return _Stat(self._ttft)

    def get_tpot(self):
        return _Stat(self._tpot)

    def get_throughput(self):
        return _Stat(self._throughput)

    def get_inference_duration(self):
        return _Stat(0.0)

    def get_generate_duration(self):
        return _Stat(0.0)


class _BrokenPerfMetrics(_FakePerfMetrics):
    def get_ttft(self):
        raise RuntimeError("perf_metrics API drift")


class _FakeResult:
    def __init__(self, perf_metrics):
        self.perf_metrics = perf_metrics


class TestBuildAlertVerdictSchema:
    def test_schema_orders_description_before_decision(self):
        schema = _build_alert_verdict_schema(32)

        assert schema["type"] == "object"
        assert schema["required"] == ["description", "decision"]
        assert schema["additionalProperties"] is False
        assert schema["properties"]["decision"]["enum"] == ["Yes", "No"]

    def test_description_max_length_scales_with_token_budget(self):
        schema = _build_alert_verdict_schema(64)
        expected = max(64 - vlm._JSON_OVERHEAD_TOKENS, 5) * vlm._CHARS_PER_TOKEN

        assert schema["properties"]["description"]["maxLength"] == expected


class TestParseAlertVerdict:
    def test_extracts_valid_verdict_from_json(self):
        raw = '{"decision": "Yes", "description": "Person holding a box."}'

        assert _parse_alert_verdict(raw) == ("Yes", "Person holding a box.")

    def test_ignores_non_json_noise_around_valid_verdict(self):
        raw = '!! {"decision": "No", "description": "No suspicious activity."} !!'

        assert _parse_alert_verdict(raw) == ("No", "No suspicious activity.")

    def test_returns_none_for_partial_or_invalid_json(self):
        assert _parse_alert_verdict("{\"decision\": \"Yes\"") == (None, None)
        assert _parse_alert_verdict("not-json") == (None, None)
        assert _parse_alert_verdict('{"decision": "Maybe"}') == (None, None)

    def test_returns_none_when_json_decode_fails_inside_braces(self):
        assert _parse_alert_verdict("{oops}") == (None, None)

    def test_returns_none_when_json_is_not_object(self):
        assert _parse_alert_verdict('["decision", "Yes"]') == (None, None)


class TestFormatAlertCaption:
    def test_formats_a_valid_verdict(self):
        caption = VLMEngine._format_alert_caption('{"decision": "Yes", "description": "Person near shelf."}')

        assert caption == "Decision: Yes\nDescription: Person near shelf."

    def test_returns_none_for_incomplete_verdict(self):
        assert VLMEngine._format_alert_caption('{"decision": "Yes"}') is None
        assert VLMEngine._format_alert_caption("oops") is None


class TestExtractCaptionText:
    def test_uses_first_text_item_when_present(self):
        class _Result:
            texts = ["  Decision: Yes\nDescription: Person near shelf.  "]

        assert VLMEngine._extract_caption_text(_Result()) == "Decision: Yes\nDescription: Person near shelf."

    def test_falls_back_to_string_conversion_when_no_texts_list(self):
        class _Result:
            def __str__(self):
                return "  {\"decision\": \"No\", \"description\": \"Quiet scene\"}  "

        assert VLMEngine._extract_caption_text(_Result()) == '{"decision": "No", "description": "Quiet scene"}'


class TestParseYesNo:
    @pytest.mark.parametrize(
        "caption",
        [
            "Decision: Yes\nDescription: Person holding an item near shelf.",
            "  decision: yes\nDescription: Person holding an item near shelf.  ",
        ],
    )
    def test_recognizes_affirmative_captions(self, caption):
        assert parse_yes_no(caption) is True

    @pytest.mark.parametrize(
        "caption",
        [
            "Decision: No\nDescription: Regular shopping scene with no suspicious act.",
            "  decision: no\nDescription: Regular shopping scene with no suspicious act.  ",
        ],
    )
    def test_recognizes_negative_captions(self, caption):
        assert parse_yes_no(caption) is False

    @pytest.mark.parametrize(
        "caption",
        [
            "Maybe",
            "Unclear",
            "123",
            "",
            None,
            "Decision: Maybe\nDescription: A fuzzy scene.",
            "There is no direct evidence, but yes there is suspicious movement.",
        ],
    )
    def test_returns_none_for_ambiguous_captions(self, caption):
        assert parse_yes_no(caption) is None

    def test_prefers_decision_field_over_other_text(self):
        caption = "No obvious event. Decision: Yes\nDescription: Person conceals item in bag."
        assert parse_yes_no(caption) is True


class TestDeepAnalyzerVLMRuntimeHelpers:
    def test_model_path_uses_deep_analyzer_device_and_model(self, monkeypatch):
        monkeypatch.setattr(vlm.settings, "VLM_MODELS_DIR", "/models")
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_DEVICE", "NPU")
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_MODEL", "Qwen3.5-2B")

        assert DeepAnalyzerVLMRuntime.model_path() == "/models/npu/Qwen3.5-2B"

    @pytest.mark.parametrize("device", ["CPU", "NPU"])
    def test_build_pipeline_uses_expected_config(self, monkeypatch, device):
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_DEVICE", device)
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_NPU_MAX_PROMPT_LEN", 128)
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_NPU_MIN_RESPONSE_LEN", 16)
        monkeypatch.setattr(vlm.tempfile, "gettempdir", lambda: "/tmp")

        called = {}

        def fake_makedirs(path, exist_ok=False):
            called["cache_dir"] = path
            called["exist_ok"] = exist_ok

        class _Pipeline:
            def __init__(self, model_path, selected_device, **kwargs):
                called["args"] = (model_path, selected_device)
                called["kwargs"] = kwargs

        monkeypatch.setattr(vlm.os, "makedirs", fake_makedirs)
        monkeypatch.setattr(vlm.ov_genai, "VLMPipeline", _Pipeline)

        DeepAnalyzerVLMRuntime.build_pipeline("/models/deep")

        assert called["cache_dir"] == f"/tmp/{device.lower()}/vlm_cache"
        assert called["exist_ok"] is True
        assert called["args"] == ("/models/deep", device)
        if device == "CPU":
            assert called["kwargs"] == {"CACHE_DIR": "/tmp/cpu/vlm_cache"}
        else:
            assert called["kwargs"] == {"MAX_PROMPT_LEN": 128, "MIN_RESPONSE_LEN": 16}

    def test_build_generation_config_falls_back_when_defaults_unavailable(self, monkeypatch):
        class _Cfg:
            def __init__(self):
                self.max_new_tokens = 0
                self.min_new_tokens = 0
                self.num_beams = 0
                self.do_sample = False
                self.temperature = None
                self.top_p = None
                self.top_k = None
                self.repetition_penalty = 0.0
                self.no_repeat_ngram_size = 0
                self.apply_chat_template = False

        class _Pipe:
            def get_generation_config(self):
                raise RuntimeError("missing")

        monkeypatch.setattr(vlm.ov_genai, "GenerationConfig", _Cfg)
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_MAX_TOKENS", 64)
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_MIN_TOKENS", 12)
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_DO_SAMPLE", False)
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_REPETITION_PENALTY", 1.2)
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_NO_REPEAT_NGRAM_SIZE", 0)

        cfg = DeepAnalyzerVLMRuntime.build_generation_config(_Pipe())

        assert cfg.max_new_tokens == 64
        assert cfg.min_new_tokens == 12
        assert cfg.apply_chat_template is True
        assert cfg.repetition_penalty == 1.2

    def test_build_generation_config_sets_sampling_knobs(self, monkeypatch):
        class _Cfg:
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

        class _Pipe:
            def get_generation_config(self):
                return _Cfg()

        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_MAX_TOKENS", 80)
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_MIN_TOKENS", 20)
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_DO_SAMPLE", True)
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_TEMPERATURE", 0.3)
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_TOP_P", 0.7)
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_TOP_K", 40)
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_REPETITION_PENALTY", 1.1)
        monkeypatch.setattr(vlm.settings, "DEEP_ANALYZER_NO_REPEAT_NGRAM_SIZE", 3)

        cfg = DeepAnalyzerVLMRuntime.build_generation_config(_Pipe())

        assert cfg.do_sample is True
        assert cfg.temperature == 0.3
        assert cfg.top_p == 0.7
        assert cfg.top_k == 40
        assert cfg.no_repeat_ngram_size == 3

    def test_parse_analysis_result_handles_non_object_and_invalid_summary(self):
        assert DeepAnalyzerVLMRuntime.parse_analysis_result('["x"]') == (False, '["x"]')
        assert DeepAnalyzerVLMRuntime.parse_analysis_result('{"confirmed": true, "summary": "   "}') == (
            False,
            '{"confirmed": true, "summary": "   "}',
        )

    def test_extract_text_falls_back_to_string_repr(self):
        class _NoTexts:
            def __str__(self):
                return "  deep result  "

        assert DeepAnalyzerVLMRuntime.extract_text(_NoTexts()) == "deep result"


class TestExtractPerfMetrics:
    def test_returns_none_values_when_perf_metrics_missing(self):
        result = object()  # no `perf_metrics` attribute at all
        metrics = utils._extract_perf_metrics(result)
        assert metrics == {
            "ttft_ms": None,
            "tpot_ms": None,
            "throughput_tps": None,
            "total_tokens_generated": None,
        }

    def test_extracts_mean_values_from_perf_metrics(self):
        result = _FakeResult(_FakePerfMetrics(ttft=12.5, tpot=3.25, throughput=42.0))

        metrics = utils._extract_perf_metrics(result)

        assert metrics == {
            "ttft_ms": 12.5,
            "tpot_ms": 3.25,
            "throughput_tps": 42.0,
            "total_tokens_generated": 10.0,
        }

    def test_falls_back_to_none_when_accessors_raise(self):
        result = _FakeResult(_BrokenPerfMetrics())

        metrics = utils._extract_perf_metrics(result)

        assert metrics == {
            "ttft_ms": None,
            "tpot_ms": None,
            "throughput_tps": None,
            "total_tokens_generated": None,
        }
