"""Integration tests: error handling scenarios.

Phase 7: register body uses nested `pipeline` wrapper and `source_url`.
"""

import time

import pytest


def _body(source_id: str, rtsp_url: str) -> dict:
    return {
        "source_id": source_id,
        "source_url": rtsp_url,
        "pipeline": {
            "prefilter": {"enabled": False},
            "recording": {"enabled": False},
        },
    }


@pytest.mark.integration
class TestErrorHandling:
    def test_invalid_rtsp_url_pipeline_reconnects(self, http_client, analytics_url):
        """Registering with an invalid RTSP URL should not crash the service."""
        resp = http_client.post(
            f"{analytics_url}/register_source",
            json=_body("bad_cam", "rtsp://nonexistent-host:8554/invalid"),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "started"

        time.sleep(5)

        health = http_client.get(f"{analytics_url}/health")
        assert health.status_code == 200

        status = http_client.get(f"{analytics_url}/sources/bad_cam")
        assert status.status_code == 200
        assert status.json()["source_id"] == "bad_cam"

        http_client.post(f"{analytics_url}/sources/bad_cam/stop")

    def test_register_duplicate_while_running(self, http_client, analytics_url, rtsp_url):
        """Re-registering a running source should return already_running."""
        http_client.post(f"{analytics_url}/register_source", json=_body("dup_cam", rtsp_url))
        time.sleep(2)

        resp = http_client.post(f"{analytics_url}/register_source", json=_body("dup_cam", rtsp_url))
        assert resp.json()["status"] == "already_running"

        http_client.post(f"{analytics_url}/sources/dup_cam/stop")

    def test_unregister_nonexistent_returns_404(self, http_client, analytics_url):
        """Unregistering a source that doesn't exist should return 404."""
        resp = http_client.request("DELETE", f"{analytics_url}/unregister_source", json={
            "source_id": "ghost_cam",
        })
        assert resp.status_code == 404

    def test_service_healthy_after_errors(self, http_client, analytics_url, rtsp_url):
        """After error scenarios, service should still function normally."""
        http_client.post(
            f"{analytics_url}/register_source",
            json=_body("error_cam", "rtsp://127.0.0.1:9999/nonexistent"),
        )
        time.sleep(3)

        resp = http_client.post(
            f"{analytics_url}/register_source", json=_body("good_cam", rtsp_url)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "started"

        http_client.post(f"{analytics_url}/sources/error_cam/stop")
        http_client.post(f"{analytics_url}/sources/good_cam/stop")
