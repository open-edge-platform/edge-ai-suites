# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import sys
from unittest.mock import MagicMock, patch

_SC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SC_ROOT not in sys.path:
    sys.path.insert(0, _SC_ROOT)

from components.summarizer_component import SummarizerComponent
from utils.config_loader import config


def _make_component(handler):
    """Build a SummarizerComponent with ModelManager.text_gen() -> handler."""
    with patch("components.summarizer_component.ModelManager") as mock_mm:
        mock_mm.instance.return_value.text_gen.return_value = handler
        component = SummarizerComponent(
            session_id="test-session",
            provider="openvino",
            model_name="Qwen/Qwen3-8B",
            device="GPU",
            temperature=0.0,
            mode="dialog",
        )
    return component, mock_mm


def test_summarizer_uses_model_manager_text_gen():
    handler = MagicMock(name="text_gen_handler")
    component, mock_mm = _make_component(handler)

    mock_mm.instance.assert_called_once_with()
    mock_mm.instance.return_value.text_gen.assert_called_once_with()
    assert component.summarizer is handler


def test_summarizer_metadata_reflects_text_gen_config():
    handler = MagicMock(name="text_gen_handler")
    component, _ = _make_component(handler)
    assert component.provider == config.models.text_gen.provider
    assert component.model_name == config.models.text_gen.vlm_name


def test_summarizer_shares_singleton_handler():
    handler = MagicMock(name="text_gen_handler")

    with patch("components.summarizer_component.ModelManager") as mock_mm:
        mock_mm.instance.return_value.text_gen.return_value = handler
        first = SummarizerComponent("s1", "openvino", "m", "GPU", mode="dialog")
        second = SummarizerComponent("s2", "openvino", "m", "GPU", mode="teacher")

    assert first.summarizer is second.summarizer is handler
