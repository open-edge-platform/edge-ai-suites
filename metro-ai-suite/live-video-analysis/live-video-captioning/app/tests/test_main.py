# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for main, FastAPI application setup and root endpoint."""


class TestRootEndpoint:
    """GET / serves the frontend index.html."""

    def test_root_returns_200(self, client):
        """The root endpoint returns HTTP 200."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_returns_html(self, client):
        """The root endpoint serves HTML content."""
        resp = client.get("/")
        assert "html" in resp.headers.get("content-type", "").lower()


class TestAppRouterInclusion:
    """Verify that all expected routers are mounted."""

    def test_health_route_registered(self, client):
        """The /api/health route is accessible."""
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_vlm_models_route_registered(self, client):
        """The /api/vlm-models route is accessible."""
        resp = client.get("/api/vlm-models")
        # May return empty list but should not 404
        assert resp.status_code == 200

    def test_detection_models_route_registered(self, client):
        """The /api/detection-models route is accessible."""
        resp = client.get("/api/detection-models")
        assert resp.status_code == 200

    def test_runs_route_registered(self, client):
        """The /api/runs route is accessible."""
        resp = client.get("/api/runs")
        assert resp.status_code == 200

    def test_runtime_config_route_registered(self, client):
        """The /runtime-config.js route is accessible."""
        resp = client.get("/runtime-config.js")
        assert resp.status_code == 200
