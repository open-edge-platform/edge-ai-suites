# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for the health-check routes (app/routes.py).

Covers:
- GET /health basic health check
- GET /api/health detailed health check with relay status
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestHealthCheck:
    """Tests for the GET /health endpoint."""

    def test_health_returns_healthy(self, client):
        """GET /health returns 200 with status 'healthy'."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_health_response_content_type(self, client):
        """GET /health responds with JSON content type."""
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]


class TestApiHealthCheck:
    """Tests for the GET /api/health detailed endpoint."""

    def test_api_health_returns_status_and_relay_info(self, client):
        """GET /api/health returns status plus collector/client counts."""
        with patch(
            "app.routes.get_status",
            new_callable=AsyncMock,
            return_value={"collector_connected": False, "clients_connected": 0},
        ):
            response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert "collector_connected" in body
        assert "clients_connected" in body

    def test_api_health_with_collector_connected(self, client):
        """GET /api/health reflects a connected collector."""
        with patch(
            "app.routes.get_status",
            new_callable=AsyncMock,
            return_value={"collector_connected": True, "clients_connected": 3},
        ):
            response = client.get("/api/health")
        body = response.json()
        assert body["collector_connected"] is True
        assert body["clients_connected"] == 3

    def test_api_health_no_collector_no_clients(self, client):
        """GET /api/health reports zeros when nothing is connected."""
        with patch(
            "app.routes.get_status",
            new_callable=AsyncMock,
            return_value={"collector_connected": False, "clients_connected": 0},
        ):
            response = client.get("/api/health")
        body = response.json()
        assert body["collector_connected"] is False
        assert body["clients_connected"] == 0
