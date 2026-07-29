"""Integration tests: container health and basic connectivity."""

import pytest

import httpx


@pytest.mark.integration
class TestContainerHealth:
    def test_health_endpoint_returns_200(self, http_client, analytics_url):
        resp = http_client.get(f"{analytics_url}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "videostream-analytics"

    def test_sources_initially_empty(self, http_client, analytics_url):
        resp = http_client.get(f"{analytics_url}/sources")
        assert resp.status_code == 200
        # Phase 7: /sources returns a bare array, not {"sources":[...]}
        assert resp.json() == []

    def test_webhook_server_reachable(self, http_client, webhook_url):
        resp = http_client.get(f"{webhook_url}/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
