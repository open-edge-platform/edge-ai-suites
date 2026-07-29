# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.routes.health, health check endpoint."""

from unittest.mock import patch


class TestHealthCheck:
    """GET /api/health endpoint."""

    def test_health_returns_200(self, client):
        """Health endpoint returns HTTP 200."""
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_returns_healthy_status(self, client):
        """Health endpoint body contains {"status": "healthy"}."""
        resp = client.get("/api/health")
        assert resp.json() == {"status": "healthy"}


class TestCapabilities:
    """GET /api/capabilities endpoint."""

    def test_capabilities_reports_gpu_available(self, client):
        """Capabilities endpoint reports has_gpu=true when GPU is detected."""
        with patch("backend.routes.health.has_gpu_device", return_value=True), patch(
            "backend.routes.health.has_npu_device", return_value=False
        ):
            resp = client.get("/api/capabilities")

        assert resp.status_code == 200
        assert resp.json() == {"has_gpu": True, "has_npu": False}

    def test_capabilities_reports_gpu_unavailable(self, client):
        """Capabilities endpoint reports has_gpu=false when GPU is not detected."""
        with patch("backend.routes.health.has_gpu_device", return_value=False), patch(
            "backend.routes.health.has_npu_device", return_value=False
        ):
            resp = client.get("/api/capabilities")

        assert resp.status_code == 200
        assert resp.json() == {"has_gpu": False, "has_npu": False}