# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.services.prompt."""

import importlib.util
from pathlib import Path


def _load_prompt_module():
    # Load prompt.py directly to avoid importing backend.services package side effects.
    module_path = Path(__file__).resolve().parents[1] / "backend" / "services" / "prompt.py"
    spec = importlib.util.spec_from_file_location("prompt_for_tests", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestGetPromptTemplate:
    """Prompt selection logic for known and unknown model IDs."""

    def test_known_model_returns_specific_template(self):
        """A known model ID returns a template containing expected placeholders."""
        prompt_module = _load_prompt_module()
        template = prompt_module.get_prompt_template("Intel/neural-chat-7b-v3-3")
        assert "### System:" in template
        assert "{context}" in template
        assert "{question}" in template

    def test_unknown_model_returns_default_template(self):
        """An unknown model ID falls back to the default RAG prompt template."""
        prompt_module = _load_prompt_module()
        template = prompt_module.get_prompt_template("unknown/model")
        assert template == prompt_module.default_rag_prompt_template
