# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.services.embedding."""

from pathlib import Path
from types import ModuleType
import importlib.util
import sys

import pytest


class _FakeEmbeddingAPI:
    def __init__(self, api_url, model_name):
        self.api_url = api_url
        self.model_name = model_name

    def get_embedding_length(self):
        return 3


class _FakeVDMSClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port


class _FakeVDMS:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.add_calls = []
        self.retriever_calls = []

    def add_from(self, **kwargs):
        self.add_calls.append(kwargs)

    def as_retriever(self, **kwargs):
        self.retriever_calls.append(kwargs)
        return {"retriever": True}


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.headers = {}

    def post(self, *_args, **_kwargs):
        return _FakeResponse(self.payload)


def _load_embedding_module(monkeypatch):
    """Dynamically load the embedding module with dependencies mocked."""
    backend_dir = Path(__file__).resolve().parents[1] / "backend"
    services_dir = backend_dir / "services"
    module_path = services_dir / "embedding.py"

    backend_pkg = ModuleType("backend")
    backend_pkg.__path__ = [str(backend_dir)]

    services_pkg = ModuleType("backend.services")
    services_pkg.__path__ = [str(services_dir)]

    cfg_mod = ModuleType("backend.config")
    cfg_mod.EMBEDDING_HOST = "embedding-host"
    cfg_mod.EMBEDDING_HOST_PORT = 8000
    cfg_mod.EMBEDDING_MODEL = "embedding-model"
    cfg_mod.VDMS_HOST = "vdms-host"
    cfg_mod.VDMS_PORT = 55555
    cfg_mod.SCORE_THRESHOLD = 0.3
    cfg_mod.TOP_K = 1

    wrapper_mod = ModuleType("backend.services.embedding_wrapper")
    wrapper_mod.EmbeddingAPI = _FakeEmbeddingAPI

    vectorstores_mod = ModuleType("langchain_vdms.vectorstores")
    vectorstores_mod.VDMS = _FakeVDMS
    vectorstores_mod.VDMS_Client = _FakeVDMSClient

    langchain_vdms_mod = ModuleType("langchain_vdms")
    langchain_vdms_mod.vectorstores = vectorstores_mod

    monkeypatch.setitem(sys.modules, "backend", backend_pkg)
    monkeypatch.setitem(sys.modules, "backend.services", services_pkg)
    monkeypatch.setitem(sys.modules, "backend.config", cfg_mod)
    monkeypatch.setitem(sys.modules, "backend.services.embedding_wrapper", wrapper_mod)
    monkeypatch.setitem(sys.modules, "langchain_vdms", langchain_vdms_mod)
    monkeypatch.setitem(sys.modules, "langchain_vdms.vectorstores", vectorstores_mod)

    spec = importlib.util.spec_from_file_location("backend.services.embedding", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules["backend.services.embedding"] = module
    spec.loader.exec_module(module)
    return module


def test_build_embedding_metadata(monkeypatch):
    """Test that embedding metadata is correctly built from input."""
    mod = _load_embedding_module(monkeypatch)
    metadata = mod.CaptionEmbeddings._build_embedding_metadata(
        "imgblob", {"frame_id": 7, "img_format": "BGRA", "resolution": {"width": 1920, "height": 1080}}
    )
    assert metadata["frame_id"] == 7
    assert metadata["frame_format"] == "BGRA"
    assert metadata["frame_width"] == 1920
    assert metadata["frame_height"] == 1080
    assert metadata["frame_data"] == "imgblob"


def test_process_embeddings_success(monkeypatch):
    """Test the happy path of processing embeddings and adding to VDMS."""
    mod = _load_embedding_module(monkeypatch)
    monkeypatch.setattr(mod.requests, "Session", lambda: _FakeSession({"embedding": [0.1, 0.2, 0.3]}))

    svc = mod.CaptionEmbeddings()
    embedding_id = svc.process_embeddings("blob", {"result": "A person walking"})

    assert isinstance(embedding_id, str)
    assert svc.vdms_store.add_calls
    assert svc.vdms_store.add_calls[0]["texts"] == ["A person walking"]


def test_process_embeddings_requires_result(monkeypatch):
    """Test that a missing or empty 'result' field raises an error."""
    mod = _load_embedding_module(monkeypatch)
    monkeypatch.setattr(mod.requests, "Session", lambda: _FakeSession({"embedding": [0.1]}))

    svc = mod.CaptionEmbeddings()
    with pytest.raises(ValueError, match="required"):
        svc.process_embeddings("blob", {"result": "   "})


def test_process_embeddings_missing_embedding(monkeypatch):
    """Test that a missing 'embedding' field in the API response raises an error."""
    mod = _load_embedding_module(monkeypatch)
    monkeypatch.setattr(mod.requests, "Session", lambda: _FakeSession({"not_embedding": []}))

    svc = mod.CaptionEmbeddings()
    with pytest.raises(ValueError, match="Missing 'embedding'"):
        svc.process_embeddings("blob", {"result": "caption"})


def test_process_embeddings_invalid_embedding_type(monkeypatch):
    """Test that an invalid 'embedding' type in the API response raises an error."""
    mod = _load_embedding_module(monkeypatch)
    monkeypatch.setattr(mod.requests, "Session", lambda: _FakeSession({"embedding": "not-a-list"}))

    svc = mod.CaptionEmbeddings()
    with pytest.raises(TypeError, match="non-empty"):
        svc.process_embeddings("blob", {"result": "caption"})


def test_process_embeddings_retries_add_after_reinit(monkeypatch):
    """Test that if adding to VDMS fails, the service reinitializes and retries successfully."""
    mod = _load_embedding_module(monkeypatch)
    monkeypatch.setattr(mod.requests, "Session", lambda: _FakeSession({"embedding": [0.1, 0.2, 0.3]}))

    class _FailOnceVDMS(_FakeVDMS):
        has_failed = False

        def add_from(self, **kwargs):
            if not _FailOnceVDMS.has_failed:
                _FailOnceVDMS.has_failed = True
                raise RuntimeError("connection reset")
            return super().add_from(**kwargs)

    monkeypatch.setattr(mod, "VDMS", _FailOnceVDMS)

    svc = mod.CaptionEmbeddings()
    embedding_id = svc.process_embeddings("blob", {"result": "caption"})

    assert isinstance(embedding_id, str)
    assert svc.vdms_store.add_calls


def test_get_retriever_retries_on_failure(monkeypatch):
    """Test that if getting a retriever from VDMS fails, the service reinitializes and retries successfully."""
    mod = _load_embedding_module(monkeypatch)
    monkeypatch.setattr(mod.requests, "Session", lambda: _FakeSession({"embedding": [0.1, 0.2, 0.3]}))

    class _FailOnceVDMS(_FakeVDMS):
        has_failed = False

        def as_retriever(self, **kwargs):
            if not _FailOnceVDMS.has_failed:
                _FailOnceVDMS.has_failed = True
                raise RuntimeError("vdms timeout")
            return super().as_retriever(**kwargs)

    monkeypatch.setattr(mod, "VDMS", _FailOnceVDMS)

    svc = mod.CaptionEmbeddings()
    retriever = svc.get_retriever()
    assert retriever == {"retriever": True}


def test_reconnect_vdms_paths(monkeypatch):
    """Test that reconnecting VDMS calls the initialization method the correct number of times."""
    mod = _load_embedding_module(monkeypatch)
    monkeypatch.setattr(mod.requests, "Session", lambda: _FakeSession({"embedding": [0.1, 0.2, 0.3]}))

    svc = mod.CaptionEmbeddings()

    called = {"count": 0}

    def _count_init():
        called["count"] += 1

    monkeypatch.setattr(svc, "_init_vdms_store", _count_init)

    svc.reconnect_vdms()
    svc.reconnect_vdms(RuntimeError("boom"))

    assert called["count"] == 2
