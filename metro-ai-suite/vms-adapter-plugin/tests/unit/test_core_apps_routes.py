# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Analytics App registry + dynamic discovery routes (LVC only)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from plugin.core.api.deps import set_shims
from plugin.core.api.routes import analytics_apps as analytics_apps_routes
from plugin.core.config import AppConfig
from plugin.core.factory import ShimFactory
from analytics_app_shim.lvc import LiveCaptioningAnalyticsAppShim
from analytics_app_shim.lvc.config import LiveCaptioningAnalyticsAppConfig


@pytest.fixture
def app_config():
    return AppConfig.model_validate({
        "analytics_apps": [
            {
                "type": "live_captioning",
                "base_url": "http://lvc:4173",
                "mediamtx_url": "http://mtx:8889",
            },
        ],
    })


@pytest.fixture
def fastapi_client(app_config, monkeypatch):
    registry = ShimFactory.create_analytics_app_shims(app_config)

    async def _available_true(self):  # noqa: ANN001
        return True
    monkeypatch.setattr(LiveCaptioningAnalyticsAppShim, "is_available", _available_true)

    captured: dict = {}

    async def _start(self, params):  # noqa: ANN001
        captured["app_id"] = self.app_id
        captured["params"] = params.model_dump()
        return {"runId": "run-xyz", "params_seen": params.model_dump()}
    monkeypatch.setattr(LiveCaptioningAnalyticsAppShim, "start", _start)

    set_shims([], registry, app_config)

    app = FastAPI()
    app.include_router(analytics_apps_routes.router, prefix="/v1")
    return TestClient(app), captured


def test_registry_contains_lvc(app_config):
    registry = ShimFactory.create_analytics_app_shims(app_config)
    assert set(registry) == {"live_captioning"}
    assert isinstance(registry["live_captioning"], LiveCaptioningAnalyticsAppShim)


def test_legacy_analytics_app_singular_converts_to_list():
    cfg = AppConfig.model_validate({
        "analytics_app": {
            "type": "live_captioning",
            "base_url": "http://lvc:4173",
        },
    })
    assert len(cfg.analytics_apps) == 1
    assert cfg.analytics_apps[0].type == "live_captioning"
    assert cfg.analytics_app is cfg.analytics_apps[0]


def test_discover_returns_schemas_and_availability(fastapi_client):
    client, _ = fastapi_client
    resp = client.get("/v1/analytics-apps/discover")
    assert resp.status_code == 200
    body = resp.json()
    apps = {a["app_id"]: a for a in body}
    assert set(apps) == {"live_captioning"}
    entry = apps["live_captioning"]
    assert entry["available"] is True
    assert "type" not in entry and "base_url" not in entry
    schema = entry["params_schema"]
    assert schema["type"] == "object"
    assert "cameraId" in schema["properties"]
    assert "cameraId" in schema.get("required", [])


def test_schema_endpoint(fastapi_client):
    client, _ = fastapi_client
    resp = client.get("/v1/analytics-apps/live_captioning/schema")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["properties"]["cameraId"]["x-vms-source"] == "camera"


def test_schema_unknown_app_returns_404(fastapi_client):
    client, _ = fastapi_client
    resp = client.get("/v1/analytics-apps/nope/schema")
    assert resp.status_code == 404


def test_start_validates_payload(fastapi_client):
    client, _ = fastapi_client
    resp = client.post("/v1/analytics-apps/live_captioning/start", json={})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert any(err["loc"][-1] == "cameraId" for err in detail)


def test_start_dispatches_to_shim(fastapi_client):
    client, captured = fastapi_client
    resp = client.post(
        "/v1/analytics-apps/live_captioning/start",
        json={"cameraId": "frigate:cam-1", "maxTokens": 50, "prompt": "hi"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["runId"] == "run-xyz"
    assert captured["app_id"] == "live_captioning"
    assert captured["params"]["cameraId"] == "frigate:cam-1"
    assert captured["params"]["maxTokens"] == 50


def test_start_unknown_app_returns_404(fastapi_client):
    client, _ = fastapi_client
    resp = client.post("/v1/analytics-apps/nope/start", json={"cameraId": "x"})
    assert resp.status_code == 404


def test_lvc_shim_metadata():
    assert LiveCaptioningAnalyticsAppShim.app_id == "live_captioning"
    schema = LiveCaptioningAnalyticsAppShim.param_model.model_json_schema()
    assert schema["type"] == "object"
    assert "cameraId" in schema["properties"]
