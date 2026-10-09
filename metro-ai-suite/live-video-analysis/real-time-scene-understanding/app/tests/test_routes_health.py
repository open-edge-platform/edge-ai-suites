# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for backend.routes.health."""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.routes.health import build_health_router
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client(registry, startup_time: float = 0.0) -> TestClient:
    app = FastAPI()
    app.include_router(build_health_router(registry, startup_time))
    return TestClient(app)


class TestHealthEndpoint:
    def test_reports_healthy_with_active_stream_count(self):
        registry = MagicMock()
        registry.ids.return_value = ["cam-1", "cam-2"]

        response = _client(registry).get("/api/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["streams_active"] == 2
        assert "uptime_seconds" in body
        assert "timestamp" in body

    def test_reports_zero_streams_when_registry_empty(self):
        registry = MagicMock()
        registry.ids.return_value = []

        response = _client(registry).get("/api/health")

        assert response.json()["streams_active"] == 0
