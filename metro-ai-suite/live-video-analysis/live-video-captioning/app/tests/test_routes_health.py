# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.routes.health, health check endpoint."""


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
