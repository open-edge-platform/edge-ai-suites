"""Tests for pipeline hot-update and new API endpoints (PUT/DELETE)."""

from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.config import (
    AppConfig,
    SourceConfig,
    MotionConfig,
    SegmentConfig,
    PrefilterConfig,
    HealthConfig,
    DefaultsConfig,
    RecordingConfig,
)
from source_worker import SourceManager
from stream_monitor.rtsp_monitor import StreamPipeline
from sinks import NullSink


# =============================================================================
# StreamPipeline.update_pipeline_config() tests
# =============================================================================

def make_pipeline(source=None):
    """Create a StreamPipeline with mocked dependencies."""
    if source is None:
        source = SourceConfig(
            source_id="test_cam",
            source_url="rtsp://localhost:8554/live/test",
            prefilter=PrefilterConfig(enabled=False),
        )
    defaults = DefaultsConfig()
    with patch("stream_monitor.rtsp_monitor.cv2"):
        pipeline = StreamPipeline(
            source=source,
            defaults=defaults,
            data_dir="/tmp/test-update",
            sink=NullSink(),
        )
    return pipeline


class TestPipelineUpdateConfig:
    def test_update_motion_config(self):
        pipeline = make_pipeline()
        new_motion = MotionConfig(diff_threshold=50, area_ratio=0.1, stable_frames=60)
        pipeline.update_pipeline_config(motion=new_motion)
        assert pipeline._motion_cfg.diff_threshold == 50
        assert pipeline._motion_cfg.area_ratio == 0.1
        assert pipeline._motion_cfg.stable_frames == 60
        assert pipeline.source.motion == pipeline._motion_cfg

    def test_update_segment_config(self):
        pipeline = make_pipeline()
        new_segment = SegmentConfig(max_duration=5.0, min_duration=2.0)
        pipeline.update_pipeline_config(segment=new_segment)
        assert pipeline._segment_cfg.max_duration == 5.0
        assert pipeline._segment_cfg.min_duration == 2.0
        assert pipeline.source.segment == pipeline._segment_cfg

    def test_update_health_config(self):
        pipeline = make_pipeline()
        new_health = HealthConfig(max_failures=10, recovery_strategy="pause")
        pipeline.update_pipeline_config(health=new_health)
        assert pipeline._health_cfg.max_failures == 10
        assert pipeline._health_cfg.recovery_strategy == "pause"
        assert pipeline.source.health == pipeline._health_cfg

    def test_update_prefilter_triggers_rebuild(self):
        pipeline = make_pipeline()
        new_pf = PrefilterConfig(enabled=False)
        with patch.object(pipeline, "_init_prefilter") as mock_init:
            pipeline.update_pipeline_config(prefilter=new_pf)
            mock_init.assert_called_once()
        assert pipeline._prefilter_cfg.enabled is False

    def test_update_prefilter_preserves_existing_model_path(self):
        source = SourceConfig(
            source_id="test_cam",
            source_url="rtsp://localhost:8554/live/test",
            prefilter=PrefilterConfig(
                enabled=True,
                model_path="/models/default.xml",
                min_confidence=0.4,
            ),
        )
        pipeline = make_pipeline(source=source)
        with patch.object(pipeline, "_init_prefilter"):
            pipeline.update_pipeline_config(
                prefilter=PrefilterConfig(min_confidence=0.9)
            )
        assert pipeline._prefilter_cfg.enabled is True
        assert pipeline._prefilter_cfg.model_path == "/models/default.xml"
        assert pipeline._prefilter_cfg.min_confidence == 0.9

    def test_update_none_fields_no_change(self):
        pipeline = make_pipeline()
        original_motion = pipeline._motion_cfg
        original_segment = pipeline._segment_cfg
        pipeline.update_pipeline_config()
        assert pipeline._motion_cfg is original_motion
        assert pipeline._segment_cfg is original_segment

    def test_partial_update_only_changes_specified(self):
        pipeline = make_pipeline()
        original_segment = pipeline._segment_cfg
        new_motion = MotionConfig(diff_threshold=99)
        pipeline.update_pipeline_config(motion=new_motion)
        assert pipeline._motion_cfg.diff_threshold == 99
        assert pipeline._segment_cfg is original_segment


# =============================================================================
# SourceManager.update_pipeline_config() tests
# =============================================================================

@pytest.fixture
def mock_pipeline_class():
    with patch("source_worker.StreamPipeline") as mock_cls:
        instance = MagicMock()
        instance.is_running = True
        instance.status = "online"
        instance.rtsp_url = "rtsp://localhost:8554/live/test"
        instance.source = SourceConfig(
            source_id="test_cam", source_url="rtsp://localhost:8554/live/test"
        )
        instance.health_info = {
            "failure_count": 0,
            "last_failure_time": None,
            "reconnect_count": 0,
            "recovery_strategy": "retry",
            "max_failures": 30,
            "start_time": None,
        }
        mock_cls.return_value = instance
        yield mock_cls, instance


@pytest.fixture
def manager(mock_pipeline_class):
    with patch("source_worker.WebhookSink"):
        mgr = SourceManager(AppConfig())
    return mgr


class TestSourceManagerUpdate:
    def test_update_existing_source(self, manager, mock_pipeline_class):
        _, instance = mock_pipeline_class
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)

        result = manager.update_pipeline_config(
            source_id="cam1",
            motion=MotionConfig(diff_threshold=50),
        )
        assert result["status"] == "updated"
        assert result["source_id"] == "cam1"
        instance.stop.assert_called()
        instance.update_pipeline_config.assert_called_once_with(
            motion=MotionConfig(diff_threshold=50),
            segment=None,
            prefilter=None,
            roi=None,
            health=None,
        )
        # SourceManager.update_pipeline_config now also accepts `recording=`
        # for the continuous-recorder branch; pipeline's own update API stays
        # unchanged (no recording on StreamPipeline).
        instance.start.assert_called()

    def test_update_nonexistent_source(self, manager):
        result = manager.update_pipeline_config(
            source_id="nonexistent",
            motion=MotionConfig(diff_threshold=50),
        )
        assert result["status"] == "not_found"

    def test_update_calls_stop_then_start(self, manager, mock_pipeline_class):
        _, instance = mock_pipeline_class
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)
        instance.reset_mock()

        manager.update_pipeline_config(
            source_id="cam1",
            segment=SegmentConfig(max_duration=5.0),
        )

        calls = instance.method_calls
        stop_idx = next(i for i, c in enumerate(calls) if c[0] == "stop")
        update_idx = next(i for i, c in enumerate(calls) if c[0] == "update_pipeline_config")
        start_idx = next(i for i, c in enumerate(calls) if c[0] == "start")
        assert stop_idx < update_idx < start_idx

    def test_partial_recording_update_preserves_existing_values(self, manager, mock_pipeline_class):
        _, instance = mock_pipeline_class
        source = SourceConfig(
            source_id="cam1",
            source_url="rtsp://localhost:8554/live/cam1",
        )
        manager.register_source(source)
        instance.source.recording = RecordingConfig(
            enabled=True,
            interval_seconds=60,
            fps=15,
            retention_days=5,
        )

        manager.update_pipeline_config(
            source_id="cam1",
            recording=RecordingConfig(fps=25),
        )

        updated = instance.source.recording
        assert updated is not None
        assert updated.fps == 25
        assert updated.enabled is True
        assert updated.interval_seconds == 60
        assert updated.retention_days == 5


class TestSourceManagerRemoveCallback:
    def test_handle_source_removed(self, manager, mock_pipeline_class):
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)
        assert manager.get_source_status("cam1") is not None

        manager._handle_source_removed("cam1")
        assert manager.get_source_status("cam1") is None

    def test_handle_source_removed_nonexistent(self, manager):
        manager._handle_source_removed("nonexistent")


class TestSourceManagerHealthInStatus:
    def test_get_sources_includes_health(self, manager, mock_pipeline_class):
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)
        sources = manager.get_sources()
        assert "health" in sources[0]
        assert sources[0]["health"]["recovery_strategy"] == "retry"

    def test_get_source_status_includes_health(self, manager, mock_pipeline_class):
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)
        status = manager.get_source_status("cam1")
        assert "health" in status
        assert status["health"]["max_failures"] == 30


# =============================================================================
# FastAPI endpoint tests: PUT /sources/{id}/pipeline, DELETE /sources/{id}
# =============================================================================

@pytest.fixture
def api_client():
    """Create test client using the actual service.create_app."""
    from service import create_app

    config = AppConfig()
    app = create_app(config)

    with patch("source_worker.StreamPipeline") as mock_cls, \
         patch("source_worker.WebhookSink"):
        instance = MagicMock()
        instance.is_running = True
        instance.status = "online"
        instance.rtsp_url = "rtsp://localhost:8554/live/test"
        instance.source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/test"
        )
        instance.health_info = {
            "failure_count": 0,
            "last_failure_time": None,
            "reconnect_count": 0,
            "recovery_strategy": "retry",
            "max_failures": 30,
            "start_time": None,
        }
        mock_cls.return_value = instance

        with TestClient(app, raise_server_exceptions=False) as tc:
            yield tc


_REG_BODY = {
    "source_id": "cam1",
    "source_url": "rtsp://localhost:8554/live/test",
}


class TestUpdatePipelineEndpoint:
    def test_update_pipeline_success(self, api_client):
        api_client.post("/register_source", json=_REG_BODY)
        resp = api_client.put("/sources/cam1/pipeline", json={
            "pipeline": {
                "motion": {"diff_threshold": 50, "area_ratio": 0.1, "stable_frames": 60},
            },
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    def test_update_pipeline_not_found(self, api_client):
        resp = api_client.put("/sources/nonexistent/pipeline", json={
            "pipeline": {"motion": {"diff_threshold": 50}},
        })
        assert resp.status_code == 404

    def test_update_pipeline_empty_body(self, api_client):
        api_client.post("/register_source", json=_REG_BODY)
        resp = api_client.put("/sources/cam1/pipeline", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    def test_update_pipeline_health_config(self, api_client):
        api_client.post("/register_source", json=_REG_BODY)
        resp = api_client.put("/sources/cam1/pipeline", json={
            "pipeline": {
                "health": {"max_failures": 10, "recovery_strategy": "pause"},
            },
        })
        assert resp.status_code == 200


class TestDeleteSourceEndpoint:
    def test_delete_source_success(self, api_client):
        api_client.post("/register_source", json=_REG_BODY)
        resp = api_client.delete("/sources/cam1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    def test_delete_source_not_found(self, api_client):
        resp = api_client.delete("/sources/nonexistent")
        assert resp.status_code == 404

    def test_delete_source_removes_from_list(self, api_client):
        api_client.post("/register_source", json=_REG_BODY)
        api_client.delete("/sources/cam1")
        resp = api_client.get("/sources")
        # /sources is a bare array
        assert resp.json() == []
