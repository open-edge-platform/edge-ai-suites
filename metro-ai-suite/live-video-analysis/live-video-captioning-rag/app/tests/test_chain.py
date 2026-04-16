# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.services.chain retry and stream behavior."""

from pathlib import Path
from types import ModuleType
import importlib.util
import sys
import pytest


class _DummyLogger:
    def warning(self, *_args, **_kwargs):
        return None


class _DummyCaptionEmbeddings:
    def __init__(self):
        self.reconnect_calls = []

    def get_retriever(self):
        return None

    def reconnect_vdms(self, exc=None):
        self.reconnect_calls.append(exc)


class _Doc:
    def __init__(self, page_content, metadata):
        self.page_content = page_content
        self.metadata = metadata


def _load_chain_module(monkeypatch):
    """Load chain.py with lightweight stubs to prevent model initialization."""
    backend_dir = Path(__file__).resolve().parents[1] / "backend"
    services_dir = backend_dir / "services"
    module_path = services_dir / "chain.py"

    backend_pkg = ModuleType("backend")
    backend_pkg.__path__ = [str(backend_dir)]

    services_pkg = ModuleType("backend.services")
    services_pkg.__path__ = [str(services_dir)]

    cfg_mod = ModuleType("backend.config")
    cfg_mod.LLM_MODEL_ID = "test-llm"

    llm_mod = ModuleType("backend.llm")
    llm_mod.initialize_llm = lambda: object()

    prompt_mod = ModuleType("backend.services.prompt")
    prompt_mod.get_prompt_template = lambda _model_id: "Context: {context} Question: {question}"

    embedding_mod = ModuleType("backend.services.embedding")
    embedding_mod.CaptionEmbeddings = _DummyCaptionEmbeddings

    logger_mod = ModuleType("backend.logger")
    logger_mod.logger = _DummyLogger()

    monkeypatch.setitem(sys.modules, "backend", backend_pkg)
    monkeypatch.setitem(sys.modules, "backend.services", services_pkg)
    monkeypatch.setitem(sys.modules, "backend.config", cfg_mod)
    monkeypatch.setitem(sys.modules, "backend.llm", llm_mod)
    monkeypatch.setitem(sys.modules, "backend.services.prompt", prompt_mod)
    monkeypatch.setitem(sys.modules, "backend.services.embedding", embedding_mod)
    monkeypatch.setitem(sys.modules, "backend.logger", logger_mod)

    spec = importlib.util.spec_from_file_location("backend.services.chain", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules["backend.services.chain"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_process_query_retries_after_vdms_error(monkeypatch):
    """If the chain raises a retryable VDMS error, the chain is retried and the caption embeddings reconnect method is called."""
    mod = _load_chain_module(monkeypatch)

    class _FailingChain:
        async def astream(self, _query):
            raise RuntimeError("vdms connection reset by peer")
            yield

    class _RetryChain:
        async def astream(self, _query):
            yield {"source_documents": [_Doc("caption one", {"frame_id": 1})]}
            yield {"answer": "ok"}

    mod.build_chain = lambda: _RetryChain()

    events = []
    async for item in mod.process_query(chain=_FailingChain(), query="what happened"):
        events.append(item)

    assert any("data: ok" in event for event in events)
    assert any("event: frame" in event for event in events)
    assert mod.caption_embeddings.reconnect_calls


@pytest.mark.asyncio
async def test_process_query_does_not_retry_after_partial_answer(monkeypatch):
    """
    If the chain yields a partial answer and then raises a retryable VDMS error,
    the error is raised and the caption embeddings reconnect method is not called (because we don't want to lose the partial answer).
    """
    mod = _load_chain_module(monkeypatch)

    class _PartialThenErrorChain:
        async def astream(self, _query):
            yield {"answer": "partial"}
            raise RuntimeError("vdms timed out")

    with pytest.raises(RuntimeError):
        async for _item in mod.process_query(chain=_PartialThenErrorChain(), query="q"):
            pass

    assert mod.caption_embeddings.reconnect_calls == []


def test_is_vdms_retryable_error_positive(monkeypatch):
    """Errors that indicate a VDMS connection issue should be considered retryable."""
    mod = _load_chain_module(monkeypatch)
    assert mod._is_vdms_retryable_error(RuntimeError("socket timeout talking to vdms")) is True


def test_is_vdms_retryable_error_negative(monkeypatch):
    """Errors that do not indicate a VDMS connection issue should not be considered retryable."""
    mod = _load_chain_module(monkeypatch)
    assert mod._is_vdms_retryable_error(RuntimeError("validation failed")) is False
