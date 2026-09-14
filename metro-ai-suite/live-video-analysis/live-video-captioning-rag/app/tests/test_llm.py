# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.services.llm."""

from pathlib import Path
from types import ModuleType
import importlib.util
import sys


class _FakeConfig:
    def __init__(self):
        self.max_new_tokens = None


class _FakeLLM:
    def __init__(self):
        self.config = _FakeConfig()


def _load_llm_module(monkeypatch, llm_device="cpu"):
    backend_dir = Path(__file__).resolve().parents[1] / "backend"
    services_dir = backend_dir / "services"
    module_path = services_dir / "llm.py"

    backend_pkg = ModuleType("backend")
    backend_pkg.__path__ = [str(backend_dir)]

    services_pkg = ModuleType("backend.services")
    services_pkg.__path__ = [str(services_dir)]

    cfg_mod = ModuleType("backend.config")
    cfg_mod.APP_DISPLAY_NAME = "Test App"
    cfg_mod.DEBUG = False
    cfg_mod.LLM_MODEL_ID = "test-model"
    cfg_mod.LLM_DEVICE = llm_device
    cfg_mod.MAX_TOKENS = 64
    cfg_mod.CACHE_DIR = "/tmp/model_cache"
    cfg_mod.MAX_PROMPT_LEN = 4096

    calls = {}

    class _FakeOpenVINOLLM:
        @staticmethod
        def from_model_path(**kwargs):
            calls.update(kwargs)
            return _FakeLLM()

    ov_helper_mod = ModuleType("backend.integrations.ov_genai.ov_langchain_helper")
    ov_helper_mod.OpenVINOLLM = _FakeOpenVINOLLM

    monkeypatch.setitem(sys.modules, "backend", backend_pkg)
    monkeypatch.setitem(sys.modules, "backend.services", services_pkg)
    monkeypatch.setitem(sys.modules, "backend.config", cfg_mod)
    monkeypatch.setitem(sys.modules, "backend.integrations.ov_genai.ov_langchain_helper", ov_helper_mod)

    spec = importlib.util.spec_from_file_location("backend.services.llm", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules["backend.services.llm"] = module
    spec.loader.exec_module(module)
    return module, calls


def test_initialize_llm_sets_max_prompt_len_for_npu(monkeypatch):
    """On NPU, initialize_llm should pass MAX_PROMPT_LEN to OpenVINOLLM and set max_new_tokens."""
    mod, calls = _load_llm_module(monkeypatch, llm_device="NPU")
    llm = mod.initialize_llm()

    assert calls["model_path"] == "/tmp/model_cache/npu/test-model"
    assert calls["device"] == "NPU"
    assert calls["MAX_PROMPT_LEN"] == 4096
    assert llm.config.max_new_tokens == 64


def test_initialize_llm_skips_max_prompt_len_for_non_npu(monkeypatch):
    """For non-NPU devices, initialize_llm should not pass MAX_PROMPT_LEN to OpenVINOLLM."""
    mod, calls = _load_llm_module(monkeypatch, llm_device="cpu")
    llm = mod.initialize_llm()

    assert calls["model_path"] == "/tmp/model_cache/cpu/test-model"
    assert calls["device"] == "cpu"
    assert "MAX_PROMPT_LEN" not in calls
    assert llm.config.max_new_tokens == 64
