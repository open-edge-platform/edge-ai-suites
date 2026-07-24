"""Integration tests: source registration, listing, stop, restart lifecycle.

Phase 7: register body uses nested `pipeline` wrapper and `source_url`
(not `rtsp_url`); `/sources` returns a bare array.
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
class TestSourceLifecycle:
    def test_register_source(self, http_client, analytics_url, rtsp_url):
        resp = http_client.post(
            f"{analytics_url}/register_source", json=_body("test_child", rtsp_url)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"
        assert data["source_id"] == "test_child"

    def test_list_sources_after_register(self, http_client, analytics_url, rtsp_url):
        http_client.post(
            f"{analytics_url}/register_source", json=_body("test_child_list", rtsp_url)
        )
        time.sleep(1)

        resp = http_client.get(f"{analytics_url}/sources")
        assert resp.status_code == 200
        sources = resp.json()
        # Phase 7: bare array, not {"sources": [...]}
        assert isinstance(sources, list)
        source_ids = [s["source_id"] for s in sources]
        assert "test_child_list" in source_ids

    def test_get_source_status(self, http_client, analytics_url, rtsp_url):
        http_client.post(
            f"{analytics_url}/register_source", json=_body("test_child_status", rtsp_url)
        )
        time.sleep(2)

        resp = http_client.get(f"{analytics_url}/sources/test_child_status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_id"] == "test_child_status"
        assert data["running"] is True

    def test_get_source_status_via_status_path(self, http_client, analytics_url, rtsp_url):
        """MCP's analyticsSourceExists calls /sources/{id}/status."""
        http_client.post(
            f"{analytics_url}/register_source",
            json=_body("test_child_status_alias", rtsp_url),
        )
        time.sleep(1)
        resp = http_client.get(f"{analytics_url}/sources/test_child_status_alias/status")
        assert resp.status_code == 200
        assert resp.json()["source_id"] == "test_child_status_alias"

    def test_stop_source(self, http_client, analytics_url, rtsp_url):
        http_client.post(
            f"{analytics_url}/register_source", json=_body("test_child_stop", rtsp_url)
        )
        time.sleep(1)

        resp = http_client.post(f"{analytics_url}/sources/test_child_stop/stop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    def test_stop_nonexistent_returns_404(self, http_client, analytics_url):
        resp = http_client.post(f"{analytics_url}/sources/nonexistent_cam/stop")
        assert resp.status_code == 404

    def test_register_duplicate_returns_already_running(
        self, http_client, analytics_url, rtsp_url
    ):
        http_client.post(
            f"{analytics_url}/register_source", json=_body("test_child_dup", rtsp_url)
        )
        time.sleep(1)

        resp = http_client.post(
            f"{analytics_url}/register_source", json=_body("test_child_dup", rtsp_url)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "already_running"

    def test_unregister_source(self, http_client, analytics_url, rtsp_url):
        http_client.post(
            f"{analytics_url}/register_source", json=_body("test_child_unreg", rtsp_url)
        )
        time.sleep(1)

        resp = http_client.request(
            "DELETE", f"{analytics_url}/unregister_source",
            json={"source_id": "test_child_unreg"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    def test_register_old_flat_body_rejected(self, http_client, analytics_url, rtsp_url):
        """Phase 7: hard cutover — old flat body must return 422."""
        resp = http_client.post(f"{analytics_url}/register_source", json={
            "source_id": "test_flat_reject",
            "rtsp_url": rtsp_url,  # renamed → unknown field
            "use_case": "child_safety",  # removed → unknown field
            "motion": {"diff_threshold": 25},  # moved into pipeline → unknown field
        })
        assert resp.status_code == 422
        body = resp.json()
        assert "unknown_fields" in body
        assert "rtsp_url" in body["unknown_fields"]
