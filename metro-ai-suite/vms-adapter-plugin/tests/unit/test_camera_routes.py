# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for camera routes with masked browser-facing RTSP URLs."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from plugin.core.api.deps import get_db_session, get_vms_shim_sets
from plugin.core.api.routes import cameras as cameras_routes
from plugin.core.main import create_app
from plugin.core.models.domain import Camera, MASKED_PASSWORD_PLACEHOLDER


@pytest.fixture
def client():
    app = create_app()

    async def override_db():
        yield object()

    app.dependency_overrides[get_db_session] = override_db
    return TestClient(app, raise_server_exceptions=False)


def _camera():
    return Camera(
        camera_id="nx:cam-1",
        name="Front Door",
        vendor="nx_witness",
        stream_url="rtsp://admin:secret@localhost:7001/cam-1",
    )


def test_list_cameras_masks_rtsp_password(client, monkeypatch):
    monkeypatch.setattr(
        cameras_routes.repo,
        "get_all_cameras",
        AsyncMock(return_value=[_camera()]),
    )

    resp = client.get("/v1/cameras")

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["stream_url"] == f"rtsp://admin:{MASKED_PASSWORD_PLACEHOLDER}@localhost:7001/cam-1"


def test_get_camera_masks_rtsp_password(client, monkeypatch):
    monkeypatch.setattr(
        cameras_routes.repo,
        "get_camera",
        AsyncMock(return_value=_camera()),
    )

    resp = client.get("/v1/cameras/nx:cam-1")

    assert resp.status_code == 200
    assert resp.json()["stream_url"] == f"rtsp://admin:{MASKED_PASSWORD_PLACEHOLDER}@localhost:7001/cam-1"


def test_live_stream_masks_rtsp_password(client, monkeypatch):
    shim = SimpleNamespace(
        camera_id_prefix="nx:",
        get_live_stream_url=AsyncMock(return_value="rtsp://admin:secret@localhost:7001/cam-1"),
    )
    shim_sets = [SimpleNamespace(name="nx-main", vms_shim=shim)]

    async def override_shims():
        return shim_sets

    client.app.dependency_overrides[get_vms_shim_sets] = override_shims
    try:
        resp = client.get("/v1/cameras/nx:cam-1/live-stream")
    finally:
        client.app.dependency_overrides.pop(get_vms_shim_sets, None)

    assert resp.status_code == 200
    assert resp.json()["rtsp_url"] == f"rtsp://admin:{MASKED_PASSWORD_PLACEHOLDER}@localhost:7001/cam-1"


def test_discover_cameras_masks_rtsp_password(client, monkeypatch):
    shim = SimpleNamespace(discover_cameras=AsyncMock(return_value=[_camera()]))
    shim_sets = [SimpleNamespace(name="nx-main", vms_shim=shim)]

    async def override_shims():
        return shim_sets

    monkeypatch.setattr(cameras_routes.repo, "upsert_camera", AsyncMock(return_value=None))
    monkeypatch.setattr(cameras_routes.repo, "get_all_cameras", AsyncMock(return_value=[_camera()]))
    client.app.dependency_overrides[get_vms_shim_sets] = override_shims

    try:
        resp = client.post("/v1/cameras/discover")
    finally:
        client.app.dependency_overrides.pop(get_vms_shim_sets, None)

    assert resp.status_code == 200
    assert resp.json()[0]["stream_url"] == f"rtsp://admin:{MASKED_PASSWORD_PLACEHOLDER}@localhost:7001/cam-1"
