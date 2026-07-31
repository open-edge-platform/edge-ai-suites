"""Tests for health monitoring: HealthConfig, backoff, recovery strategies."""

import threading
from unittest.mock import patch, MagicMock, call

import pytest

from shared.config import (
    AppConfig,
    SourceConfig,
    DefaultsConfig,
    HealthConfig,
    MotionConfig,
    SegmentConfig,
    PrefilterConfig,
)
from stream_monitor.rtsp_monitor import StreamPipeline
from sinks import NullSink


@pytest.fixture
def defaults():
    return DefaultsConfig()


@pytest.fixture
def null_sink():
    return NullSink()


def make_pipeline(health_cfg=None, on_remove_callback=None):
    """Create a StreamPipeline with mocked OpenCV and prefilter."""
    source = SourceConfig(
        source_id="test_cam",
        source_url="rtsp://localhost:8554/live/test",
        health=health_cfg,
        prefilter=PrefilterConfig(enabled=False),
    )
    defaults = DefaultsConfig()
    with patch("stream_monitor.rtsp_monitor.cv2"):
        pipeline = StreamPipeline(
            source=source,
            defaults=defaults,
            data_dir="/tmp/test-health",
            sink=NullSink(),
            on_remove_callback=on_remove_callback,
        )
    return pipeline


class TestHealthConfig:
    def test_defaults(self):
        cfg = HealthConfig()
        assert cfg.max_failures == 30
        assert cfg.recovery_strategy == "retry"
        assert cfg.backoff_base == 2.0
        assert cfg.backoff_max == 120.0

    def test_custom_values(self):
        cfg = HealthConfig(
            max_failures=10,
            recovery_strategy="pause",
            backoff_base=1.0,
            backoff_max=60.0,
        )
        assert cfg.max_failures == 10
        assert cfg.recovery_strategy == "pause"
        assert cfg.backoff_base == 1.0
        assert cfg.backoff_max == 60.0

    def test_source_config_with_health(self):
        src = SourceConfig(
            source_id="cam1",
            source_url="rtsp://localhost:8554/live/test",
            health=HealthConfig(max_failures=5, recovery_strategy="remove"),
        )
        assert src.health is not None
        assert src.health.max_failures == 5
        assert src.health.recovery_strategy == "remove"

    def test_defaults_config_includes_health(self):
        d = DefaultsConfig()
        assert d.health is not None
        assert d.health.max_failures == 30

    def test_app_config_loads_health_from_yaml(self):
        cfg = AppConfig(
            defaults=DefaultsConfig(
                health=HealthConfig(max_failures=50, recovery_strategy="pause")
            )
        )
        assert cfg.defaults.health.max_failures == 50
        assert cfg.defaults.health.recovery_strategy == "pause"


class TestBackoffCalculation:
    def test_first_attempt_uses_base(self):
        pipeline = make_pipeline()
        pipeline._reconnect_count = 0
        delay = pipeline._calculate_backoff()
        assert delay == 2.0  # backoff_base * 2^0 = 2.0

    def test_exponential_growth(self):
        pipeline = make_pipeline()
        delays = []
        for i in range(5):
            pipeline._reconnect_count = i
            delays.append(pipeline._calculate_backoff())
        assert delays == [2.0, 4.0, 8.0, 16.0, 32.0]

    def test_capped_at_backoff_max(self):
        pipeline = make_pipeline(HealthConfig(backoff_base=2.0, backoff_max=30.0))
        pipeline._reconnect_count = 10
        delay = pipeline._calculate_backoff()
        assert delay == 30.0

    def test_custom_backoff_base(self):
        pipeline = make_pipeline(HealthConfig(backoff_base=5.0, backoff_max=120.0))
        pipeline._reconnect_count = 0
        assert pipeline._calculate_backoff() == 5.0
        pipeline._reconnect_count = 1
        assert pipeline._calculate_backoff() == 10.0
        pipeline._reconnect_count = 2
        assert pipeline._calculate_backoff() == 20.0


class TestHealthInfo:
    def test_initial_health_info(self):
        pipeline = make_pipeline()
        info = pipeline.health_info
        assert info["failure_count"] == 0
        assert info["last_failure_time"] is None
        assert info["reconnect_count"] == 0
        assert info["recovery_strategy"] == "retry"
        assert info["max_failures"] == 30
        assert info["start_time"] is None

    def test_health_info_reflects_state(self):
        pipeline = make_pipeline()
        pipeline._failure_count = 5
        pipeline._last_failure_time = "2026-06-12T10:00:00"
        pipeline._reconnect_count = 3
        pipeline._start_time = "2026-06-12T09:00:00"
        info = pipeline.health_info
        assert info["failure_count"] == 5
        assert info["last_failure_time"] == "2026-06-12T10:00:00"
        assert info["reconnect_count"] == 3
        assert info["start_time"] == "2026-06-12T09:00:00"

    def test_health_info_uses_source_health_config(self):
        pipeline = make_pipeline(HealthConfig(
            max_failures=10,
            recovery_strategy="remove",
        ))
        info = pipeline.health_info
        assert info["max_failures"] == 10
        assert info["recovery_strategy"] == "remove"


class TestHandleUnhealthy:
    def test_retry_strategy_emits_unhealthy_and_sleeps(self):
        pipeline = make_pipeline(HealthConfig(
            recovery_strategy="retry",
            backoff_max=5.0,
        ))
        pipeline._failure_count = 30
        pipeline._running = True

        with patch("stream_monitor.rtsp_monitor.time.sleep") as mock_sleep:
            pipeline._handle_unhealthy()

        assert pipeline._status == "unhealthy"
        mock_sleep.assert_called_once_with(5.0)

    def test_remove_strategy_stops_and_calls_callback(self):
        callback = MagicMock()
        pipeline = make_pipeline(
            HealthConfig(recovery_strategy="remove"),
            on_remove_callback=callback,
        )
        pipeline._failure_count = 30
        pipeline._running = True

        pipeline._handle_unhealthy()

        assert pipeline._running is False
        assert pipeline._status == "removed"
        callback.assert_called_once_with("test_cam")

    def test_remove_strategy_no_callback(self):
        pipeline = make_pipeline(HealthConfig(recovery_strategy="remove"))
        pipeline._failure_count = 30
        pipeline._running = True

        pipeline._handle_unhealthy()

        assert pipeline._running is False
        assert pipeline._status == "removed"

    def test_pause_strategy_pauses_and_waits(self):
        pipeline = make_pipeline(HealthConfig(recovery_strategy="pause"))
        pipeline._failure_count = 30
        pipeline._running = True

        def resume_after_pause():
            import time
            time.sleep(0.1)
            pipeline._paused.set()

        threading.Thread(target=resume_after_pause, daemon=True).start()
        pipeline._handle_unhealthy()

        assert pipeline._failure_count == 0
        assert pipeline._reconnect_count == 0

    def test_unhealthy_sets_status_without_webhook(self):
        sink = MagicMock()
        source = SourceConfig(
            source_id="cam_health",
            source_url="rtsp://localhost:8554/live/test",
            health=HealthConfig(recovery_strategy="retry", backoff_max=0.01),
            prefilter=PrefilterConfig(enabled=False),
        )
        with patch("stream_monitor.rtsp_monitor.cv2"):
            pipeline = StreamPipeline(
                source=source,
                defaults=DefaultsConfig(),
                data_dir="/tmp/test-health",
                sink=sink,
            )
        pipeline._failure_count = 30
        pipeline._running = True

        with patch("stream_monitor.rtsp_monitor.time.sleep"):
            pipeline._handle_unhealthy()

        # §32: unhealthy (RTSP health) is no longer pushed to the /events webhook.
        # Internal status is set instead — MCP reads it via GET /sources/{id}/status.
        sink.emit.assert_not_called()
        assert pipeline._status == "unhealthy"


class TestRunReconnectionLogic:
    def test_successful_connection_resets_counters(self):
        pipeline = make_pipeline()
        pipeline._failure_count = 10
        pipeline._reconnect_count = 5
        pipeline._running = True

        call_count = [0]

        def fake_connect():
            pipeline._cap = MagicMock()
            pipeline._cap.isOpened.return_value = True

        def fake_process_loop():
            call_count[0] += 1
            pipeline._running = False

        with patch.object(pipeline, "_connect", side_effect=fake_connect), \
             patch.object(pipeline, "_process_loop", side_effect=fake_process_loop), \
             patch.object(pipeline, "_emit_status"):
            pipeline._run()

        assert pipeline._failure_count == 0
        assert pipeline._reconnect_count == 0

    def test_connection_failure_increments_counters(self):
        pipeline = make_pipeline(HealthConfig(max_failures=100, backoff_max=0.01))
        pipeline._running = True

        attempt = [0]

        def fake_connect():
            attempt[0] += 1
            if attempt[0] >= 3:
                pipeline._running = False
            raise ConnectionError("fail")

        with patch.object(pipeline, "_connect", side_effect=fake_connect), \
             patch.object(pipeline, "_emit_status"), \
             patch("stream_monitor.rtsp_monitor.time.sleep"):
            pipeline._run()

        assert pipeline._failure_count == 3
        assert pipeline._reconnect_count >= 2
