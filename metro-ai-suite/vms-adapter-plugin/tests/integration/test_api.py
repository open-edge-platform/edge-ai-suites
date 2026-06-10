# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for FastAPI API endpoints."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from plugin.core.api.deps import get_db_session, get_vms_shim_sets
from plugin.core.main import create_app


@pytest.fixture
def client():
    app = create_app()
    # Don't use lifespan for integration tests (no DB)
    return TestClient(app, raise_server_exceptions=False)


def test_health(client):
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_openapi_spec(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert spec["info"]["title"] == "VMS Plugin Microservice"
    assert "/v1/health" in spec["paths"]
    assert "/v1/cameras" in spec["paths"]
    assert "/v1/events/timeline" in spec["paths"]
    assert "/v1/analysis/results" in spec["paths"]
    assert "/v1/config/status" in spec["paths"]


def test_ready_reports_db_and_vms_status(client):
    class FakeDbSession:
        async def execute(self, _query):
            return 1

    async def override_db():
        yield FakeDbSession()

    frigate_shim = SimpleNamespace(is_connected=MagicMock(return_value=True))
    nx_shim = SimpleNamespace(is_connected=MagicMock(return_value=False))
    shim_sets = [
        SimpleNamespace(
            name="frigate-main",
            config=SimpleNamespace(vendor="frigate"),
            vms_shim=frigate_shim,
        ),
        SimpleNamespace(
            name="nx-main",
            config=SimpleNamespace(vendor="nx_witness"),
            vms_shim=nx_shim,
        ),
    ]

    client.app.dependency_overrides[get_db_session] = override_db
    client.app.dependency_overrides[get_vms_shim_sets] = lambda: shim_sets

    try:
        resp = client.get("/v1/ready")
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ready",
        "database": True,
        "vms_connected": True,
    }
