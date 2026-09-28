# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for backend.services.vlm helpers."""

from __future__ import annotations

import pytest
from backend.services import vlm
from backend.services.vlm import _build_alert_verdict_schema
from backend.services.vlm import _parse_alert_verdict
from backend.services.vlm import VLMEngine
from backend.services.vlm import parse_yes_no


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
