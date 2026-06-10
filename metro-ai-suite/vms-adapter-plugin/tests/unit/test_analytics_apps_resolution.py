# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for analytics-app camera resolution before payload dispatch."""

from __future__ import annotations

import pytest
from pydantic import create_model

from plugin.core.api.routes import analytics_apps as analytics_apps_routes
from plugin.core.models.domain import Camera


class _FakeDb:
    pass


@pytest.mark.asyncio
async def test_start_resolves_camera_id_to_raw_rtsp(monkeypatch):
    raw_camera = Camera(
        camera_id="nx:cam-1",
        name="Front Door",
        vendor="nx_witness",
        stream_url="rtsp://admin:secret@localhost:7001/cam-1",
    )

    async def fake_get_camera(_db, camera_id):
        assert camera_id == "nx:cam-1"
        return raw_camera

    monkeypatch.setattr(analytics_apps_routes.repo, "get_camera", fake_get_camera)

    captured = {}

    class FakeShim:
        @property
        def param_model(self):
            return create_model(
                "FakeParams",
                camera_id=(str, ...),
                camera_id_ref=(str, ""),
                parameters=(dict, {}),
            )

        def camera_fields(self):
            return ["camera_id"]

        async def start(self, params):
            captured["payload"] = params.model_dump()
            return {"status": "ok"}

    monkeypatch.setattr(analytics_apps_routes, "_require_shim", lambda _app_id: FakeShim())

    result = await analytics_apps_routes.start_analytics_app_run(
        "dls_vision",
        payload={"camera_id": "nx:cam-1", "parameters": {}},
        db=_FakeDb(),
    )

    assert result["status"] == "ok"
    assert captured["payload"]["camera_id"] == raw_camera.stream_url
    assert captured["payload"]["camera_id_ref"] == "nx:cam-1"
