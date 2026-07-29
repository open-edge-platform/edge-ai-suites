# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for POST /v1/vms/{name}/register route delegation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from plugin.core.api.deps import get_db_session, get_vms_shim_sets
from plugin.core.config import VmsAuthConfig, VmsInstanceConfig
from plugin.core.main import create_app
from fastapi.testclient import TestClient


def _make_shim_set(name: str, vendor: str):
    config = VmsInstanceConfig(
        name=name,
        vendor=vendor,
        base_url="https://localhost:7001",
        auth=VmsAuthConfig(username="admin", password="test"),
    )
    shim = AsyncMock()
    shim.handle_register = AsyncMock(return_value={"status": "ok", "vendor": vendor})
    return SimpleNamespace(name=name, config=config, vms_shim=shim)


@pytest.fixture
def client_factory():
    import contextlib

    @contextlib.contextmanager
    def _make(shim_sets):
        app = create_app()

        async def override_shims():
            return shim_sets

        mock_db = AsyncMock()

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_vms_shim_sets] = override_shims
        app.dependency_overrides[get_db_session] = override_db
        yield TestClient(app, raise_server_exceptions=False)

    return _make


def test_register_vms_not_found(client_factory):
    with client_factory([]) as client:
        resp = client.post("/v1/vms/unknown/register", json={"manifest": {}})
    assert resp.status_code == 404


def test_register_delegates_to_shim_handle_register(client_factory):
    """Route passes raw body dict to shim.handle_register and returns result."""
    ss = _make_shim_set("nx-main", "nx_witness")
    body = {"manifest": {}, "analytics_app_id": "test"}
    with client_factory([ss]) as client:
        resp = client.post("/v1/vms/nx-main/register", json=body)
    assert resp.status_code == 200
    assert resp.json()["vendor"] == "nx_witness"
    ss.vms_shim.handle_register.assert_awaited_once()
    called_body, _, called_name = ss.vms_shim.handle_register.call_args[0]
    assert called_body == body
    assert called_name == "nx-main"


def test_register_non_nx_vendor_delegates_to_shim(client_factory):
    """Non-Nx vendors also go through handle_register — no vendor check in route."""
    ss = _make_shim_set("frigate-main", "frigate")
    with client_factory([ss]) as client:
        resp = client.post("/v1/vms/frigate-main/register", json={"manifest": {}})
    assert resp.status_code == 200
    ss.vms_shim.handle_register.assert_awaited_once()


def test_register_empty_body_is_tolerated(client_factory):
    """Route gracefully handles empty or missing JSON body."""
    ss = _make_shim_set("nx-main", "nx_witness")
    with client_factory([ss]) as client:
        resp = client.post("/v1/vms/nx-main/register", content=b"", headers={"content-type": "application/json"})
    # Should reach handle_register (may return whatever mock returns)
    ss.vms_shim.handle_register.assert_awaited_once()

