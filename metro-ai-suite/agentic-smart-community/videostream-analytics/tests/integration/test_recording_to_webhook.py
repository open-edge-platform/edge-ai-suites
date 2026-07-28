"""Integration tests: continuous recording branch → webhook + disk files.

Phase 7 §3 enabled the fixed-duration recording path. This test confirms:
  - `recording: enabled=true` in register body wires up ContinuousRecorder
  - Recording events arrive in the nested envelope with the right payload
  - mp4 files land on disk under `<data_dir>/recordings/<YYYY-MM-DD>/`
"""

import os
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from .conftest import wait_for_events


@pytest.mark.integration
class TestRecordingToWebhook:
    @pytest.fixture(autouse=True)
    def register_source(self, http_client, analytics_url, rtsp_url, webhook_url):
        """Register a source with recording enabled at a short interval."""
        data_root = Path(os.environ.get("SMARTBUILDING_DATA_DIR", str(Path.home() / ".mcp-smartbuilding")))
        self.data_dir = str(data_root / "segments" / f"rec_cam_{uuid4().hex[:8]}")
        http_client.post(f"{analytics_url}/register_source", json={
            "source_id": "rec_cam",
            "source_url": rtsp_url,
            "webhook_url": f"{webhook_url}/events",
            "data_dir": self.data_dir,
            "pipeline": {
                "prefilter": {"enabled": False},
                "recording": {
                    "enabled": True,
                    "interval_seconds": 5,
                    "retention_days": 1,
                },
            },
        })
        time.sleep(2)
        yield
        try:
            http_client.post(f"{analytics_url}/sources/rec_cam/stop")
        except httpx.HTTPError:
            pass

    def test_recording_event_envelope_and_payload(self, http_client, webhook_url):
        """Recording event uses nested envelope with recording_* payload fields."""
        events = wait_for_events(
            http_client, webhook_url, event_type="recording", min_count=1, timeout=30
        )
        assert len(events) >= 1, "No recording events received within 30s"

        event = events[0]
        assert event["sourceId"] == "rec_cam"
        assert event["type"] == "recording"
        assert "timestamp" in event
        payload = event["payload"]
        assert payload["recording_path"].endswith(".mp4")
        assert "recording_start" in payload
        assert "recording_end" in payload
        assert payload["duration_seconds"] > 0
        assert payload["file_size_bytes"] > 0

    def test_recording_files_on_disk(self, http_client, webhook_url):
        """Recordings should appear under <data_dir>/recordings/<today>/."""
        wait_for_events(
            http_client, webhook_url, event_type="recording", min_count=1, timeout=30
        )
        today = datetime.now().strftime("%Y-%m-%d")
        rec_dir = os.path.join(self.data_dir, "recordings", today)
        assert os.path.isdir(rec_dir), f"Expected recordings dir at {rec_dir}"
        mp4s = [f for f in os.listdir(rec_dir) if f.endswith(".mp4")]
        assert len(mp4s) >= 1, f"No mp4 in {rec_dir}: {os.listdir(rec_dir)}"

    def test_latest_jpg_snapshot_written(self, http_client, webhook_url):
        """latest.jpg should be written to per-source data_dir at ~1Hz."""
        # Give the pipeline ~3 frames worth of warm-up.
        time.sleep(5)
        snapshot = os.path.join(self.data_dir, "latest.jpg")
        assert os.path.exists(snapshot), f"latest.jpg missing at {snapshot}"
        age = time.time() - os.path.getmtime(snapshot)
        assert age < 5.0, f"latest.jpg mtime too old: {age:.1f}s"
