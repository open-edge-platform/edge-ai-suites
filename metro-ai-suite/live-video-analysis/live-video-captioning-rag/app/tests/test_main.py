# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for app bootstrap and route wiring in main.py."""


class TestRootEndpoint:
    """GET / endpoint should serve frontend content."""

    def test_root_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_serves_html(self, client):
        resp = client.get("/")
        assert "html" in resp.headers.get("content-type", "").lower()


class TestRouteRegistration:
    """All public API routers are mounted."""

    def test_health_route_registered(self, client):
        """The health check route is registered and returns 200."""
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_model_route_registered(self, client):
        """The model info route is registered and returns 200."""
        resp = client.get("/api/model")
        assert resp.status_code == 200

    def test_embedding_route_registered(self, client):
        """The embedding route is registered and returns 200."""
        resp = client.post("/api/embeddings", json={"image_data": "abc", "metadata": {"result": "x"}})
        assert resp.status_code == 200

    def test_chat_route_registered(self, client):
        """The chat route is registered and returns 200."""
        resp = client.post("/api/chat", json={"input": "hello"})
        assert resp.status_code == 200
