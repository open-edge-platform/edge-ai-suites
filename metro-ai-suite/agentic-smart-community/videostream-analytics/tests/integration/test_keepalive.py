"""Phase 8 integration tests — keepalive protocol & watchdog auto-pause.

Requires a live VSA service (`videostream-analytics serve`) and an RTSP source
(see scripts/test-videostream-analytics.sh). The watchdog timeout / interval
are intentionally short here (3s / 1s) so the suite stays under a minute.
"""

import time

import httpx
import pytest


def _body(
    source_id: str,
    rtsp_url: str,
    *,
    keepalive_enabled: bool,
    timeout_seconds: float = 3.0,
    check_interval_seconds: float = 1.0,
) -> dict:
    return {
        "source_id": source_id,
        "source_url": rtsp_url,
        "pipeline": {
            "prefilter": {"enabled": False},
            "recording": {"enabled": False},
            "keepalive": {
                "enabled": keepalive_enabled,
                "timeout_seconds": timeout_seconds,
                "check_interval_seconds": check_interval_seconds,
            },
        },
    }


@pytest.mark.integration
class TestKeepalive:
    @pytest.fixture(autouse=True)
    def cleanup(self, http_client, analytics_url):
        """Best-effort teardown — drop any sources this suite registers."""
        yield
        for sid in ("ka_real", "ka_timeout", "ka_disabled"):
            try:
                http_client.post(f"{analytics_url}/sources/{sid}/stop")
            except httpx.HTTPError:
                pass

    def test_keepalive_endpoint_real_http(
        self, http_client, analytics_url, rtsp_url
    ):
        """POST /sources/{id}/keepalive returns 200 and last_keepalive_at."""
        resp = http_client.post(
            f"{analytics_url}/register_source",
            json=_body("ka_real", rtsp_url, keepalive_enabled=True),
        )
        assert resp.status_code == 200

        resp = http_client.post(f"{analytics_url}/sources/ka_real/keepalive")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["source_id"] == "ka_real"
        assert "last_keepalive_at" in body

        status = http_client.get(f"{analytics_url}/sources/ka_real/status")
        assert status.status_code == 200
        sbody = status.json()
        assert sbody["keepalive_enabled"] is True
        assert sbody["last_keepalive_at"] is not None

    def test_watchdog_auto_pauses_after_timeout(
        self, http_client, analytics_url, rtsp_url
    ):
        """No keepalive within timeout → watchdog auto-pauses."""
        resp = http_client.post(
            f"{analytics_url}/register_source",
            json=_body(
                "ka_timeout",
                rtsp_url,
                keepalive_enabled=True,
                timeout_seconds=3.0,
                check_interval_seconds=1.0,
            ),
        )
        assert resp.status_code == 200

        # Wait past timeout + at least one watchdog tick.
        time.sleep(6)

        resp = http_client.get(f"{analytics_url}/sources/ka_timeout/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused", (
            f"expected status=paused, got {resp.json()}"
        )

    def test_watchdog_disabled_does_not_pause(
        self, http_client, analytics_url, rtsp_url
    ):
        """When keepalive is disabled, watchdog never pauses."""
        resp = http_client.post(
            f"{analytics_url}/register_source",
            json=_body(
                "ka_disabled",
                rtsp_url,
                keepalive_enabled=False,
                timeout_seconds=1.0,
                check_interval_seconds=1.0,
            ),
        )
        assert resp.status_code == 200

        time.sleep(5)

        resp = http_client.get(f"{analytics_url}/sources/ka_disabled/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] != "paused"
        assert body["keepalive_enabled"] is False
