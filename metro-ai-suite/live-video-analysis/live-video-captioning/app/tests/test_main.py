# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for main, FastAPI application setup and root endpoint."""

import runpy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRootEndpoint:
    """GET / serves the frontend index.html."""

    def test_root_returns_200(self, client):
        """The root endpoint returns HTTP 200."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_returns_html(self, client):
        """The root endpoint serves HTML content."""
        resp = client.get("/")
        assert "html" in resp.headers.get("content-type", "").lower()


class TestAppRouterInclusion:
    """Verify that all expected routers are mounted."""

    def test_health_route_registered(self, client):
        """The /api/health route is accessible."""
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_vlm_models_route_registered(self, client):
        """The /api/vlm-models route is accessible."""
        resp = client.get("/api/vlm-models")
        # May return empty list but should not 404
        assert resp.status_code == 200

    def test_detection_models_route_registered(self, client):
        """The /api/detection-models route is accessible."""
        resp = client.get("/api/detection-models")
        assert resp.status_code == 200

    def test_runs_route_registered(self, client):
        """The /api/generate_captions_alerts route is accessible."""
        resp = client.get("/api/generate_captions_alerts")
        assert resp.status_code == 200

    def test_runtime_config_route_registered(self, client):
        """The /runtime-config.js route is accessible."""
        resp = client.get("/runtime-config.js")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_lifespan_logs_warning_when_mqtt_init_fails():
    """Startup continues and logs a warning when MQTT init raises an exception."""
    from main import app, lifespan

    with patch(
        "main.get_mqtt_subscriber", AsyncMock(side_effect=RuntimeError("boom"))
    ), patch("main.start_pipeline_health_monitor", MagicMock()) as mock_start, patch(
        "main.stop_pipeline_health_monitor", AsyncMock()
    ) as mock_stop, patch(
        "main.shutdown_mqtt_subscriber", AsyncMock()
    ) as mock_shutdown, patch(
        "main.logger.warning"
    ) as mock_warning:
        async with lifespan(app):
            pass

    mock_warning.assert_called_once()
    assert "Failed to initialize MQTT subscriber" in mock_warning.call_args[0][0]
    mock_start.assert_called_once()
    mock_stop.assert_awaited_once()
    mock_shutdown.assert_awaited_once()


def test_main_entrypoint_runs_uvicorn():
    """Executing module as __main__ invokes uvicorn.run with expected defaults."""
    with patch("uvicorn.run") as mock_uvicorn_run:
        runpy.run_module("main", run_name="__main__")

    mock_uvicorn_run.assert_called_once()
    args, kwargs = mock_uvicorn_run.call_args
    assert args[0] == "main:app"
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["reload"] is True
