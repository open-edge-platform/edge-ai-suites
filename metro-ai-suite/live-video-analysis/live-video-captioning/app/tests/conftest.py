# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Shared fixtures for live-video-captioning tests.

Provides:
  - FastAPI TestClient via the `client` fixture
  - Temporary model directories via `models_dir` / `detection_models_dir`
  - Automatic cleanup of the global RUNS state between tests
  - Monkeypatched MQTT subscriber so tests never hit a real broker
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Patch config values BEFORE any application module is imported so that every
# module that reads backend.config at import time will see the test defaults.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _patch_config(monkeypatch, tmp_path):
    """Override config values with safe test defaults for every test."""
    monkeypatch.setenv("DASHBOARD_PORT", "4173")
    monkeypatch.setenv("WEBRTC_PEER_ID", "test-peer")
    monkeypatch.setenv("SIGNALING_URL", "http://test-signaling:8889")
    monkeypatch.setenv("WEBRTC_BITRATE", "2048")
    monkeypatch.setenv("ALERT_MODE", "false")
    monkeypatch.setenv("DEFAULT_RTSP_URL", "")
    monkeypatch.setenv("ENABLE_DETECTION_PIPELINE", "false")
    monkeypatch.setenv("METRICS_SERVICE_PORT", "9090")
    monkeypatch.setenv("MQTT_BROKER_HOST", "localhost")
    monkeypatch.setenv("MQTT_BROKER_PORT", "1883")
    monkeypatch.setenv("MQTT_TOPIC_PREFIX", "test-prefix")
    monkeypatch.setenv("PIPELINE_SERVER_URL", "http://mock-pipeline:8080")
    monkeypatch.setenv("PIPELINE_NAME", "genai_pipeline")
    monkeypatch.setenv("MODELS_DIR", str(tmp_path / "ov_models"))
    monkeypatch.setenv("DETECTION_MODELS_DIR", str(tmp_path / "ov_detection_models"))


# ---------------------------------------------------------------------------
# MQTT subscriber stub, prevents real connections during testing
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_mqtt(monkeypatch):
    """Replace the global MQTT helpers with no-op async stubs."""
    subscriber = MagicMock()
    subscriber.connect = AsyncMock()
    subscriber.disconnect = AsyncMock()
    subscriber.subscribe_to_run = MagicMock()
    subscriber.unsubscribe_from_run = MagicMock()
    subscriber.is_connected = True

    async def _get():
        return subscriber

    monkeypatch.setattr("backend.services.mqtt_subscriber.get_mqtt_subscriber", _get)
    monkeypatch.setattr(
        "backend.services.mqtt_subscriber.shutdown_mqtt_subscriber", AsyncMock()
    )
    return subscriber


# ---------------------------------------------------------------------------
# FastAPI TestClient
# ---------------------------------------------------------------------------
@pytest.fixture()
def client(mock_mqtt, monkeypatch, tmp_path):
    """Return a TestClient wired to the FastAPI application.

    The MQTT lifespan hooks are patched so we never touch a real broker.
    A temporary UI directory is created so static-file mounting does not fail.
    """
    # Create a minimal UI directory with index.html
    ui_dir = tmp_path / "ui"
    ui_dir.mkdir()
    (ui_dir / "index.html").write_text("<html><body>test</body></html>")

    monkeypatch.setattr("backend.config.UI_DIR", ui_dir)

    # Patch lifespan MQTT calls
    async def _noop_get():
        return mock_mqtt

    monkeypatch.setattr("main.get_mqtt_subscriber", _noop_get)
    monkeypatch.setattr("main.shutdown_mqtt_subscriber", AsyncMock())

    # Also patch in the runs module
    monkeypatch.setattr("backend.routes.runs.get_mqtt_subscriber", _noop_get)

    # Import app after all patches are in place
    from main import app

    with TestClient(app) as tc:
        yield tc


# ---------------------------------------------------------------------------
# Temporary model directories
# ---------------------------------------------------------------------------
@pytest.fixture()
def models_dir(tmp_path):
    """Return an empty temporary directory for VLM models."""
    d = tmp_path / "ov_models"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture()
def detection_models_dir(tmp_path):
    """Return an empty temporary directory for detection models."""
    d = tmp_path / "ov_detection_models"
    d.mkdir(exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Cleanup global run state between tests
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _clear_runs():
    """Ensure the RUNS dict is empty before and after each test."""
    from backend.state import RUNS

    RUNS.clear()
    yield
    RUNS.clear()
