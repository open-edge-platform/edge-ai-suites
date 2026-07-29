# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Shared pytest fixtures for live-video-captioning-rag tests."""

from types import ModuleType
import importlib
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _patch_env(monkeypatch):
    """Set safe defaults for environment-driven config in tests."""
    monkeypatch.setenv("APP_PORT", "4172")
    monkeypatch.setenv("LLM_MODEL_ID", "test-model")
    monkeypatch.setenv("LLM_DEVICE", "cpu")
    monkeypatch.setenv("MAX_TOKENS", "32")
    monkeypatch.setenv("TOP_K", "1")
    monkeypatch.setenv("SCORE_THRESHOLD", "0.3")
    monkeypatch.setenv("CACHE_DIR", "/tmp/model_cache")
    monkeypatch.setenv("VDMS_HOST", "localhost")
    monkeypatch.setenv("VDMS_PORT", "55555")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embedding")
    monkeypatch.setenv("EMBEDDING_HOST", "localhost")
    monkeypatch.setenv("EMBEDDING_HOST_PORT", "8000")
    monkeypatch.setenv("EMBEDDING_LENGTH", "8")


@pytest.fixture()
def client(monkeypatch, tmp_path):
    """Return a TestClient without initializing real LLM/VDMS dependencies."""

    # Stub backend.services so route imports are lightweight during app startup.
    fake_services = ModuleType("backend.services")

    async def _process_embeddings(_image_data, _metadata):
        return "test-embedding-id"

    def _build_chain():
        return object()

    async def _process_query(_chain=None, _query=""):
        yield "data: test-answer\\n\\n"
        yield "event: frame\\n"
        yield "data: []\\n\\n"

    fake_services.process_embeddings = _process_embeddings
    fake_services.build_chain = _build_chain
    fake_services.process_query = _process_query

    monkeypatch.setitem(sys.modules, "backend.services", fake_services)

    ui_dir = tmp_path / "ui"
    ui_dir.mkdir()
    (ui_dir / "index.html").write_text("<html><body>rag-test</body></html>")

    import backend.config as cfg

    monkeypatch.setattr(cfg, "UI_DIR", ui_dir)

    # Ensure app and route modules are imported after stubbing backend.services.
    sys.modules.pop("backend.routes.chat", None)
    sys.modules.pop("backend.routes.embedding", None)
    sys.modules.pop("backend.routes", None)
    sys.modules.pop("main", None)

    main = importlib.import_module("main")
    importlib.reload(main)

    with TestClient(main.app) as tc:
        yield tc
