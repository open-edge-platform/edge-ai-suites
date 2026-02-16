# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for the FastAPI application setup (app/main.py).

Covers:
- Root endpoint response
- Application metadata (title, version)
- CORS middleware presence
- Router inclusion
"""

import pytest

from app.main import app


class TestRootEndpoint:
    """Tests for the GET / root endpoint."""

    def test_root_returns_service_info(self, client):
        """GET / returns the service name, version, and description."""
        response = client.get("/")
        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "Metrics Service"
        assert body["version"] == "1.0.0"

    def test_root_contains_endpoint_listing(self, client):
        """GET / includes a map of available endpoints."""
        response = client.get("/")
        endpoints = response.json()["endpoints"]
        assert "websocket_collector" in endpoints
        assert "websocket_clients" in endpoints
        assert "health" in endpoints
        assert "health_detailed" in endpoints

    def test_root_endpoint_paths_are_correct(self, client):
        """GET / endpoint paths match the actual route configuration."""
        response = client.get("/")
        endpoints = response.json()["endpoints"]
        assert endpoints["websocket_collector"] == "/ws/collector"
        assert endpoints["websocket_clients"] == "/ws/clients"
        assert endpoints["health"] == "/health"
        assert endpoints["health_detailed"] == "/api/health"


class TestAppConfiguration:
    """Tests for FastAPI application metadata and middleware."""

    def test_app_title(self):
        """Application title is set to 'Metrics Service'."""
        assert app.title == "Metrics Service"

    def test_app_version(self):
        """Application version is '1.0.0'."""
        assert app.version == "1.0.0"

    def test_cors_middleware_is_registered(self):
        """CORS middleware is present in the middleware stack."""
        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_classes

    def test_routes_are_registered(self):
        """Key routes (/, /health, /api/health) are registered on the app."""
        route_paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/" in route_paths
        assert "/health" in route_paths
        assert "/api/health" in route_paths

    def test_websocket_routes_are_registered(self):
        """WebSocket routes (/ws/collector, /ws/clients) are registered."""
        route_paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/ws/collector" in route_paths
        assert "/ws/clients" in route_paths
