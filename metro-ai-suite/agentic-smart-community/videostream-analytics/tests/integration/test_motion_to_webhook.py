"""Integration tests: full pipeline — RTSP → motion detect → webhook events.

Phase 7: webhooks now use the nested envelope:
  { sourceId, type, timestamp, payload: {...} }
Motion payload fields: event_file_path, summary_clip_input, start_time, ...
"""

import time

import pytest
import httpx

from .conftest import wait_for_events


@pytest.mark.integration
class TestMotionToWebhook:
    @pytest.fixture(autouse=True)
    def register_source(self, http_client, analytics_url, rtsp_url, webhook_url):
        """Register a test source before each test, unregister after."""
        http_client.post(f"{analytics_url}/register_source", json={
            "source_id": "test_motion",
            "source_url": rtsp_url,
            "webhook_url": f"{webhook_url}/events",
            "pipeline": {
                "prefilter": {"enabled": False},
                "recording": {"enabled": False},  # tests focus on motion path
            },
        })
        time.sleep(2)
        yield
        try:
            http_client.post(f"{analytics_url}/sources/test_motion/stop")
        except httpx.HTTPError:
            pass

    def test_no_status_events_pushed(self, http_client, webhook_url):
        """§32: RTSP connection status is no longer pushed to the /events webhook.
        After the source connects, the mock webhook must have recorded zero `status`
        events (health is exposed via GET /sources/{id}/status instead)."""
        time.sleep(3)  # allow the source to connect / go online
        resp = http_client.get(f"{webhook_url}/recorded_events/status")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_motion_events_received(self, http_client, webhook_url):
        """After pipeline runs, motion events should arrive (video has motion after ~40s)."""
        events = wait_for_events(
            http_client, webhook_url, event_type="motion", min_count=1, timeout=60
        )
        assert len(events) >= 1, "No motion events received within 60s"

    def test_motion_event_payload_complete(self, http_client, webhook_url):
        """Motion event envelope + payload should have all required fields."""
        events = wait_for_events(
            http_client, webhook_url, event_type="motion", min_count=1, timeout=60
        )
        assert len(events) >= 1
        event = events[0]
        assert event["sourceId"] == "test_motion"
        assert event["type"] == "motion"
        assert "timestamp" in event
        payload = event["payload"]
        assert "start_time" in payload
        assert "end_time" in payload
        assert "duration_seconds" in payload
        assert "event_file_path" in payload
        assert "summary_clip_input" in payload
        assert payload["duration_seconds"] > 0
        assert payload["event_file_path"].endswith(".mp4")

    def test_motion_event_duration_within_range(self, http_client, webhook_url):
        """Motion event duration should be within min_duration to interval range."""
        events = wait_for_events(
            http_client, webhook_url, event_type="motion", min_count=1, timeout=240
        )
        assert len(events) >= 1
        for event in events:
            duration = event["payload"]["duration_seconds"]
            # Fixed interval cutting: each segment is at most interval (10s) + tolerance
            assert 1.0 <= duration <= 11.0, f"Duration {duration}s out of range"

    def test_multiple_motion_events_over_time(self, http_client, webhook_url):
        """Running long enough should produce multiple motion events."""
        events = wait_for_events(
            http_client, webhook_url, event_type="motion", min_count=2, timeout=240
        )
        assert len(events) >= 2, f"Expected >=2 motion events, got {len(events)}"

    def test_static_event_received(self, http_client, webhook_url):
        """A quiet period after motion should close out as a `type=static` event.

        VSA emits static on the strict Motion → static → Motion loop (and on
        shutdown drain), so a `static` must appear once the feed has a quiet
        span ≥ pipeline.static.min_duration between motions.
        """
        events = wait_for_events(
            http_client, webhook_url, event_type="static", min_count=1, timeout=240
        )
        assert len(events) >= 1, "No static events received within 240s"

    def test_static_event_payload_complete(self, http_client, webhook_url):
        """Static envelope + payload should carry the API §4 required fields."""
        events = wait_for_events(
            http_client, webhook_url, event_type="static", min_count=1, timeout=240
        )
        assert len(events) >= 1
        event = events[0]
        assert event["sourceId"] == "test_motion"
        assert event["type"] == "static"
        assert "timestamp" in event
        payload = event["payload"]
        assert "start_time" in payload
        assert "duration_seconds" in payload
        assert payload["duration_seconds"] > 0
