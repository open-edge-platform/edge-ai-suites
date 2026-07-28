"""Tests for pause/resume functionality at pipeline and manager level."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from shared.config import (
    AppConfig,
    SourceConfig,
    DefaultsConfig,
    MotionConfig,
    SegmentConfig,
)
from stream_monitor.rtsp_monitor import StreamPipeline
from source_worker import SourceManager
from sinks import EventSink


class TestStreamPipelinePauseResume:
    @pytest.fixture
    def mock_sink(self):
        sink = MagicMock(spec=EventSink)
        sink.emit.return_value = True
        return sink

    @pytest.fixture
    def pipeline(self, tmp_path, mock_sink):
        source = SourceConfig(
            source_id="test_pause", source_url="rtsp://localhost:8554/live/test"
        )
        defaults = DefaultsConfig(
            motion=MotionConfig(),
            segment=SegmentConfig(),
        )
        p = StreamPipeline(
            source=source,
            defaults=defaults,
            data_dir=str(tmp_path),
            sink=mock_sink,
        )
        return p

    def test_pause_sets_status(self, pipeline):
        pipeline._running = True
        pipeline._status = "online"
        pipeline.pause()
        assert pipeline.status == "paused"
        assert not pipeline._paused.is_set()

    def test_resume_sets_status(self, pipeline):
        pipeline._running = True
        pipeline._status = "paused"
        pipeline._paused.clear()
        pipeline.resume()
        assert pipeline.status == "online"
        assert pipeline._paused.is_set()

    def test_pause_when_not_running_is_noop(self, pipeline):
        pipeline._running = False
        pipeline._status = "stopped"
        pipeline.pause()
        assert pipeline.status == "stopped"
        assert pipeline._paused.is_set()

    def test_resume_when_not_paused_is_noop(self, pipeline):
        pipeline._running = True
        pipeline._status = "online"
        pipeline.resume()
        assert pipeline.status == "online"

    def test_pause_sets_status_without_webhook(self, pipeline, mock_sink):
        pipeline._running = True
        pipeline._status = "online"
        pipeline.pause()
        # §32: RTSP status is no longer pushed to the /events webhook. Internal
        # status is still updated (MCP reads it via GET /sources/{id}/status), but
        # no `status` envelope is emitted to the sink.
        assert pipeline.status == "paused"
        status_emits = [
            c.args[0] for c in mock_sink.emit.call_args_list
            if c.args and c.args[0].get("type") == "status"
        ]
        assert status_emits == []

    def test_resume_sets_status_without_webhook(self, pipeline, mock_sink):
        pipeline._running = True
        pipeline._status = "paused"
        pipeline._paused.clear()
        pipeline.resume()
        assert pipeline.status == "online"
        status_emits = [
            c.args[0] for c in mock_sink.emit.call_args_list
            if c.args and c.args[0].get("type") == "status"
        ]
        assert status_emits == []

    def test_stop_unblocks_paused_pipeline(self, pipeline):
        pipeline._running = True
        pipeline._paused.clear()
        pipeline.stop()
        assert pipeline._paused.is_set()
        assert pipeline.status == "stopped"


class TestSourceManagerPauseResume:
    @pytest.fixture
    def config(self):
        return AppConfig()

    @pytest.fixture
    def mock_pipeline_class(self):
        with patch("source_worker.StreamPipeline") as mock_cls:
            instance = MagicMock()
            instance.is_running = True
            instance.status = "online"
            instance.rtsp_url = "rtsp://localhost:8554/live/test"
            instance.source = SourceConfig(
                source_id="cam_test", source_url="rtsp://localhost:8554/live/test"
            )
            mock_cls.return_value = instance
            yield mock_cls, instance

    @pytest.fixture
    def manager(self, config, mock_pipeline_class):
        with patch("source_worker.WebhookSink"):
            mgr = SourceManager(config)
        return mgr

    def test_pause_existing_source(self, manager, mock_pipeline_class):
        _, instance = mock_pipeline_class
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)
        result = manager.pause_source("cam1")
        assert result["status"] == "paused"
        instance.pause.assert_called_once()

    def test_pause_nonexistent_source(self, manager):
        result = manager.pause_source("nonexistent")
        assert result["status"] == "not_found"

    def test_pause_stopped_source(self, manager, mock_pipeline_class):
        _, instance = mock_pipeline_class
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)
        instance.is_running = False
        result = manager.pause_source("cam1")
        assert result["status"] == "not_running"

    def test_resume_existing_source(self, manager, mock_pipeline_class):
        _, instance = mock_pipeline_class
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)
        result = manager.resume_source("cam1")
        assert result["status"] == "online"
        instance.resume.assert_called_once()

    def test_resume_nonexistent_source(self, manager):
        result = manager.resume_source("nonexistent")
        assert result["status"] == "not_found"
