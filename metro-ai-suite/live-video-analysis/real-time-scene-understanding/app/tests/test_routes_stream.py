# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for backend.routes.stream."""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.routes.stream import build_stream_router
from backend.services.stream_manager import StreamHealth
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client(registry, alert_index) -> TestClient:
    app = FastAPI()
    app.include_router(build_stream_router(registry, alert_index))
    return TestClient(app)


def _fake_manager(stream_id="cam-1", url="rtsp://example/cam1"):
    manager = MagicMock()
    manager.stream_id = stream_id
    manager.source_url = url
    manager.vlm_prompt = "Find fire near ATM."
    manager.deep_analyzer_prompt = "Verify event and summarize clip."
    manager.get_health.return_value = StreamHealth(publishing=True, resolution="640x360", codec="h264")
    return manager


class TestListStreams:
    def test_lists_active_streams_with_health_and_alert_count(self):
        registry = MagicMock()
        registry.all.return_value = [_fake_manager()]
        alert_index = MagicMock()
        alert_index.count.return_value = 3

        response = _client(registry, alert_index).get("/api/streams")

        assert response.status_code == 200
        streams = response.json()["streams"]
        assert len(streams) == 1
        assert streams[0]["stream_id"] == "cam-1"
        assert streams[0]["publishing"] is True
        assert streams[0]["alert_count"] == 3
        assert streams[0]["alert_prompt"] == "Find fire near ATM."
        assert streams[0]["deep_analyzer_prompt"] == "Verify event and summarize clip."
        assert streams[0]["whep_path"] == "/cam-1/whep"

    def test_includes_caption_history_in_payload(self):
        registry = MagicMock()
        manager = _fake_manager()
        manager.get_health.return_value = StreamHealth(
            caption="Yes",
            caption_history=[
                {"response": "Yes", "playback_seconds": 10.1},
                {"response": "No", "playback_seconds": 9.1},
                {"response": "Yes", "playback_seconds": 8.1},
            ],
        )
        registry.all.return_value = [manager]
        alert_index = MagicMock()
        alert_index.count.return_value = 0

        response = _client(registry, alert_index).get("/api/streams")

        assert response.status_code == 200
        stream = response.json()["streams"][0]
        assert stream["caption"] == "Yes"
        assert stream["caption_history"][0]["response"] == "Yes"
        assert stream["caption_history"][1]["response"] == "No"

    def test_returns_empty_list_when_no_streams(self):
        registry = MagicMock()
        registry.all.return_value = []
        alert_index = MagicMock()

        response = _client(registry, alert_index).get("/api/streams")

        assert response.json() == {"streams": []}


class TestAddStream:
    def test_adds_stream_with_valid_payload(self):
        registry = MagicMock()
        alert_index = MagicMock()

        response = _client(registry, alert_index).post(
            "/api/streams",
            json={
                "url": "rtsp://example/cam1",
                "stream_id": "cam-1",
                "alert_prompt": "Look for smoke near the ATM.\nMention visible hazards.",
                "deep_analyzer_prompt": "Analyze the segment and summarize visible threat evidence.",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"status": "added", "stream_id": "cam-1"}
        registry.add.assert_called_once()
        args, _kwargs = registry.add.call_args
        assert args[0] == "cam-1"
        assert args[1] == "rtsp://example/cam1"
        assert args[2] == "Look for smoke near the ATM.\nMention visible hazards."
        assert args[3] == "Analyze the segment and summarize visible threat evidence."

    def test_defaults_stream_id_when_omitted(self):
        registry = MagicMock()
        alert_index = MagicMock()

        response = _client(registry, alert_index).post(
            "/api/streams",
            json={
                "url": "rtsp://example/cam1",
                "alert_prompt": "Check for a visible firearm.",
                "deep_analyzer_prompt": "Confirm firearm visibility from the clip and describe evidence.",
            },
        )

        assert response.json()["stream_id"] == "default"

    def test_rejects_missing_url(self):
        registry = MagicMock()
        alert_index = MagicMock()

        response = _client(registry, alert_index).post("/api/streams", json={})

        assert response.status_code == 400
        registry.add.assert_not_called()

    def test_rejects_missing_alert_prompt(self):
        registry = MagicMock()
        alert_index = MagicMock()

        response = _client(registry, alert_index).post(
            "/api/streams", json={"url": "rtsp://example/cam1", "alert_prompt": ""}
        )

        assert response.status_code == 400
        registry.add.assert_not_called()

    def test_rejects_missing_deep_analyzer_prompt(self):
        registry = MagicMock()
        alert_index = MagicMock()

        response = _client(registry, alert_index).post(
            "/api/streams",
            json={"url": "rtsp://example/cam1", "alert_prompt": "Look for smoke.", "deep_analyzer_prompt": ""},
        )

        assert response.status_code == 400
        registry.add.assert_not_called()

    def test_rejects_disallowed_url_scheme(self):
        registry = MagicMock()
        alert_index = MagicMock()

        response = _client(registry, alert_index).post(
            "/api/streams",
            json={
                "url": "file:///etc/passwd",
                "alert_prompt": "Look for smoke.",
                "deep_analyzer_prompt": "Summarize the scene evidence for smoke.",
            },
        )

        assert response.status_code == 400
        registry.add.assert_not_called()

    def test_rejects_stream_id_with_path_traversal(self):
        registry = MagicMock()
        alert_index = MagicMock()

        response = _client(registry, alert_index).post(
            "/api/streams",
            json={
                "url": "rtsp://example/cam1",
                "stream_id": "../../etc/cron.d/evil",
                "alert_prompt": "Look for smoke.",
                "deep_analyzer_prompt": "Summarize the scene evidence for smoke.",
            },
        )

        assert response.status_code == 400
        registry.add.assert_not_called()

    def test_rejects_oversized_prompt(self):
        registry = MagicMock()
        alert_index = MagicMock()

        response = _client(registry, alert_index).post(
            "/api/streams",
            json={
                "url": "rtsp://example/cam1",
                "alert_prompt": "x" * 5000,
                "deep_analyzer_prompt": "Summarize the scene evidence for smoke.",
            },
        )

        assert response.status_code == 422
        registry.add.assert_not_called()

    def test_returns_409_when_registry_rejects_duplicate(self):
        registry = MagicMock()
        registry.add.side_effect = ValueError("Stream 'cam-1' already exists")
        alert_index = MagicMock()

        response = _client(registry, alert_index).post(
            "/api/streams",
            json={
                "url": "rtsp://example/cam1",
                "stream_id": "cam-1",
                "alert_prompt": "Look for smoke.",
                "deep_analyzer_prompt": "Summarize the scene evidence for smoke.",
            },
        )

        assert response.status_code == 409


class TestDeleteStream:
    def test_removes_existing_stream(self):
        registry = MagicMock()
        alert_index = MagicMock()

        response = _client(registry, alert_index).delete("/api/streams/cam-1")

        assert response.status_code == 200
        assert response.json() == {"status": "removed", "stream_id": "cam-1"}
        registry.remove.assert_called_once_with("cam-1")

    def test_returns_404_for_unknown_stream(self):
        registry = MagicMock()
        registry.remove.side_effect = KeyError("cam-1")
        alert_index = MagicMock()

        response = _client(registry, alert_index).delete("/api/streams/cam-1")

        assert response.status_code == 404
