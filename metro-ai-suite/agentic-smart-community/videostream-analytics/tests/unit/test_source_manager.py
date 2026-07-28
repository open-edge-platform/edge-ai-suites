"""Tests for SourceManager with mocked StreamPipeline."""

from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from shared.config import AppConfig, SourceConfig
from source_worker import SourceManager


@pytest.fixture
def config():
    return AppConfig()


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
        mock_cls.return_value = instance
        yield mock_cls, instance


@pytest.fixture
def manager(config, mock_pipeline_class):
    with patch("source_worker.WebhookSink"):
        mgr = SourceManager(config)
    return mgr


class TestSourceManagerRegister:
    def test_register_source_creates_and_starts_pipeline(self, manager, mock_pipeline_class):
        _, instance = mock_pipeline_class
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        result = manager.register_source(source)
        assert result["status"] == "started"
        assert result["source_id"] == "cam1"
        instance.start.assert_called_once()

    def test_register_duplicate_running_returns_already_running(self, manager, mock_pipeline_class):
        _, instance = mock_pipeline_class
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)
        result = manager.register_source(source)
        assert result["status"] == "already_running"

    def test_register_duplicate_stopped_restarts(self, manager, mock_pipeline_class):
        mock_cls, instance = mock_pipeline_class
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)
        # Simulate pipeline stopped
        instance.is_running = False
        result = manager.register_source(source)
        assert result["status"] == "started"
        instance.stop.assert_called()


class TestSourceManagerUnregister:
    def test_unregister_existing_stops_pipeline(self, manager, mock_pipeline_class):
        _, instance = mock_pipeline_class
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)
        result = manager.unregister_source("cam1")
        assert result["status"] == "stopped"
        instance.stop.assert_called()

    def test_unregister_nonexistent_returns_not_found(self, manager):
        result = manager.unregister_source("nonexistent")
        assert result["status"] == "not_found"


class TestSourceManagerQuery:
    def test_get_sources_empty(self, manager):
        sources = manager.get_sources()
        assert sources == []

    def test_get_sources_after_register(self, manager, mock_pipeline_class):
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)
        sources = manager.get_sources()
        assert len(sources) == 1
        assert sources[0]["source_id"] == "cam1"
        assert sources[0]["running"] is True

    def test_get_source_status_existing(self, manager, mock_pipeline_class):
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)
        status = manager.get_source_status("cam1")
        assert status is not None
        assert status["source_id"] == "cam1"
        assert status["running"] is True

    def test_get_source_status_nonexistent(self, manager):
        assert manager.get_source_status("nope") is None


class TestSourceManagerPerSourceWebhook:
    def test_register_with_webhook_url_creates_dedicated_sink(self, config, mock_pipeline_class):
        mock_cls, instance = mock_pipeline_class
        with patch("source_worker.WebhookSink") as mock_ws:
            mock_ws.return_value = MagicMock()
            mgr = SourceManager(config)
            # First call is default sink in __init__
            default_call_count = mock_ws.call_count

            source = SourceConfig(
                source_id="cam1",
                source_url="rtsp://localhost:8554/live/cam1",
                webhook_url="http://other-server:9000/events",
            )
            mgr.register_source(source)

            # Should have created a second WebhookSink with the per-source URL
            assert mock_ws.call_count == default_call_count + 1
            last_call_args = mock_ws.call_args
            webhook_cfg = last_call_args[0][0]
            assert webhook_cfg.url == "http://other-server:9000/events"

    def test_register_without_webhook_url_uses_default_sink(self, manager, mock_pipeline_class):
        mock_cls, instance = mock_pipeline_class
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)
        # Pipeline should receive the default sink
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["sink"] is manager._default_sink


class TestSourceManagerStopAll:
    def test_stop_all_clears_pipelines(self, manager, mock_pipeline_class):
        _, instance = mock_pipeline_class
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)
        manager.stop_all()
        assert manager.get_sources() == []
        instance.stop.assert_called()
