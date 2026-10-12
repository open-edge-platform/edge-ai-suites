# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for backend.routes.registry."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from backend.routes.registry import build_registry_router
from backend.services.frame_registry import FrameRecord
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client(frame_registry) -> TestClient:
    app = FastAPI()
    app.include_router(build_registry_router(frame_registry))
    return TestClient(app)


class TestRegistryStats:
    def test_returns_registry_stats(self):
        frame_registry = MagicMock()
        frame_registry.stats.return_value = {"total": 1, "per_stream_capacity": 500, "per_stream": {"cam-1": 1}}

        response = _client(frame_registry).get("/api/registry/stats")

        assert response.status_code == 200
        assert response.json()["total"] == 1


class TestRegistryStreamLatest:
    def test_returns_latest_records_for_stream(self):
        frame_registry = MagicMock()
        record = FrameRecord(
            frame_id=uuid.uuid4(),
            stream_id="cam-1",
            rtsp_url="rtsp://example/cam1",
            segment_path="segments/cam-1_0001.mp4",
            pts_seconds=1.5,
        )
        frame_registry.latest.return_value = [record]

        response = _client(frame_registry).get("/api/registry/stream/cam-1")

        body = response.json()
        assert response.status_code == 200
        assert body["records"][0]["stream_id"] == "cam-1"
        assert body["records"][0]["segment_path"] == "segments/cam-1_0001.mp4"


class TestRegistryFrame:
    def test_returns_record_for_valid_frame_id(self):
        frame_registry = MagicMock()
        frame_id = uuid.uuid4()
        record = FrameRecord(
            frame_id=frame_id,
            stream_id="cam-1",
            rtsp_url="rtsp://example/cam1",
            segment_path="segments/cam-1_0001.mp4",
        )
        frame_registry.get_record.return_value = record

        response = _client(frame_registry).get(f"/api/registry/frame/{frame_id}")

        assert response.status_code == 200
        assert response.json()["frame_id"] == str(frame_id)

    def test_returns_404_when_frame_id_not_found(self):
        frame_registry = MagicMock()
        frame_registry.get_record.return_value = None

        response = _client(frame_registry).get(f"/api/registry/frame/{uuid.uuid4()}")

        assert response.status_code == 404

    def test_returns_400_for_malformed_frame_id(self):
        frame_registry = MagicMock()

        response = _client(frame_registry).get("/api/registry/frame/not-a-uuid")

        assert response.status_code == 400
