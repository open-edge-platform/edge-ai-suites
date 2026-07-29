# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.llm."""

from pathlib import Path
from types import ModuleType
import importlib.util
import sys


class _FakeTokenizer:
    def __init__(self, eos_token_id):
        self.eos_token_id = eos_token_id
        self.pad_token_id = None


class _FakePipelineInner:
    def __init__(self, eos_token_id):
        self.tokenizer = _FakeTokenizer(eos_token_id)


class _FakeLLM:
    def __init__(self, eos_token_id):
        self.pipeline = _FakePipelineInner(eos_token_id)


def _load_llm_module(monkeypatch, eos_token_id=42):
    backend_dir = Path(__file__).resolve().parents[1] / "backend"
    module_path = backend_dir / "llm.py"

    backend_pkg = ModuleType("backend")
    backend_pkg.__path__ = [str(backend_dir)]

    cfg_mod = ModuleType("backend.config")
    cfg_mod.LLM_MODEL_ID = "test-model"
    cfg_mod.LLM_DEVICE = "cpu"
    cfg_mod.MAX_TOKENS = 64
    cfg_mod.CACHE_DIR = "/tmp/model_cache"

    calls = {}

    class _FakeHFPipeline:
        @staticmethod
        def from_model_id(**kwargs):
            calls.update(kwargs)
            return _FakeLLM(eos_token_id=eos_token_id)

    lchf_mod = ModuleType("langchain_huggingface")
    lchf_mod.HuggingFacePipeline = _FakeHFPipeline

    monkeypatch.setitem(sys.modules, "backend", backend_pkg)
    monkeypatch.setitem(sys.modules, "backend.config", cfg_mod)
    monkeypatch.setitem(sys.modules, "langchain_huggingface", lchf_mod)

    spec = importlib.util.spec_from_file_location("backend.llm", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules["backend.llm"] = module
    spec.loader.exec_module(module)
    return module, calls


def test_initialize_llm_sets_pad_token_from_eos(monkeypatch):
    """If the tokenizer has an eos_token_id, initialize_llm should set the pad_token_id to the same value."""
    mod, calls = _load_llm_module(monkeypatch, eos_token_id=5)
    llm = mod.initialize_llm()

    assert calls["task"] == "text-generation"
    assert calls["backend"] == "openvino"
    assert calls["pipeline_kwargs"] == {"max_new_tokens": 64}
    assert llm.pipeline.tokenizer.pad_token_id == 5


def test_initialize_llm_does_not_set_pad_token_when_eos_missing(monkeypatch):
    """If the tokenizer does not have an eos_token_id, initialize_llm should not set the pad_token_id."""
    mod, _calls = _load_llm_module(monkeypatch, eos_token_id=0)
    llm = mod.initialize_llm()
    assert llm.pipeline.tokenizer.pad_token_id is None
