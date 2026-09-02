"""Tests for FastAPI endpoints with mocked SourceManager.

The request schemas in service.py use the nested `pipeline` wrapper and
reject the old flat format with HTTP 422.
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
        # /sources returns a bare array, not {"sources": [...]}
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
        """pipeline.roi top-level block must be accepted.

        No `model_path` here on purpose: this test is about the `roi` block, and
        a request-supplied model path would drag in the containment check
        (`TestModelPathContainment`) for no reason. Omitting it makes the
        prefilter inherit the deployment default, which is what MCP does.
        """
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
        """Old rtsp_url / top-level motion must 422."""
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
        resp = client.delete("/sources/cam1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    def test_unregister_not_found(self, client, mock_mgr):
        mock_mgr.unregister_source.return_value = {
            "status": "not_found",
            "source_id": "nonexistent",
        }
        resp = client.delete("/sources/nonexistent")
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
    """Restart is delegated to `SourceManager.restart_source`.

    The endpoint used to reach into `mgr._bundles` and drive stop/start itself,
    which meant it ran outside the per-source lock and could interleave with an
    unregister. The stop/start sequencing is covered by
    `test_source_manager.py`; here we only assert the delegation.
    """

    def test_restart_success(self, client, mock_mgr):
        mock_mgr.restart_source.return_value = {
            "status": "restarted",
            "source_id": "cam1",
        }
        resp = client.post("/sources/cam1/restart")
        assert resp.status_code == 200
        assert resp.json()["status"] == "restarted"
        mock_mgr.restart_source.assert_called_once_with("cam1")

    def test_restart_not_found(self, client, mock_mgr):
        mock_mgr.restart_source.return_value = {
            "status": "not_found",
            "source_id": "nonexistent",
        }
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


class TestPrefilterCapabilities:
    def test_capabilities_unavailable_without_model(self, client):
        """Default AppConfig ships an empty prefilter.model_path → unavailable."""
        resp = client.get("/capabilities/prefilter")
        assert resp.status_code == 200
        data = resp.json()
        assert data["labels_source"] == "unavailable"
        assert data["class_names"] == []
        assert data["available_devices"]  # non-empty (at least ["CPU"])

    def test_capabilities_embedded_labels(self, client, monkeypatch, tmp_path):
        model = tmp_path / "model.xml"
        model.write_text("<net/>")
        import stream_monitor.pipeline.prefilter_yolo as pf

        monkeypatch.setattr(pf, "read_model_labels",
                            lambda p: (["person", "knife"], "embedded"))
        # The endpoint reads config.defaults.prefilter from the create_app
        # closure, which is the same object as app.state.config.
        client.app.state.config.defaults.prefilter.model_path = str(model)
        resp = client.get("/capabilities/prefilter")
        assert resp.status_code == 200
        data = resp.json()
        assert data["labels_source"] == "embedded"
        assert data["class_names"] == ["person", "knife"]


class TestTargetClassesValidation:
    def _model(self, client, tmp_path):
        """Create a model file and make its directory a permitted model root.

        `AppConfig()` ships no `defaults.prefilter.model_path`, so there is no
        model root at all by default and `validate_model_path` rejects every
        request-supplied path with 400 (see `TestModelPathContainment`). Same
        closure-sharing trick as `test_capabilities_embedded_labels`:
        `app.state.config` IS the object `create_app` closed over.
        """
        model = tmp_path / "model.xml"
        model.write_text("<net/>")
        client.app.state.config.security.allowed_model_roots.append(str(tmp_path))
        return str(model)

    def test_register_rejects_unknown_target_class(self, client, mock_mgr, monkeypatch, tmp_path):
        import stream_monitor.pipeline.prefilter_yolo as pf
        monkeypatch.setattr(pf, "read_model_labels",
                            lambda p: (["person", "knife"], "embedded"))
        resp = client.post("/register_source", json={
            "source_id": "cam1",
            "source_url": "rtsp://localhost:8554/live/cam1",
            "pipeline": {
                "prefilter": {
                    "enabled": True,
                    "model_path": self._model(client, tmp_path),
                    "target_classes": ["person", "helmets"],
                },
            },
        })
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "unknown target_classes"
        assert detail["unknown"] == ["helmets"]
        assert "knife" in detail["class_names"]

    def test_register_accepts_valid_target_class(self, client, mock_mgr, monkeypatch, tmp_path):
        import stream_monitor.pipeline.prefilter_yolo as pf
        monkeypatch.setattr(pf, "read_model_labels",
                            lambda p: (["person", "knife"], "embedded"))
        mock_mgr.register_source.return_value = {"status": "started", "source_id": "cam1"}
        resp = client.post("/register_source", json={
            "source_id": "cam1",
            "source_url": "rtsp://localhost:8554/live/cam1",
            "pipeline": {
                "prefilter": {
                    "enabled": True,
                    "model_path": self._model(client, tmp_path),
                    "target_classes": ["person", "knife"],
                },
            },
        })
        assert resp.status_code == 200

    def test_register_skips_validation_when_labels_untrusted(self, client, mock_mgr, monkeypatch, tmp_path):
        """A fallback_coco/unavailable label set is a guess — don't hard-fail."""
        import stream_monitor.pipeline.prefilter_yolo as pf
        monkeypatch.setattr(pf, "read_model_labels",
                            lambda p: (["person"], "fallback_coco"))
        mock_mgr.register_source.return_value = {"status": "started", "source_id": "cam1"}
        resp = client.post("/register_source", json={
            "source_id": "cam1",
            "source_url": "rtsp://localhost:8554/live/cam1",
            "pipeline": {
                "prefilter": {
                    "enabled": True,
                    "model_path": self._model(client, tmp_path),
                    "target_classes": ["anything_goes"],
                },
            },
        })
        assert resp.status_code == 200


class TestSourceIdValidation:
    """`source_id` reaches the filesystem as `<data_dir>/<source_id>`.

    Same regex as the dashboard's `monitorIdSchema`
    (packages/mcp-server/src/dashboard/router.ts), so an id MCP accepts is an
    id VSA accepts.
    """

    @pytest.mark.parametrize("source_id", ["cam_ok\n", "cam_ok\r", "cam_ok\t"])
    def test_trailing_whitespace_is_not_a_bypass(self, client, mock_mgr, source_id):
        """`$` must not match before a trailing newline.

        Python's `re` treats `^...$` as newline-lax, so `"cam_ok\\n"` would slip
        through and become a directory name. pydantic v2's default rust-regex
        engine anchors strictly; this test fails loudly if that ever changes
        (e.g. someone sets `regex_engine="python-re"`).
        """
        resp = client.post(
            "/register_source",
            json={"source_id": source_id, "source_url": "rtsp://localhost:8554/live/x"},
        )
        assert resp.status_code == 422
        mock_mgr.register_source.assert_not_called()

    @pytest.mark.parametrize(
        "source_id",
        ["../../tmp/pwn", "..", "a/b", "cam child", "cam.child", "", "x" * 129],
    )
    def test_register_rejects_invalid_source_id(self, client, mock_mgr, source_id):
        resp = client.post(
            "/register_source",
            json={"source_id": source_id, "source_url": "rtsp://localhost:8554/live/x"},
        )
        assert resp.status_code == 422
        mock_mgr.register_source.assert_not_called()

    @pytest.mark.parametrize("source_id", ["cam_child", "cam-1", "CAM1", "x" * 128])
    def test_register_accepts_valid_source_id(self, client, mock_mgr, source_id):
        mock_mgr.register_source.return_value = {"status": "started", "source_id": source_id}
        resp = client.post(
            "/register_source",
            json={"source_id": source_id, "source_url": "rtsp://localhost:8554/live/x"},
        )
        assert resp.status_code == 200

    def test_path_param_traversal_is_rejected(self, client, mock_mgr):
        resp = client.get("/sources/..%2F..%2Fetc")
        assert resp.status_code in (404, 422)
        mock_mgr.get_source_status.assert_not_called()

    def test_delete_with_invalid_id_is_rejected(self, client, mock_mgr):
        resp = client.delete("/sources/cam%20child")
        assert resp.status_code == 422
        mock_mgr.unregister_source.assert_not_called()


class TestRequestFieldValidation:
    def test_relative_data_dir_is_rejected(self, client, mock_mgr):
        """The reported §1.1 repro: `data_dir: "fuzzstring"` used to 500."""
        resp = client.post(
            "/register_source",
            json={
                "source_id": "fuzz-repro",
                "source_url": "rtsp://localhost:8554/live/x",
                "data_dir": "fuzzstring",
            },
        )
        assert resp.status_code == 422
        mock_mgr.register_source.assert_not_called()

    def test_empty_source_url_is_rejected(self, client, mock_mgr):
        resp = client.post(
            "/register_source", json={"source_id": "cam1", "source_url": ""}
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "webhook_url",
        ["ftp://host/x", "file:///etc/passwd", "not-a-url", "http://u:p@host/x", "http://"],
    )
    def test_bad_webhook_url_is_rejected(self, client, mock_mgr, webhook_url):
        resp = client.post(
            "/register_source",
            json={
                "source_id": "cam1",
                "source_url": "rtsp://localhost:8554/live/x",
                "webhook_url": webhook_url,
            },
        )
        assert resp.status_code == 422
        mock_mgr.register_source.assert_not_called()

    def test_good_webhook_url_is_accepted(self, client, mock_mgr):
        mock_mgr.register_source.return_value = {"status": "started", "source_id": "cam1"}
        resp = client.post(
            "/register_source",
            json={
                "source_id": "cam1",
                "source_url": "rtsp://localhost:8554/live/x",
                "webhook_url": "http://localhost:3101/events",
            },
        )
        assert resp.status_code == 200

    def test_control_characters_are_rejected(self, client, mock_mgr):
        resp = client.post(
            "/register_source",
            json={"source_id": "cam1", "source_url": "rtsp://host/\x00x"},
        )
        assert resp.status_code == 422

    def test_out_of_range_pipeline_value_is_rejected(self, client, mock_mgr):
        resp = client.post(
            "/register_source",
            json={
                "source_id": "cam1",
                "source_url": "rtsp://localhost:8554/live/x",
                "pipeline": {"motion": {"area_ratio": 5.0}},
            },
        )
        assert resp.status_code == 422

    def test_unknown_recovery_strategy_is_rejected(self, client, mock_mgr):
        resp = client.post(
            "/register_source",
            json={
                "source_id": "cam1",
                "source_url": "rtsp://localhost:8554/live/x",
                "pipeline": {"health": {"recovery_strategy": "fuzzstring"}},
            },
        )
        assert resp.status_code == 422


class TestErrorMapping:
    """Business-layer failures must map to a deliberate status, never a bare 500."""

    def test_oserror_becomes_400(self, client, mock_mgr):
        mock_mgr.register_source.side_effect = PermissionError(
            13, "Permission denied", "/home/someone/secret/segments"
        )
        resp = client.post(
            "/register_source",
            json={"source_id": "cam1", "source_url": "rtsp://localhost:8554/live/x"},
        )
        assert resp.status_code == 400

    def test_400_body_does_not_leak_server_paths(self, client, mock_mgr):
        mock_mgr.register_source.side_effect = PermissionError(
            13, "Permission denied", "/home/someone/secret/segments"
        )
        resp = client.post(
            "/register_source",
            json={"source_id": "cam1", "source_url": "rtsp://localhost:8554/live/x"},
        )
        assert "/home/someone/secret" not in resp.text
        assert resp.json()["detail"]["reason"] == "PermissionError"

    def test_value_error_becomes_400(self, client, mock_mgr):
        mock_mgr.register_source.side_effect = ValueError(
            "path escapes the permitted data root(s)"
        )
        resp = client.post(
            "/register_source",
            json={"source_id": "cam1", "source_url": "rtsp://localhost:8554/live/x"},
        )
        assert resp.status_code == 400

    def test_connection_error_becomes_503(self, client, mock_mgr):
        """ffmpeg missing from PATH is a server defect, not a bad request."""
        mock_mgr.register_source.side_effect = ConnectionError(
            "ffmpeg not found on PATH; cannot record (copy backend)"
        )
        resp = client.post(
            "/register_source",
            json={"source_id": "cam1", "source_url": "rtsp://localhost:8554/live/x"},
        )
        assert resp.status_code == 503
        assert resp.json()["detail"]["error"] == "dependency_unavailable"

    def test_delete_maps_oserror_to_400(self, client, mock_mgr):
        mock_mgr.unregister_source.side_effect = OSError("boom")
        resp = client.delete("/sources/cam1")
        assert resp.status_code == 400

    def test_update_pipeline_maps_value_error_to_400(self, client, mock_mgr):
        mock_mgr.update_pipeline_config.side_effect = ValueError(
            "effective segment.min_duration (30.0) must not exceed"
        )
        resp = client.put(
            "/sources/cam1/pipeline", json={"pipeline": {"segment": {"min_duration": 30}}}
        )
        assert resp.status_code == 400

    def test_partial_segment_update_is_not_rejected_by_schema(self, client, mock_mgr):
        """A lone `min_duration` must reach the manager, not 422 at the schema."""
        mock_mgr.update_pipeline_config.return_value = {
            "status": "updated",
            "source_id": "cam1",
        }
        resp = client.put(
            "/sources/cam1/pipeline", json={"pipeline": {"segment": {"min_duration": 30}}}
        )
        assert resp.status_code == 200
        mock_mgr.update_pipeline_config.assert_called_once()


class TestSourceUrlSchemeAllowlist:
    """`source_url` reaches `ffmpeg -i` and cv2.VideoCapture verbatim.

    ffmpeg speaks `file:`, `concat:`, `subfile:`, `data:` … so an unrestricted
    scheme is an arbitrary-file-read whose output lands in `data_dir`, which the
    MCP dashboard serves back as mp4.
    """

    @pytest.mark.parametrize(
        "source_url",
        [
            "file:///etc/shadow",
            "concat:/etc/passwd|/etc/shadow",
            "subfile,,start,0,end,100,,:/etc/passwd",
            "data:text/plain;base64,AAAA",
            "ftp://host/x",
            "/etc/passwd",
            "relative/path.mp4",
        ],
    )
    def test_disallowed_scheme_is_rejected(self, client, mock_mgr, source_url):
        resp = client.post(
            "/register_source", json={"source_id": "cam1", "source_url": source_url}
        )
        assert resp.status_code == 400, source_url
        mock_mgr.register_source.assert_not_called()

    @pytest.mark.parametrize(
        "source_url",
        [
            "rtsp://localhost:8554/live/x",
            "rtsps://localhost:8555/live/x",
            "http://cam.local/stream.m3u8",
            "https://cam.local/stream.m3u8",
        ],
    )
    def test_allowed_scheme_is_accepted(self, client, mock_mgr, source_url):
        mock_mgr.register_source.return_value = {"status": "started", "source_id": "cam1"}
        resp = client.post(
            "/register_source", json={"source_id": "cam1", "source_url": source_url}
        )
        assert resp.status_code == 200, source_url

    def test_scheme_check_is_case_insensitive(self, client, mock_mgr):
        resp = client.post(
            "/register_source",
            json={"source_id": "cam1", "source_url": "FILE:///etc/shadow"},
        )
        assert resp.status_code == 400

    def test_file_source_allowed_when_opted_in(self, mock_manager, monkeypatch):
        """`allow_file_source` exists for offline evaluation against local clips."""
        from fastapi.testclient import TestClient

        import service as service_module
        from service import create_app
        from shared.config import AppConfig

        config = AppConfig()
        config.security.allow_file_source = True
        app = create_app(config)
        with TestClient(app, raise_server_exceptions=False) as tc:
            monkeypatch.setattr(service_module, "_manager", mock_manager)
            mock_manager.register_source.return_value = {
                "status": "started",
                "source_id": "cam1",
            }
            resp = tc.post(
                "/register_source",
                json={"source_id": "cam1", "source_url": "file:///tmp/sample.mp4"},
            )
        assert resp.status_code == 200


class TestConcurrentRegistration:
    def test_concurrent_registration_of_same_id_returns_409(self, client, mock_mgr):
        """Second concurrent register for one id is refused, not queued.

        Queueing would park a threadpool worker through a 20s teardown, which is
        exactly the amplification an unauthenticated caller would want.
        """
        mock_mgr.register_source.return_value = {
            "status": "registration_in_progress",
            "source_id": "cam1",
        }
        resp = client.post(
            "/register_source",
            json={"source_id": "cam1", "source_url": "rtsp://localhost:8554/live/x"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"] == "registration_in_progress"


class TestModelPathContainment:
    """A request-supplied `model_path` must resolve under a permitted root.

    The value reaches `openvino.Core().read_model()` twice — once in
    `_validate_target_classes` via `Path(...).exists()` + `read_model_labels`,
    and again in `rtsp_monitor._init_prefilter` on the running pipeline — and
    the API has no authentication. Unconfined, it is a file-existence oracle
    plus a way to have arbitrary server files parsed as an IR model
    (CodeQL `py/path-injection`).

    Permitted roots are the directory of `defaults.prefilter.model_path` plus
    `security.allowed_model_roots`. `AppConfig()` sets neither, so the default
    posture is "reject every request-supplied model_path".
    """

    def _register(self, client, model_path):
        return client.post(
            "/register_source",
            json={
                "source_id": "cam1",
                "source_url": "rtsp://localhost:8554/live/x",
                "pipeline": {
                    "prefilter": {
                        "enabled": True,
                        "model_path": model_path,
                        "target_classes": ["person"],
                    },
                },
            },
        )

    def _update(self, client, model_path):
        return client.put(
            "/sources/cam1/pipeline",
            json={
                "pipeline": {
                    "prefilter": {
                        "enabled": True,
                        "model_path": model_path,
                        "target_classes": ["person"],
                    },
                },
            },
        )

    @staticmethod
    def _permit(client, root):
        client.app.state.config.security.allowed_model_roots.append(str(root))

    def test_no_root_configured_rejects_any_model_path(self, client, mock_mgr):
        """Default posture: nothing configured -> nothing accepted."""
        resp = self._register(client, "/etc/shadow")
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "invalid_request"

    def test_path_inside_root_is_accepted(self, client, mock_mgr, tmp_path):
        """Inside a permitted root the request goes through.

        The file need not exist: containment is a path check, not an existence
        check, and `_validate_target_classes` already treats a missing model as
        "labels unavailable" and skips.
        """
        mock_mgr.register_source.return_value = {"status": "started", "source_id": "cam1"}
        self._permit(client, tmp_path)
        resp = self._register(client, str(tmp_path / "sub" / "model.xml"))
        assert resp.status_code == 200

    def test_path_outside_root_is_rejected(self, client, mock_mgr, tmp_path):
        self._permit(client, tmp_path / "allowed")
        resp = self._register(client, str(tmp_path / "elsewhere" / "model.xml"))
        assert resp.status_code == 400

    def test_traversal_out_of_root_is_rejected(self, client, mock_mgr, tmp_path):
        """`..` must not walk out — normalization happens before the check."""
        self._permit(client, tmp_path / "allowed")
        resp = self._register(
            client, str(tmp_path / "allowed" / ".." / "etc" / "model.xml")
        )
        assert resp.status_code == 400

    def test_sibling_prefix_is_not_contained(self, client, mock_mgr, tmp_path):
        """`<root>-evil/x` shares a string prefix with `<root>` but is outside.

        This is why containment appends `os.sep` before comparing.
        """
        root = tmp_path / "models"
        root.mkdir()
        (tmp_path / "models-evil").mkdir()
        self._permit(client, root)
        resp = self._register(client, str(tmp_path / "models-evil" / "model.xml"))
        assert resp.status_code == 400

    def test_symlink_escape_is_rejected(self, client, mock_mgr, tmp_path):
        """A symlink inside the root pointing out of it must not smuggle access."""
        root = tmp_path / "models"
        root.mkdir()
        outside = tmp_path / "secrets"
        outside.mkdir()
        (outside / "model.xml").write_text("<net/>")
        (root / "link").symlink_to(outside)
        self._permit(client, root)
        resp = self._register(client, str(root / "link" / "model.xml"))
        assert resp.status_code == 400

    def test_resolved_path_is_substituted(self, client, mock_mgr, tmp_path):
        """The SourceConfig must carry the RESOLVED path, not the raw request.

        Substitution is what keeps the running pipeline
        (`rtsp_monitor._init_prefilter`) from loading an unnormalized path, and
        it is what puts the containment check on the data flow that reaches the
        sink — a validate-and-discard helper would satisfy neither.
        """
        mock_mgr.register_source.return_value = {"status": "started", "source_id": "cam1"}
        root = tmp_path / "models"
        root.mkdir()
        self._permit(client, root)
        resp = self._register(client, str(root / "." / "model.xml"))
        assert resp.status_code == 200
        ((source_arg,), _) = mock_mgr.register_source.call_args
        assert source_arg.prefilter.model_path == str(
            (root / "model.xml").resolve()
        )

    def test_absent_model_path_inherits_trusted_default(self, client, mock_mgr, tmp_path):
        """Omitting model_path must NOT be blocked by containment.

        This is the MCP path — it never sends `model_path`, so every real
        request inherits `defaults.prefilter.model_path`, which is trusted
        config and deliberately not re-checked.
        """
        mock_mgr.register_source.return_value = {"status": "started", "source_id": "cam1"}
        client.app.state.config.defaults.prefilter.model_path = str(
            tmp_path / "deployment" / "model.xml"
        )
        resp = client.post(
            "/register_source",
            json={
                "source_id": "cam1",
                "source_url": "rtsp://localhost:8554/live/x",
                "pipeline": {"prefilter": {"enabled": True, "target_classes": ["person"]}},
            },
        )
        assert resp.status_code == 200

    def test_deployment_model_directory_is_a_root(self, client, mock_mgr, tmp_path):
        """A sibling of the deployment model is accepted with no extra config.

        `_model_roots` derives the root from `defaults.prefilter.model_path`, so
        the standard deployment can switch models within its own model dir
        without anyone setting `allowed_model_roots`.
        """
        mock_mgr.register_source.return_value = {"status": "started", "source_id": "cam1"}
        model_dir = tmp_path / "openvino" / "yolo11s" / "FP16"
        model_dir.mkdir(parents=True)
        client.app.state.config.defaults.prefilter.model_path = str(
            model_dir / "yolo11s.xml"
        )
        resp = self._register(client, str(model_dir / "yolo11m.xml"))
        assert resp.status_code == 200

    def test_overlong_model_path_does_not_500(self, client, mock_mgr):
        """Regression: a fuzzed over-long model_path must not reach `Path.exists()`.

        History: `Path.exists()` only swallows ENOENT/ENOTDIR/ELOOP, so a
        model_path longer than NAME_MAX raised ENAMETOOLONG and escaped
        `_validate_target_classes` as a bare 500 (InvalidValueChecker_500 on
        both register_source and PUT /pipeline). That was first fixed by
        treating an un-stat-able path as missing; containment now rejects it
        earlier and for a better reason — it is not under a permitted root —
        so the response is a deliberate 400. What must never come back is 500.
        """
        resp = self._register(client, "z" * 2000)
        assert resp.status_code == 400

    def test_overlong_model_path_on_update_pipeline(self, client, mock_mgr):
        resp = self._update(client, "z" * 2000)
        assert resp.status_code == 400

    def test_relative_model_path_is_rejected(self, client, mock_mgr, tmp_path):
        self._permit(client, tmp_path)
        resp = self._register(client, "models/model.xml")
        assert resp.status_code == 400


class TestConfiguredModelPathStatFailure:
    """The OSError-from-`exists()` fallback now only guards the TRUSTED path.

    Request-supplied paths are rejected by `validate_model_path` before they
    reach `Path(...).exists()` (see `TestModelPathContainment`), but
    `defaults.prefilter.model_path` is not containment-checked, so a mistyped
    config.yaml can still land in that `except OSError` branch. It must degrade
    to "labels unavailable, skip the check" rather than crash.
    """

    def test_exists_oserror_on_configured_default_is_treated_as_missing(
        self, client, mock_mgr, monkeypatch
    ):
        from pathlib import Path as _P

        monkeypatch.setattr(
            _P, "exists", lambda self: (_ for _ in ()).throw(OSError("boom"))
        )
        mock_mgr.register_source.return_value = {"status": "started", "source_id": "cam1"}
        client.app.state.config.defaults.prefilter.model_path = "/some/model.xml"
        resp = client.post(
            "/register_source",
            json={
                "source_id": "cam1",
                "source_url": "rtsp://localhost:8554/live/x",
                "pipeline": {"prefilter": {"enabled": True, "target_classes": ["person"]}},
            },
        )
        assert resp.status_code == 200
