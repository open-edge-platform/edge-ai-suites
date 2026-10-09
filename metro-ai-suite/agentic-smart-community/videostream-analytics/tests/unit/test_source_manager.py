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


class TestSourceManagerConcurrency:
    """The registry race the fuzz run likely tripped.

    `register_source` used to be read-build-write on a bare dict: two concurrent
    calls for the same id each built a full pipeline + recorder (threads and an
    ffmpeg child process each), one landed in `_bundles`, and the other leaked
    forever while still writing to data_dir.
    """

    def test_inflight_registration_is_refused(self, manager, mock_pipeline_class):
        """While id X is mid-registration, a second call is refused cleanly."""
        manager._registering.add("cam1")
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        result = manager.register_source(source)
        assert result["status"] == "registration_in_progress"
        mock_pipeline_class[0].assert_not_called()

    def test_concurrent_register_builds_exactly_one_pipeline(
        self, manager, mock_pipeline_class
    ):
        """Two racing threads, one id: exactly one pipeline is constructed.

        The constructor is made to block so both threads are genuinely in-flight
        before either finishes — the claim set is what stops the loser from
        building a second pipeline that would then be lost.
        """
        import threading

        gate = threading.Event()
        mock_cls, instance = mock_pipeline_class

        def gated_constructor(**kwargs):
            gate.wait(timeout=5)
            return instance

        mock_cls.side_effect = gated_constructor

        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        results = []

        def do_register():
            results.append(manager.register_source(source))

        t1 = threading.Thread(target=do_register)
        t2 = threading.Thread(target=do_register)
        t1.start()
        # Give t1 the head start it needs to take the claim.
        threading.Event().wait(0.05)
        t2.start()
        threading.Event().wait(0.05)
        gate.set()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not t1.is_alive() and not t2.is_alive()
        statuses = sorted(r["status"] for r in results)
        assert statuses == ["registration_in_progress", "started"]
        assert mock_cls.call_count == 1

    def test_failed_registration_releases_the_claim(self, manager, mock_pipeline_class):
        """A build that raises must not wedge the id for later attempts."""
        mock_cls, instance = mock_pipeline_class
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        with patch.object(manager, "_build_sink", side_effect=OSError("boom")):
            with pytest.raises(OSError):
                manager.register_source(source)
        assert "cam1" not in manager._registering
        # And the next attempt proceeds normally.
        assert manager.register_source(source)["status"] == "started"

    def test_registration_in_progress_clears_dead_bundle_after_failure(
        self, manager, mock_pipeline_class
    ):
        """A rejected re-register must leave the existing source running.

        Regression lock for the input-validation ordering: validation happens
        before the old bundle is detached and torn down.
        """
        from shared.config import SegmentConfig

        mock_cls, instance = mock_pipeline_class
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)
        # A lone `min_duration` passes the schema (partial updates are not
        # compared against the default max); the inverted pair only emerges
        # AFTER merging with the defaults (max_duration=10), which is exactly
        # the effective check register_source runs before touching state.
        bad = SourceConfig(
            source_id="cam1",
            source_url="rtsp://localhost:8554/live/cam1",
            segment=SegmentConfig(min_duration=30.0),
        )
        with pytest.raises(ValueError, match="must not exceed"):
            manager.register_source(bad)
        # Original source is intact and still reported.
        status = manager.get_source_status("cam1")
        assert status is not None
        assert status["source_id"] == "cam1"

    def test_unregister_pop_is_atomic(self, manager, mock_pipeline_class):
        """Two concurrent unregisters: exactly one tears the bundle down."""
        import threading

        _, instance = mock_pipeline_class
        source = SourceConfig(
            source_id="cam1", source_url="rtsp://localhost:8554/live/cam1"
        )
        manager.register_source(source)

        results = []
        threads = [
            threading.Thread(
                target=lambda: results.append(manager.unregister_source("cam1"))
            )
            for _ in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        statuses = sorted(r["status"] for r in results)
        assert statuses == ["not_found", "stopped"]
        # stop() called exactly once — the loser found nothing to tear down.
        instance.stop.assert_called_once()


class TestSourceManagerRestart:
    def test_restart_drives_pipeline_and_recorder_under_lock(
        self, manager, mock_pipeline_class
    ):
        """Restart sequencing lives in the manager, not the endpoint."""
        mock_cls, instance = mock_pipeline_class
        source = SourceConfig(
            source_id="cam1",
            source_url="rtsp://localhost:8554/live/cam1",
            recording={"enabled": False},
        )
        manager.register_source(source)
        instance.stop.reset_mock()
        instance.start.reset_mock()

        result = manager.restart_source("cam1")
        assert result["status"] == "restarted"
        instance.stop.assert_called_once()
        instance.start.assert_called_once()

    def test_restart_not_found(self, manager):
        assert manager.restart_source("nope")["status"] == "not_found"
