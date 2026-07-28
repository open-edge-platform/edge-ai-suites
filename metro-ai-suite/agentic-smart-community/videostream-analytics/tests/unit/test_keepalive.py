"""Phase 8 — keepalive protocol & watchdog auto-pause.

Tests cover three layers:
1. SourceBundle / SourceManager state plumbing (init, refresh, describe).
2. Watchdog auto-pause logic (stale → pause; fresh / paused / disabled → skip).
3. HTTP endpoint plumbing (200 + payload on hit, 404 on miss).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import service as service_module
from service import create_app
from shared.config import (
    AppConfig,
    DefaultsConfig,
    KeepaliveConfig,
    SourceConfig,
)
from source_worker import SourceManager


# ---------------------------------------------------------------------------
# SourceManager state tests
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_pipeline_class():
    """Patch StreamPipeline / ContinuousRecorder to dummy mocks so register
    doesn't try to open an RTSP stream."""
    with patch("source_worker.StreamPipeline") as mock_pipe_cls, \
         patch("source_worker.ContinuousRecorder") as mock_rec_cls:
        pipe = MagicMock()
        pipe.is_running = True
        pipe.status = "online"
        pipe.health_info = {}
        pipe.source = SourceConfig(
            source_id="cam_test", source_url="rtsp://x"
        )
        mock_pipe_cls.return_value = pipe
        rec = MagicMock()
        mock_rec_cls.return_value = rec
        yield mock_pipe_cls, pipe, mock_rec_cls, rec


@pytest.fixture
def manager(mock_pipeline_class):
    """Build a SourceManager with the watchdog thread inert.

    We stop the daemon immediately so tests can drive `_watchdog_check_once`
    deterministically without races.
    """
    config = AppConfig()
    with patch("source_worker.WebhookSink"):
        mgr = SourceManager(config)
    mgr._watchdog_running = False
    yield mgr
    # Clean shutdown; daemon flag already False so loop will exit on next tick.
    mgr._bundles.clear()


def _register(mgr, source_id: str, keepalive_enabled: bool = False, **ka_kwargs):
    """Helper: register source with an optional KeepaliveConfig."""
    ka = (
        KeepaliveConfig(enabled=keepalive_enabled, **ka_kwargs)
        if keepalive_enabled or ka_kwargs
        else None
    )
    src = SourceConfig(
        source_id=source_id,
        source_url=f"rtsp://x/{source_id}",
        keepalive=ka,
    )
    return mgr.register_source(src)


class TestKeepaliveManager:
    def test_keepalive_updates_timestamp(self, manager):
        _register(manager, "cam_a", keepalive_enabled=True)
        before = manager._bundles["cam_a"].last_keepalive_at
        assert before is not None
        with patch("source_worker.time.time", return_value=before + 5):
            result = manager.keepalive_source("cam_a")
        assert result["status"] == "ok"
        assert result["source_id"] == "cam_a"
        assert "last_keepalive_at" in result
        assert manager._bundles["cam_a"].last_keepalive_at == before + 5

    def test_keepalive_not_found(self, manager):
        result = manager.keepalive_source("never_registered")
        assert result["status"] == "not_found"
        assert result["source_id"] == "never_registered"

    def test_keepalive_disabled_no_init(self, manager):
        _register(manager, "cam_off", keepalive_enabled=False)
        assert manager._bundles["cam_off"].last_keepalive_at is None

    def test_keepalive_enabled_inits_timestamp(self, manager):
        _register(manager, "cam_on", keepalive_enabled=True)
        assert manager._bundles["cam_on"].last_keepalive_at is not None

    def test_partial_keepalive_inherits_default_timeout(self, mock_pipeline_class):
        defaults = DefaultsConfig(
            keepalive=KeepaliveConfig(
                enabled=True,
                timeout_seconds=15.0,
                check_interval_seconds=3.0,
            )
        )
        with patch("source_worker.WebhookSink"):
            manager = SourceManager(AppConfig(defaults=defaults))
        manager._watchdog_running = False
        try:
            src = SourceConfig(
                source_id="cam_partial",
                source_url="rtsp://x/cam_partial",
                keepalive=KeepaliveConfig(enabled=True),
            )
            manager.register_source(src)
            cfg = manager._bundles["cam_partial"].keepalive
            assert cfg is not None
            assert cfg.enabled is True
            assert cfg.timeout_seconds == 15.0
            assert cfg.check_interval_seconds == 3.0
        finally:
            manager._bundles.clear()

    def test_describe_bundle_exposes_keepalive(self, manager):
        _register(manager, "cam_describe", keepalive_enabled=True)
        status = manager.get_source_status("cam_describe")
        assert status is not None
        assert status["keepalive_enabled"] is True
        assert status["last_keepalive_at"] is not None

    def test_describe_bundle_keepalive_disabled(self, manager):
        _register(manager, "cam_no_ka", keepalive_enabled=False)
        status = manager.get_source_status("cam_no_ka")
        assert status["keepalive_enabled"] is False
        assert status["last_keepalive_at"] is None


class TestWatchdog:
    def test_watchdog_pauses_stale_source(self, manager, mock_pipeline_class):
        _, pipe, _, _ = mock_pipeline_class
        _register(
            manager,
            "cam_stale",
            keepalive_enabled=True,
            timeout_seconds=5.0,
        )
        # Roll keepalive timestamp 100s into the past.
        manager._bundles["cam_stale"].last_keepalive_at -= 100
        # Spy on pause_source.
        with patch.object(manager, "pause_source", wraps=manager.pause_source) as spy:
            manager._watchdog_check_once()
        assert spy.call_count == 1
        spy.assert_called_with("cam_stale")

    def test_watchdog_skips_fresh_source(self, manager, mock_pipeline_class):
        _register(
            manager,
            "cam_fresh",
            keepalive_enabled=True,
            timeout_seconds=90.0,
        )
        # last_keepalive_at = now; only 5s back.
        manager._bundles["cam_fresh"].last_keepalive_at -= 5
        with patch.object(manager, "pause_source", wraps=manager.pause_source) as spy:
            manager._watchdog_check_once()
        assert spy.call_count == 0

    def test_watchdog_skips_already_paused(self, manager, mock_pipeline_class):
        _, pipe, _, _ = mock_pipeline_class
        _register(
            manager,
            "cam_paused",
            keepalive_enabled=True,
            timeout_seconds=5.0,
        )
        manager._bundles["cam_paused"].last_keepalive_at -= 100
        # Mark pipeline already paused.
        pipe.status = "paused"
        with patch.object(manager, "pause_source", wraps=manager.pause_source) as spy:
            manager._watchdog_check_once()
        assert spy.call_count == 0

    def test_watchdog_skips_disabled_source(self, manager, mock_pipeline_class):
        _register(manager, "cam_off", keepalive_enabled=False)
        # Even with a stale timestamp, disabled means hands-off.
        manager._bundles["cam_off"].last_keepalive_at = 0.0
        with patch.object(manager, "pause_source", wraps=manager.pause_source) as spy:
            manager._watchdog_check_once()
        assert spy.call_count == 0

    def test_watchdog_skips_source_without_first_keepalive(
        self, manager, mock_pipeline_class
    ):
        """If `last_keepalive_at is None` (grace period not started), don't pause."""
        _register(manager, "cam_off", keepalive_enabled=False)
        # Force enabled=True with last_keepalive_at None (simulate edge case).
        manager._bundles["cam_off"].keepalive = KeepaliveConfig(
            enabled=True, timeout_seconds=5.0
        )
        manager._bundles["cam_off"].last_keepalive_at = None
        with patch.object(manager, "pause_source", wraps=manager.pause_source) as spy:
            manager._watchdog_check_once()
        assert spy.call_count == 0


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def app_client(monkeypatch):
    """TestClient with a mocked SourceManager (same pattern as test_app_endpoints)."""
    mgr = MagicMock(spec=SourceManager)
    app = create_app(AppConfig())
    with TestClient(app, raise_server_exceptions=False) as tc:
        monkeypatch.setattr(service_module, "_manager", mgr)
        yield tc, mgr


class TestKeepaliveEndpoint:
    def test_endpoint_returns_200_and_payload(self, app_client):
        tc, mgr = app_client
        mgr.keepalive_source.return_value = {
            "status": "ok",
            "source_id": "cam_a",
            "last_keepalive_at": "2026-06-29T10:30:15+00:00",
        }
        resp = tc.post("/sources/cam_a/keepalive")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["source_id"] == "cam_a"
        assert "last_keepalive_at" in body
        mgr.keepalive_source.assert_called_once_with("cam_a")

    def test_endpoint_accepts_empty_body(self, app_client):
        tc, mgr = app_client
        mgr.keepalive_source.return_value = {
            "status": "ok",
            "source_id": "cam_a",
            "last_keepalive_at": "2026-06-29T10:30:15+00:00",
        }
        resp = tc.post("/sources/cam_a/keepalive", json={})
        assert resp.status_code == 200

    def test_endpoint_404_on_missing(self, app_client):
        tc, mgr = app_client
        mgr.keepalive_source.return_value = {
            "status": "not_found",
            "source_id": "never_registered",
        }
        resp = tc.post("/sources/never_registered/keepalive")
        assert resp.status_code == 404
