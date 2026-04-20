# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.routes.health."""


class TestHealthCheck:
    """GET /api/health endpoint."""

    def test_health_returns_200(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_returns_payload(self, client):
        resp = client.get("/api/health")
        assert resp.json()["status"] == "healthy"
        assert "running" in resp.json()["message"].lower()
