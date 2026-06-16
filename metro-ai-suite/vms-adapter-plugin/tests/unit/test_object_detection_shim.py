# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for ObjectDetectionAnalyticsAppShim."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from analytics_app_shim.object_detection import api_client as od_api_client_module
from analytics_app_shim.object_detection.api_client import ObjectDetectionApiClient
from analytics_app_shim.object_detection.shim import ObjectDetectionAnalyticsAppShim
from analytics_app_shim.object_detection.config import ObjectDetectionAnalyticsAppConfig


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_config(**kwargs) -> ObjectDetectionAnalyticsAppConfig:
    defaults = {
        "type": "object_detection",
        "app_id": "dls_vision",
        "display_name": "DLStreamer Vision",
        "base_url": "https://localhost:443/api",
        "mqtt_host": "localhost",
        "mqtt_port": 1883,
        "pipeline_server_mqtt_host": "mqtt-broker",
        "pipeline_server_mqtt_port": 1883,
    }
    defaults.update(kwargs)
    return ObjectDetectionAnalyticsAppConfig(**defaults)


def _make_shim(**kwargs) -> ObjectDetectionAnalyticsAppShim:
    return ObjectDetectionAnalyticsAppShim(_make_config(**kwargs))


# ── Basic identity ─────────────────────────────────────────────────────────────

def test_shim_app_id():
    shim = _make_shim()
    assert shim.app_id == "dls_vision"


def test_shim_display_name():
    shim = _make_shim(display_name="My DLStreamer Vision App")
    assert shim.display_name == "My DLStreamer Vision App"


def test_shim_implements_interface():
    from plugin.base.interfaces import IAnalyticsAppShim
    shim = _make_shim()
    assert isinstance(shim, IAnalyticsAppShim)


def test_camera_fields_returns_camera_id():
    shim = _make_shim()
    assert shim.camera_fields() == ["camera_id"]


# ── fetch_schema ──────────────────────────────────────────────────────────────

async def test_fetch_schema_returns_object_schema():
    shim = _make_shim()
    shim._api.list_pipelines = AsyncMock(return_value=[
        {"name": "user_defined_pipelines", "version": "dls_vision_pipeline"},
    ])

    schema = await shim.fetch_schema()

    assert schema["type"] == "object"
    assert "pipeline_name" in schema["properties"]
    assert "camera_id" in schema["properties"]
    assert set(schema["required"]) == {"pipeline_name", "camera_id"}


async def test_fetch_schema_populates_pipeline_enum():
    """Pipeline enum uses the 'version' field, not 'name' (which is the root)."""
    shim = _make_shim()
    shim._api.list_pipelines = AsyncMock(return_value=[
        {"name": "user_defined_pipelines", "version": "dls_vision_pipeline"},
        {"name": "user_defined_pipelines", "version": "dls_vision_pipeline_gpu"},
    ])
    schema = await shim.fetch_schema()
    enum = schema["properties"]["pipeline_name"]["enum"]
    assert "dls_vision_pipeline" in enum
    assert "dls_vision_pipeline_gpu" in enum
    # Root name must NOT appear in the enum
    assert "user_defined_pipelines" not in enum


async def test_fetch_schema_builds_pipeline_root_map():
    """_pipeline_root_map maps version → root for correct POST URL."""
    shim = _make_shim()
    shim._api.list_pipelines = AsyncMock(return_value=[
        {"name": "user_defined_pipelines", "version": "dls_vision_pipeline"},
    ])
    await shim.fetch_schema()
    assert shim._pipeline_root_map == {"dls_vision_pipeline": "user_defined_pipelines"}


async def test_fetch_schema_handles_empty_pipeline_list():
    shim = _make_shim()
    shim._api.list_pipelines = AsyncMock(return_value=[])
    schema = await shim.fetch_schema()
    assert schema["properties"]["pipeline_name"]["enum"] == []


# ── is_reachable ──────────────────────────────────────────────────────────────

async def test_is_reachable_delegates_to_api_client():
    shim = _make_shim()
    shim._api.is_reachable = AsyncMock(return_value=True)
    assert await shim.is_reachable() is True

    shim._api.is_reachable = AsyncMock(return_value=False)
    assert await shim.is_reachable() is False


# ── start ─────────────────────────────────────────────────────────────────────

async def test_start_creates_run():
    """start() posts to /{pipeline_root}/{pipeline_version} and returns run_id=instance_id."""
    shim = _make_shim()
    shim._pipeline_root_map = {"dls_vision_pipeline": "user_defined_pipelines"}
    shim._api.start_run = AsyncMock(
        return_value={"instance_id": "4b36b3ce52ad11f0ad60863f511204e2"}
    )

    params = MagicMock()
    params.model_dump.return_value = {
        "pipeline_name": "dls_vision_pipeline",
        "camera_id": "rtsp://cam:554/stream",
        "camera_id_ref": "nx:e3e9a385-7fe0-3ba5-5482-a86cde7faf48",
        "parameters": {},
    }

    result = await shim.start(params)

    shim._api.start_run.assert_called_once_with(
        "user_defined_pipelines",
        "dls_vision_pipeline",
        {
            "source": {"uri": "rtsp://cam:554/stream", "type": "uri", "properties": {"protocols": "tcp", "add-reference-timestamp-meta": True, "latency": 100}},
            "destination": {"metadata": {"type": "mqtt", "host": "mqtt-broker:1883", "topic": "nx/dls_vision/e3e9a385-7fe0-3ba5-5482-a86cde7faf48"}},
            "parameters": {},
        },
    )
    assert result["run_id"] == "4b36b3ce52ad11f0ad60863f511204e2"
    assert result["pipeline_name"] == "dls_vision_pipeline"


async def test_start_uses_default_root_when_not_in_map():
    """If pipeline_root_map is empty, defaults to 'user_defined_pipelines'."""
    shim = _make_shim()
    shim._api.start_run = AsyncMock(return_value={"instance_id": "abc123"})

    params = MagicMock()
    params.model_dump.return_value = {
        "pipeline_name": "some_pipeline",
        "camera_id": "rtsp://cam/s",
        "camera_id_ref": "",
        "parameters": {},
    }
    await shim.start(params)
    shim._api.start_run.assert_called_once_with(
        "user_defined_pipelines",
        "some_pipeline",
        {
            "source": {"uri": "rtsp://cam/s", "type": "uri", "properties": {"protocols": "tcp", "add-reference-timestamp-meta": True, "latency": 100}},
            "destination": {"metadata": {"type": "mqtt", "host": "mqtt-broker:1883", "topic": "vap/dls_vision/unknown"}},
            "parameters": {},
        },
    )


async def test_start_raises_on_missing_pipeline_name():
    shim = _make_shim()
    params = MagicMock()
    params.model_dump.return_value = {
        "pipeline_name": "",
        "camera_id": "rtsp://cam/stream",
        "parameters": {},
    }
    with pytest.raises(ValueError, match="pipeline_name"):
        await shim.start(params)


async def test_start_raises_on_api_failure():
    shim = _make_shim()
    shim._api.start_run = AsyncMock(return_value=None)

    params = MagicMock()
    params.model_dump.return_value = {
        "pipeline_name": "dls_vision_pipeline",
        "camera_id": "rtsp://x/y",
        "parameters": {},
    }
    with pytest.raises(RuntimeError):
        await shim.start(params)


# ── stop_run ──────────────────────────────────────────────────────────────────

async def test_stop_run_calls_api_with_instance_id():
    """stop_run() passes run_id (hex UUID) directly to the API — no name/version lookup."""
    shim = _make_shim()
    run_id = "4b36b3ce52ad11f0ad60863f511204e2"
    shim._api.stop_run = AsyncMock(return_value=True)

    ok = await shim.stop_run(run_id)

    shim._api.stop_run.assert_called_once_with(run_id)
    assert ok is True


async def test_stop_run_clears_cache_on_success():
    """Successful stop removes the entry from _runs cache."""
    shim = _make_shim()
    run_id = "abc123"
    shim._runs[run_id] = {"run_id": run_id, "pipeline_name": "pd"}
    shim._api.stop_run = AsyncMock(return_value=True)

    await shim.stop_run(run_id)

    assert run_id not in shim._runs


async def test_stop_run_not_in_cache_still_calls_api():
    """stop_run() does NOT require the cache — it calls the API directly."""
    shim = _make_shim()
    shim._api.stop_run = AsyncMock(return_value=False)
    ok = await shim.stop_run("unknown-id")
    shim._api.stop_run.assert_called_once_with("unknown-id")
    assert ok is False


# ── deliver (no-op) ──────────────────────────────────────────────────────────

async def test_deliver_returns_none():
    shim = _make_shim()
    from plugin.core.models.domain import MetadataEvent
    event = MagicMock(spec=MetadataEvent)
    event.event_id = "test-evt"
    result = await shim.deliver(event, "/tmp/clip.mp4")
    assert result is None


def test_shim_passes_tls_settings_to_api_client():
    shim = _make_shim(tls_verify=True, tls_ca_bundle="/tmp/od-ca.pem")
    assert shim._api._tls_verify is True
    assert shim._api._tls_ca_bundle == "/tmp/od-ca.pem"


def test_api_client_default_verify_is_false(monkeypatch):
    captured: dict = {}

    def _fake_async_client(*args, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(od_api_client_module.httpx, "AsyncClient", _fake_async_client)
    client = ObjectDetectionApiClient(base_url="https://localhost:443/api")
    client._ensure_client()

    assert captured["verify"] is False


def test_api_client_verify_uses_ca_bundle_path(monkeypatch):
    captured: dict = {}

    def _fake_async_client(*args, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(od_api_client_module.httpx, "AsyncClient", _fake_async_client)
    client = ObjectDetectionApiClient(
        base_url="https://localhost:443/api",
        tls_verify=True,
        tls_ca_bundle="/tmp/od-ca.pem",
    )
    client._ensure_client()

    assert captured["verify"] == "/tmp/od-ca.pem"
