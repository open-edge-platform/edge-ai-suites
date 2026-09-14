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
        self.process_calls = []

    def get_retriever(self):
        return None

    def process_embeddings(self, image_data, metadata):
        self.process_calls.append((image_data, metadata))
        return "dummy-id"

    def reconnect_vdms(self, exc=None):
        self.reconnect_calls.append(exc)


class _Doc:
    def __init__(self, page_content, metadata):
        self.page_content = page_content
        self.metadata = metadata


class _PipeExpr:
    """Simple pipeable expression used to stub runnable composition."""

    def __init__(self, name):
        self.name = name

    def __or__(self, other):
        other_name = getattr(other, "name", other.__class__.__name__)
        return _PipeExpr(f"{self.name}|{other_name}")


class _FakeRunnableParallel:
    def __init__(self, mapping):
        self.mapping = mapping
        self.assigned = {}

    def assign(self, **kwargs):
        self.assigned.update(kwargs)
        return self


class _FakeChain:
    def __init__(self, chunks=None, err=None):
        self._chunks = chunks or []
        self._err = err

    async def astream(self, _query):
        for chunk in self._chunks:
            yield chunk
        if self._err is not None:
            raise self._err


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

    llm_mod = ModuleType("backend.services.llm")
    llm_mod.initialize_llm = lambda: object()

    prompt_mod = ModuleType("backend.services.prompt")
    prompt_mod.get_prompt_template = lambda _model_id: "Context: {context} Question: {question}"

    embedding_mod = ModuleType("backend.services.embedding")
    embedding_mod.CaptionEmbeddings = _DummyCaptionEmbeddings

    logger_mod = ModuleType("backend.utils.logger")
    logger_mod.logger = _DummyLogger()

    monkeypatch.setitem(sys.modules, "backend", backend_pkg)
    monkeypatch.setitem(sys.modules, "backend.services", services_pkg)
    monkeypatch.setitem(sys.modules, "backend.config", cfg_mod)
    monkeypatch.setitem(sys.modules, "backend.services.llm", llm_mod)
    monkeypatch.setitem(sys.modules, "backend.services.prompt", prompt_mod)
    monkeypatch.setitem(sys.modules, "backend.services.embedding", embedding_mod)
    monkeypatch.setitem(sys.modules, "backend.utils.logger", logger_mod)

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


@pytest.mark.asyncio
async def test_process_embeddings_delegates_to_thread(monkeypatch):
    """process_embeddings should delegate sync work to asyncio.to_thread."""
    mod = _load_chain_module(monkeypatch)

    calls = {}

    async def _fake_to_thread(fn, image_data, metadata):
        calls["fn"] = fn
        calls["image_data"] = image_data
        calls["metadata"] = metadata
        return "fake-id"

    monkeypatch.setattr(mod.asyncio, "to_thread", _fake_to_thread)

    result = await mod.process_embeddings("img", {"result": "caption"})

    assert result == "fake-id"
    assert calls["fn"] == mod.caption_embeddings.process_embeddings
    assert calls["image_data"] == "img"
    assert calls["metadata"] == {"result": "caption"}


def test_default_context_returns_empty_string(monkeypatch):
    """default_context should always return an empty string."""
    mod = _load_chain_module(monkeypatch)
    assert mod.default_context([_Doc("x", {})]) == ""


def test_format_docs_joins_page_content(monkeypatch):
    """format_docs should join each document page_content with blank lines."""
    mod = _load_chain_module(monkeypatch)
    docs = [_Doc("first", {}), _Doc("second", {})]
    assert mod.format_docs(docs) == "first\n\nsecond"


def test_build_chain_with_retriever(monkeypatch):
    """build_chain should include source_documents input when retriever exists."""
    mod = _load_chain_module(monkeypatch)

    fake_prompt = _PipeExpr("prompt")
    fake_llm = _PipeExpr("llm")

    monkeypatch.setattr(mod, "prompt", fake_prompt)
    monkeypatch.setattr(mod, "llm", fake_llm)
    monkeypatch.setattr(mod, "RunnableParallel", _FakeRunnableParallel)
    monkeypatch.setattr(mod, "RunnablePassthrough", lambda: "PASSTHROUGH")
    monkeypatch.setattr(mod, "StrOutputParser", lambda: _PipeExpr("parser"))
    monkeypatch.setattr(mod.caption_embeddings, "get_retriever", lambda: "RETRIEVER")

    chain = mod.build_chain()

    assert isinstance(chain, _FakeRunnableParallel)
    assert chain.mapping["source_documents"] == "RETRIEVER"
    assert chain.mapping["question"] == "PASSTHROUGH"
    assert "context" in chain.assigned
    assert chain.assigned["context"]({"source_documents": [_Doc("ctx", {})]}) == "ctx"
    assert chain.assigned["answer"].name == "prompt|llm|parser"


def test_build_chain_without_retriever(monkeypatch):
    """build_chain should create an empty-context path when retriever is missing."""
    mod = _load_chain_module(monkeypatch)

    fake_prompt = _PipeExpr("prompt")
    fake_llm = _PipeExpr("llm")

    monkeypatch.setattr(mod, "prompt", fake_prompt)
    monkeypatch.setattr(mod, "llm", fake_llm)
    monkeypatch.setattr(mod, "RunnableParallel", _FakeRunnableParallel)
    monkeypatch.setattr(mod, "RunnablePassthrough", lambda: "PASSTHROUGH")
    monkeypatch.setattr(mod, "StrOutputParser", lambda: _PipeExpr("parser"))
    monkeypatch.setattr(mod.caption_embeddings, "get_retriever", lambda: None)

    chain = mod.build_chain()

    assert isinstance(chain, _FakeRunnableParallel)
    assert "source_documents" not in chain.mapping
    assert chain.mapping["question"] == "PASSTHROUGH"
    assert chain.assigned["context"]({"unused": True}) == ""
    assert chain.assigned["answer"].name == "prompt|llm|parser"


@pytest.mark.asyncio
async def test_process_query_builds_chain_when_none(monkeypatch):
    """process_query should call build_chain when chain argument is omitted."""
    mod = _load_chain_module(monkeypatch)

    chain = _FakeChain(
        chunks=[
            {"source_documents": [_Doc("caption one", {"frame_id": 9})]},
            {"answer": "hello"},
        ]
    )
    monkeypatch.setattr(mod, "build_chain", lambda: chain)

    events = []
    async for item in mod.process_query(query="what"):
        events.append(item)

    assert "data: hello\n\n" in events
    assert "event: frame\n" in events
    assert any('"frame_id": 9' in event for event in events)


@pytest.mark.asyncio
async def test_process_query_raises_non_retryable_error(monkeypatch):
    """Non-retryable errors should be raised without reconnect attempts."""
    mod = _load_chain_module(monkeypatch)

    failing_chain = _FakeChain(err=RuntimeError("validation failed"))

    with pytest.raises(RuntimeError, match="validation failed"):
        async for _item in mod.process_query(chain=failing_chain, query="q"):
            pass

    assert mod.caption_embeddings.reconnect_calls == []
