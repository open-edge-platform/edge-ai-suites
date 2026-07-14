# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.routes.runs, run lifecycle endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from backend.models.responses import RunInfo
import backend.routes.runs as runs_module


def _run_info(run_id: str = "r1") -> RunInfo:
    return RunInfo(
        runId=run_id,
        pipelineId=f"p-{run_id}",
        peerId=f"peer-{run_id}",
        mqttTopic=f"topic/{run_id}",
        pipelineName="Video_Captioning_RTSP_Software",
    )


# ===================================================================
# POST /api/generate_captions_alerts
# ===================================================================
class TestStartRunRoute:
    """POST /api/generate_captions_alerts endpoint."""

    def test_start_run_success(self, client):
        """Route delegates to PipelineServer.start_run and returns RunInfo."""
        expected = _run_info("abc")

        with patch.object(
            runs_module.pipeline_server,
            "start_run",
            AsyncMock(return_value=expected),
        ) as mock_start:
            resp = client.post(
                "/api/generate_captions_alerts",
                json={"rtspUrl": "rtsp://10.0.0.1/stream"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["runId"] == "abc"
        assert body["pipelineId"] == "p-abc"
        mock_start.assert_awaited_once()
        req = mock_start.await_args.args[0]
        assert req.rtspUrl == "rtsp://10.0.0.1/stream"

    def test_start_run_propagates_http_exception(self, client):
        """HTTPException raised by service is surfaced by the route."""
        with patch.object(
            runs_module.pipeline_server,
            "start_run",
            AsyncMock(
                side_effect=HTTPException(
                    status_code=400,
                    detail={"message": "No matching backend pipeline found"},
                )
            ),
        ):
            resp = client.post(
                "/api/generate_captions_alerts",
                json={"rtspUrl": "rtsp://10.0.0.1/stream"},
            )

        assert resp.status_code == 400
        assert "No matching backend pipeline found" in resp.json()["detail"]["message"]

    def test_start_run_invalid_rtsp_url_returns_422(self, client):
        """Schema validation still rejects non-RTSP/non-device source values."""
        resp = client.post(
            "/api/generate_captions_alerts",
            json={"rtspUrl": "http://not-rtsp.com/stream"},
        )
        assert resp.status_code == 422


# ===================================================================
# GET /api/generate_captions_alerts
# ===================================================================
class TestListRunsRoute:
    """GET /api/generate_captions_alerts endpoint."""

    def test_list_runs_empty(self, client):
        with patch.object(runs_module.pipeline_server, "list_runs", return_value=[]):
            resp = client.get("/api/generate_captions_alerts")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_runs_returns_active_runs(self, client):
        runs = [_run_info("r1"), _run_info("r2")]
        with patch.object(runs_module.pipeline_server, "list_runs", return_value=runs):
            resp = client.get("/api/generate_captions_alerts")

        assert resp.status_code == 200
        ids = {item["runId"] for item in resp.json()}
        assert ids == {"r1", "r2"}


# ===================================================================
# GET /api/generate_captions_alerts/{run_id}
# ===================================================================
class TestGetRunRoute:
    """GET /api/generate_captions_alerts/{run_id} endpoint."""

    def test_get_existing_run(self, client):
        with patch.object(runs_module.pipeline_server, "get_run", return_value=_run_info("r1")):
            resp = client.get("/api/generate_captions_alerts/r1")

        assert resp.status_code == 200
        assert resp.json()["runId"] == "r1"

    def test_get_nonexistent_run_returns_404(self, client):
        with patch.object(
            runs_module.pipeline_server,
            "get_run",
            side_effect=HTTPException(status_code=404, detail={"message": "Run not found"}),
        ):
            resp = client.get("/api/generate_captions_alerts/nonexistent")

        assert resp.status_code == 404


# ===================================================================
# GET /api/generate_captions_alerts/{run_id}/stream-ready
# ===================================================================
class TestStreamReadyRoute:
    """GET /api/generate_captions_alerts/{run_id}/stream-ready endpoint."""

    def test_stream_ready_true_when_frames_flowing(self, client):
        expected = {
            "runId": "r1",
            "peerId": "peer-r1",
            "ready": True,
            "state": "running",
            "error": False,
        }
        with patch.object(
            runs_module.pipeline_server,
            "stream_ready",
            AsyncMock(return_value=expected),
        ) as mock_stream_ready:
            resp = client.get("/api/generate_captions_alerts/r1/stream-ready")

        assert resp.status_code == 200
        assert resp.json() == expected
        mock_stream_ready.assert_awaited_once_with("r1")

    def test_stream_ready_nonexistent_run_returns_404(self, client):
        with patch.object(
            runs_module.pipeline_server,
            "stream_ready",
            AsyncMock(side_effect=HTTPException(status_code=404, detail={"message": "Run not found"})),
        ):
            resp = client.get("/api/generate_captions_alerts/nope/stream-ready")

        assert resp.status_code == 404


# ===================================================================
# DELETE /api/generate_captions_alerts/{run_id}
# ===================================================================
class TestStopRunRoute:
    """DELETE /api/generate_captions_alerts/{run_id} endpoint."""

    def test_stop_existing_run(self, client):
        with patch.object(
            runs_module.pipeline_server,
            "stop_run",
            AsyncMock(return_value={"status": "stopped", "runId": "r1"}),
        ) as mock_stop:
            resp = client.delete("/api/generate_captions_alerts/r1")

        assert resp.status_code == 200
        assert resp.json() == {"status": "stopped", "runId": "r1"}
        mock_stop.assert_awaited_once_with("r1")

    def test_stop_nonexistent_run_returns_404(self, client):
        with patch.object(
            runs_module.pipeline_server,
            "stop_run",
            AsyncMock(side_effect=HTTPException(status_code=404, detail={"message": "Run not found"})),
        ):
            resp = client.delete("/api/generate_captions_alerts/nonexistent")

        assert resp.status_code == 404


class TestRunsHelpers:
    """Unit tests for helper methods on the PipelineServer instance."""

    def test_build_unique_run_name_returns_none_when_sanitized_empty(self):
        assert runs_module.pipeline_server._build_unique_run_name("!!!@@@###") is None

    def test_generate_peer_id_invalid_config_raises(self, monkeypatch):
        monkeypatch.setattr(runs_module.pipeline_server, "WEBRTC_PEER_ID_PREFIX", "toolongprefix")
        monkeypatch.setattr(runs_module.pipeline_server, "WEBRTC_PEER_ID_MAX_LENGTH", 3)
        with pytest.raises(RuntimeError, match="Invalid WebRTC peer ID configuration"):
            runs_module.pipeline_server._generate_peer_id()


# ===================================================================
# GET /api/generate_captions_alerts/metadata-stream
# ===================================================================
class TestMetadataStreamRoute:
    """Tests for metadata stream endpoint."""

    def test_metadata_stream_endpoint_returns_sse_headers(self, client):
        async def _dummy_generator():
            yield "data: {}\n\n"

        stream = StreamingResponse(
            _dummy_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

        with patch.object(runs_module.pipeline_server, "metadata_stream", return_value=stream):
            resp = client.get("/api/generate_captions_alerts/metadata-stream")

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert resp.headers["cache-control"] == "no-cache"

    def test_metadata_stream_delegates_to_pipeline_server(self, client):
        async def _dummy_generator():
            yield "data: {}\n\n"

        with patch.object(
            runs_module.pipeline_server,
            "metadata_stream",
            return_value=StreamingResponse(_dummy_generator(), media_type="text/event-stream"),
        ) as mock_metadata:
            resp = client.get("/api/generate_captions_alerts/metadata-stream")

        assert resp.status_code == 200
        mock_metadata.assert_called_once_with()
