# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.services.embedding_wrapper."""

from pathlib import Path
from types import ModuleType
import importlib.util
import sys


class _DummyLogger:
    def debug(self, *_args, **_kwargs):
        return None


def _load_embedding_wrapper_module(monkeypatch, embedding_length=0, no_proxy_value=""):
    """Load embedding_wrapper.py with minimal package stubs to avoid side effects."""
    backend_dir = Path(__file__).resolve().parents[1] / "backend"
    services_dir = backend_dir / "services"
    module_path = services_dir / "embedding_wrapper.py"

    backend_pkg = ModuleType("backend")
    backend_pkg.__path__ = [str(backend_dir)]

    services_pkg = ModuleType("backend.services")
    services_pkg.__path__ = [str(services_dir)]

    cfg_mod = ModuleType("backend.config")
    cfg_mod.EMBEDDING_LENGTH = embedding_length

    logger_mod = ModuleType("backend.logger")
    logger_mod.logger = _DummyLogger()

    if no_proxy_value is not None:
        monkeypatch.setenv("no_proxy", no_proxy_value)

    monkeypatch.setitem(sys.modules, "backend", backend_pkg)
    monkeypatch.setitem(sys.modules, "backend.services", services_pkg)
    monkeypatch.setitem(sys.modules, "backend.config", cfg_mod)
    monkeypatch.setitem(sys.modules, "backend.logger", logger_mod)

    spec = importlib.util.spec_from_file_location("backend.services.embedding_wrapper", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules["backend.services.embedding_wrapper"] = module
    spec.loader.exec_module(module)
    return module


class TestNoProxySelection:
    """Unit tests for proxy bypass logic."""

    def test_should_use_no_proxy_true_for_matching_domain(self, monkeypatch):
        mod = _load_embedding_wrapper_module(monkeypatch, no_proxy_value="localhost,.svc")
        assert mod.should_use_no_proxy("http://service.namespace.svc/v1") is True

    def test_should_use_no_proxy_false_for_non_matching_domain(self, monkeypatch):
        mod = _load_embedding_wrapper_module(monkeypatch, no_proxy_value="localhost,.svc")
        assert mod.should_use_no_proxy("http://example.com/v1") is False


class TestEmbeddingAPI:
    """Behavior tests for embedding API client."""

    def test_post_embeddings_wraps_1d_vector(self, monkeypatch):
        """The API should accept both 1D and 2D vectors, wrapping 1D in an outer list."""
        mod = _load_embedding_wrapper_module(monkeypatch)

        class _Response:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"embedding": [0.1, 0.2, 0.3]}

        monkeypatch.setattr(mod.requests, "post", lambda *_a, **_kw: _Response())

        api = mod.EmbeddingAPI(api_url="http://embeddings:8000/embeddings", model_name="m")
        result = api.embed_documents(["hello"])
        assert result == [[0.1, 0.2, 0.3]]

    def test_embed_query_returns_first_vector(self, monkeypatch):
        """The API should return the first vector for a query."""
        mod = _load_embedding_wrapper_module(monkeypatch)

        class _Response:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"embedding": [[1.0, 2.0], [3.0, 4.0]]}

        monkeypatch.setattr(mod.requests, "post", lambda *_a, **_kw: _Response())

        api = mod.EmbeddingAPI(api_url="http://embeddings:8000/embeddings", model_name="m")
        assert api.embed_query("query") == [1.0, 2.0]

    def test_get_embedding_length_uses_config_when_present(self, monkeypatch):
        """When EMBEDDING_LENGTH is set in config, it should be returned without probing the API."""
        mod = _load_embedding_wrapper_module(monkeypatch, embedding_length=512)
        api = mod.EmbeddingAPI(api_url="http://embeddings:8000/embeddings", model_name="m")
        assert api.get_embedding_length() == 512

    def test_get_embedding_length_probes_when_config_zero(self, monkeypatch):
        """When EMBEDDING_LENGTH is 0, the API should be probed to determine the length."""
        mod = _load_embedding_wrapper_module(monkeypatch, embedding_length=0)

        class _Response:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"embedding": [[0.1, 0.2, 0.3, 0.4]]}

        monkeypatch.setattr(mod.requests, "post", lambda *_a, **_kw: _Response())

        api = mod.EmbeddingAPI(api_url="http://embeddings:8000/embeddings", model_name="m")
        assert api.get_embedding_length() == 4
