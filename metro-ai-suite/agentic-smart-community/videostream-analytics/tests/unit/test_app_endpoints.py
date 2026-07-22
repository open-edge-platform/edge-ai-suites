"""Tests for FastAPI endpoints with mocked SourceManager.

Phase 7 hard cutover: the request schemas in service.py now use the nested
`pipeline` wrapper and reject the old flat format with HTTP 422.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import service as service_module
from service import create_app
from shared.config import AppConfig
from source_worker import SourceManager


@pytest.fixture
def mock_manager():
    mgr = MagicMock(spec=SourceManager)
    mgr.get_sources.return_value = []
    mgr.get_source_status.return_value = None
    mgr._bundles = {}
    return mgr


@pytest.fixture
def app_and_client(mock_manager, monkeypatch):
    """Spin up the real service.create_app() against a mocked SourceManager.

    Must patch `_manager` AFTER TestClient enters context — the lifespan
    handler creates a real SourceManager on startup. Patching before would
    be overwritten.
    """
    app = create_app(AppConfig())
    with TestClient(app, raise_server_exceptions=False) as tc:
        monkeypatch.setattr(service_module, "_manager", mock_manager)
        yield tc, mock_manager


@pytest.fixture
def client(app_and_client):
    return app_and_client[0]


@pytest.fixture
def mock_mgr(app_and_client):
    return app_and_client[1]


# Lifespan startup re-binds _manager. Re-patch in each test that needs it,
# or use the fixture above which patches AFTER `with TestClient(...)` enters.


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "videostream-analytics"


class TestListSources:
    def test_empty_sources(self, client, mock_mgr):
        mock_mgr.get_sources.return_value = []
        resp = client.get("/sources")
        assert resp.status_code == 200
        # /sources returns a bare array (Phase 7 contract)
        assert resp.json() == []

    def test_with_sources(self, client, mock_mgr):
        mock_mgr.get_sources.return_value = [
            {
                "source_id": "cam1",
                "source_url": "rtsp://localhost:8554/live/cam1",
                "status": "online",
                "running": True,
            }
        ]
        resp = client.get("/sources")
        assert resp.status_code == 200
        sources = resp.json()
        assert isinstance(sources, list)
        assert len(sources) == 1
        assert sources[0]["source_id"] == "cam1"


class TestGetSource:
    def test_existing_source(self, client, mock_mgr):
        mock_mgr.get_source_status.return_value = {
            "source_id": "cam1",
            "source_url": "rtsp://localhost:8554/live/cam1",
            "status": "online",
            "running": True,
        }
        resp = client.get("/sources/cam1")
        assert resp.status_code == 200
        assert resp.json()["source_id"] == "cam1"

    def test_status_endpoint_alias(self, client, mock_mgr):
        """MCP's analyticsSourceExists hits /sources/{id}/status."""
        mock_mgr.get_source_status.return_value = {
            "source_id": "cam1",
            "status": "online",
        }
        resp = client.get("/sources/cam1/status")
        assert resp.status_code == 200
        assert resp.json()["source_id"] == "cam1"

    def test_nonexistent_source(self, client, mock_mgr):
        mock_mgr.get_source_status.return_value = None
        resp = client.get("/sources/nonexistent")
        assert resp.status_code == 404

    def test_nonexistent_status_returns_404(self, client, mock_mgr):
        mock_mgr.get_source_status.return_value = None
        resp = client.get("/sources/nonexistent/status")
        assert resp.status_code == 404


class TestRegisterSource:
    def test_register_success_nested(self, client, mock_mgr):
        mock_mgr.register_source.return_value = {
            "status": "started",
            "source_id": "cam1",
            "source_url": "rtsp://localhost:8554/live/cam1",
        }
        resp = client.post("/register_source", json={
            "source_id": "cam1",
            "source_url": "rtsp://localhost:8554/live/cam1",
            "data_dir": "/tmp/cam1",
            "pipeline": {
                "prefilter": {"enabled": False},
            },
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "started"

    def test_register_accepts_roi_block(self, client, mock_mgr):
        """Phase 9: pipeline.roi top-level block must be accepted."""
        mock_mgr.register_source.return_value = {
            "status": "started",
            "source_id": "cam_child",
            "source_url": "rtsp://localhost:8554/live/child",
        }
        resp = client.post("/register_source", json={
            "source_id": "cam_child",
            "source_url": "rtsp://localhost:8554/live/child",
            "pipeline": {
                "prefilter": {
                    "enabled": True,
                    "model_path": "/models/yolo11s.xml",
                    "target_classes": ["person"],
                },
                "roi": {
                    "enabled": True,
                    "mode": "crop",
                    "expand": 0.25,
                    "auto_split_area": 0.35,
                },
            },
        })
        assert resp.status_code == 200
        # Verify the roi block survived into the SourceConfig hand-off.
        ((source_arg,), _) = mock_mgr.register_source.call_args
        assert source_arg.roi is not None
        assert source_arg.roi.enabled is True
        assert source_arg.roi.mode == "crop"
        assert source_arg.roi.auto_split_area == 0.35

    def test_register_already_running(self, client, mock_mgr):
        mock_mgr.register_source.return_value = {
            "status": "already_running",
            "source_id": "cam1",
        }
        resp = client.post("/register_source", json={
            "source_id": "cam1",
            "source_url": "rtsp://localhost:8554/live/cam1",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "already_running"

    def test_register_rejects_old_flat_body(self, client, mock_mgr):
        """Phase 7 hard cutover: old rtsp_url / top-level motion must 422."""
        resp = client.post("/register_source", json={
            "source_id": "cam1",
            "rtsp_url": "rtsp://localhost:8554/live/cam1",
            "use_case": "child_safety",
            "motion": {"diff_threshold": 15},
        })
        assert resp.status_code == 422
        body = resp.json()
        assert "unknown_fields" in body
        # rtsp_url, use_case, motion must each appear in unknown_fields
        assert "rtsp_url" in body["unknown_fields"]
        assert "use_case" in body["unknown_fields"]
        assert "motion" in body["unknown_fields"]

    def test_register_missing_source_url_returns_422(self, client, mock_mgr):
        resp = client.post("/register_source", json={"source_id": "cam1"})
        assert resp.status_code == 422


class TestUnregisterSource:
    def test_unregister_success(self, client, mock_mgr):
        mock_mgr.unregister_source.return_value = {
            "status": "stopped",
            "source_id": "cam1",
        }
        resp = client.request("DELETE", "/unregister_source", json={
            "source_id": "cam1",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    def test_unregister_not_found(self, client, mock_mgr):
        mock_mgr.unregister_source.return_value = {
            "status": "not_found",
            "source_id": "nonexistent",
        }
        resp = client.request("DELETE", "/unregister_source", json={
            "source_id": "nonexistent",
        })
        assert resp.status_code == 404


class TestStopSource:
    def test_stop_success(self, client, mock_mgr):
        mock_mgr.unregister_source.return_value = {
            "status": "stopped",
            "source_id": "cam1",
        }
        resp = client.post("/sources/cam1/stop")
        assert resp.status_code == 200

    def test_stop_not_found(self, client, mock_mgr):
        mock_mgr.unregister_source.return_value = {
            "status": "not_found",
            "source_id": "cam1",
        }
        resp = client.post("/sources/cam1/stop")
        assert resp.status_code == 404


class TestRestartSource:
    def test_restart_success(self, client, mock_mgr):
        mock_pipeline = MagicMock()
        mock_recorder = MagicMock()
        mock_bundle = MagicMock(pipeline=mock_pipeline, recorder=mock_recorder)
        mock_mgr.get_source_status.return_value = {
            "source_id": "cam1",
            "status": "online",
            "running": True,
        }
        mock_mgr._bundles = {"cam1": mock_bundle}
        resp = client.post("/sources/cam1/restart")
        assert resp.status_code == 200
        assert resp.json()["status"] == "restarted"
        mock_pipeline.stop.assert_called_once()
        mock_pipeline.start.assert_called_once()

    def test_restart_not_found(self, client, mock_mgr):
        mock_mgr.get_source_status.return_value = None
        resp = client.post("/sources/nonexistent/restart")
        assert resp.status_code == 404


class TestPauseSource:
    def test_pause_success(self, client, mock_mgr):
        mock_mgr.pause_source.return_value = {
            "status": "paused",
            "source_id": "cam1",
        }
        resp = client.post("/sources/cam1/pause")
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    def test_pause_not_found(self, client, mock_mgr):
        mock_mgr.pause_source.return_value = {
            "status": "not_found",
            "source_id": "cam1",
        }
        resp = client.post("/sources/cam1/pause")
        assert resp.status_code == 404


class TestResumeSource:
    def test_resume_success(self, client, mock_mgr):
        mock_mgr.resume_source.return_value = {
            "status": "online",
            "source_id": "cam1",
        }
        resp = client.post("/sources/cam1/resume")
        assert resp.status_code == 200
        assert resp.json()["status"] == "online"

    def test_resume_not_found(self, client, mock_mgr):
        mock_mgr.resume_source.return_value = {
            "status": "not_found",
            "source_id": "cam1",
        }
        resp = client.post("/sources/cam1/resume")
        assert resp.status_code == 404
