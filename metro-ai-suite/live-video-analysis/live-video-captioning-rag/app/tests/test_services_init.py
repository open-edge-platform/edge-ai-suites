# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.services package exports."""

from pathlib import Path
from types import ModuleType
import importlib.util
import sys


def test_services_init_exports_chain_symbols(monkeypatch):
    """Test that backend.services.__init__.py correctly imports and re-exports symbols from chain.py."""
    backend_dir = Path(__file__).resolve().parents[1] / "backend"
    services_dir = backend_dir / "services"
    module_path = services_dir / "__init__.py"

    backend_pkg = ModuleType("backend")
    backend_pkg.__path__ = [str(backend_dir)]

    services_pkg = ModuleType("backend.services")
    services_pkg.__path__ = [str(services_dir)]

    chain_mod = ModuleType("backend.services.chain")

    def _build_chain():
        return "build"

    async def _process_query(*_args, **_kwargs):
        yield "query"

    async def _process_embeddings(*_args, **_kwargs):
        return "embedding"

    chain_mod.build_chain = _build_chain
    chain_mod.process_query = _process_query
    chain_mod.process_embeddings = _process_embeddings

    monkeypatch.setitem(sys.modules, "backend", backend_pkg)
    monkeypatch.setitem(sys.modules, "backend.services", services_pkg)
    monkeypatch.setitem(sys.modules, "backend.services.chain", chain_mod)

    spec = importlib.util.spec_from_file_location("backend.services", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules["backend.services"] = module
    spec.loader.exec_module(module)

    assert module.build_chain is _build_chain
    assert module.process_query is _process_query
    assert module.process_embeddings is _process_embeddings
    assert module.__all__ == ["build_chain", "process_query", "process_embeddings"]
