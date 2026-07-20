# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests that SummarizerComponent routes generation through the shared warm
``text_gen`` VLM managed by ModelManager, instead of loading its own LLM."""

import os
import sys
from unittest.mock import MagicMock, patch

# Ensure the smart-classroom root is importable when tests are run from a
# subdirectory (mirrors model_manager/test/test_model_manager.py).
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

    # The component must borrow the singleton text_gen handler, not build a model.
    mock_mm.instance.assert_called_once_with()
    mock_mm.instance.return_value.text_gen.assert_called_once_with()
    assert component.summarizer is handler


def test_summarizer_metadata_reflects_text_gen_config():
    handler = MagicMock(name="text_gen_handler")
    component, _ = _make_component(handler)

    # provider/model_name are reported from config.models.text_gen (the actual
    # model that generates), not the legacy summarizer constructor args.
    assert component.provider == config.models.text_gen.provider
    assert component.model_name == config.models.text_gen.vlm_name


def test_summarizer_shares_singleton_handler():
    handler = MagicMock(name="text_gen_handler")

    with patch("components.summarizer_component.ModelManager") as mock_mm:
        mock_mm.instance.return_value.text_gen.return_value = handler
        first = SummarizerComponent("s1", "openvino", "m", "GPU", mode="dialog")
        second = SummarizerComponent("s2", "openvino", "m", "GPU", mode="teacher")

    # Both components resolve to the same warm handler instance.
    assert first.summarizer is second.summarizer is handler
