# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for backend.routes.alert."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.routes.alert import build_alert_router
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client(alert_index, get_alert_s3_client=None) -> TestClient:
    settings = SimpleNamespace(SEAWEEDFS_BUCKET="test-bucket")
    app = FastAPI()
    app.include_router(build_alert_router(alert_index, get_alert_s3_client or MagicMock(), settings))
    return TestClient(app)


def _alert_record(**overrides) -> dict:
    record = {
        "stream_id": "cam-1",
        "frame_id": "frame-1",
        "alert_event": "fire",
        "trigger_caption": "Yes",
        "thumbnail_object_key": "cam-1/frame-1.thumbnail.jpg",
        "video_object_key": "cam-1/frame-1.mp4",
        "description": "Smoke visible near the entrance.",
        "metrics": {"ttft_ms": 10.0},
        "model": "InternVL2-1B",
        "device": "NPU",
        "uploaded_at": "2026-01-01T00:00:00Z",
    }
    record.update(overrides)
    return record


class TestListAlerts:
    def test_lists_alerts_with_thumbnail_url_when_available(self):
        alert_index = MagicMock()
        alert_index.list.return_value = ([_alert_record()], 1)

        response = _client(alert_index).get("/api/streams/cam-1/alerts")

        body = response.json()
        assert response.status_code == 200
        assert body["total"] == 1
        assert body["alerts"][0]["thumbnail_url"] == "/api/streams/cam-1/alerts/frame-1/thumbnail"

    def test_omits_thumbnail_url_when_not_available(self):
        alert_index = MagicMock()
        alert_index.list.return_value = ([_alert_record(thumbnail_object_key="")], 1)

        response = _client(alert_index).get("/api/streams/cam-1/alerts")

        assert response.json()["alerts"][0]["thumbnail_url"] == ""

    def test_passes_limit_and_offset_through(self):
        alert_index = MagicMock()
        alert_index.list.return_value = ([], 0)

        _client(alert_index).get("/api/streams/cam-1/alerts?limit=5&offset=10")

        alert_index.list.assert_called_once_with("cam-1", limit=5, offset=10)


class TestAlertDetail:
    def test_returns_full_alert_detail(self):
        alert_index = MagicMock()
        alert_index.get.return_value = _alert_record()

        response = _client(alert_index).get("/api/streams/cam-1/alerts/frame-1")

        body = response.json()
        assert response.status_code == 200
        assert body["description"] == "Smoke visible near the entrance."
        assert body["video_url"] == "/api/streams/cam-1/alerts/frame-1/video"

    def test_returns_404_when_alert_not_found(self):
        alert_index = MagicMock()
        alert_index.get.return_value = None

        response = _client(alert_index).get("/api/streams/cam-1/alerts/missing")

        assert response.status_code == 404


class TestAlertThumbnail:
    def test_returns_thumbnail_bytes(self):
        alert_index = MagicMock()
        alert_index.get.return_value = _alert_record()
        s3_client = MagicMock()
        s3_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"jpeg-bytes")}

        response = _client(alert_index, lambda: s3_client).get("/api/streams/cam-1/alerts/frame-1/thumbnail")

        assert response.status_code == 200
        assert response.content == b"jpeg-bytes"
        assert response.headers["content-type"] == "image/jpeg"

    def test_returns_404_when_no_thumbnail_key(self):
        alert_index = MagicMock()
        alert_index.get.return_value = _alert_record(thumbnail_object_key="")

        response = _client(alert_index).get("/api/streams/cam-1/alerts/frame-1/thumbnail")

        assert response.status_code == 404

    def test_returns_404_when_alert_not_found(self):
        alert_index = MagicMock()
        alert_index.get.return_value = None

        response = _client(alert_index).get("/api/streams/cam-1/alerts/frame-1/thumbnail")

        assert response.status_code == 404


class TestAlertVideo:
    def test_returns_video_bytes(self):
        alert_index = MagicMock()
        alert_index.get.return_value = _alert_record()
        s3_client = MagicMock()
        s3_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"mp4-bytes")}

        response = _client(alert_index, lambda: s3_client).get("/api/streams/cam-1/alerts/frame-1/video")

        assert response.status_code == 200
        assert response.content == b"mp4-bytes"
        assert response.headers["content-type"] == "video/mp4"

    def test_returns_404_when_no_video_key(self):
        alert_index = MagicMock()
        alert_index.get.return_value = _alert_record(video_object_key="")

        response = _client(alert_index).get("/api/streams/cam-1/alerts/frame-1/video")

        assert response.status_code == 404
