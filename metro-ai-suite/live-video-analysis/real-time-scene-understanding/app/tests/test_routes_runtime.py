# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for backend.routes.runtime."""

from __future__ import annotations

import json
from types import SimpleNamespace

from backend.routes.runtime import build_runtime_config_router
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _fake_settings() -> SimpleNamespace:
    return SimpleNamespace(
        WEBRTC_SIGNALING_URL="wss://example",
        WEBRTC_SIGNALING_PORT=8889,
        METRICS_SERVICE_PORT=9090,
        ALERT_VLM_MODEL="InternVL2-1B",
        ALERT_VLM_DEVICE="NPU",
        ALERT_VLM_MAX_TOKENS=32,
        DEEP_ANALYZER_ENABLED=True,
        DEEP_ANALYZER_MODEL="Qwen3.5-2B-int4-ov",
        DEEP_ANALYZER_DEVICE="GPU",
        DEEP_ANALYZER_MAX_FRAMES=8,
        DEEP_ANALYZER_MAX_TOKENS=128,
    )


class TestRuntimeConfigEndpoint:
    def test_returns_javascript_assigning_runtime_config(self):
        settings = _fake_settings()
        app = FastAPI()
        app.include_router(build_runtime_config_router(settings))
        client = TestClient(app)

        response = client.get("/api/runtime-config.js")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/javascript")
        assert response.text.startswith("window.RUNTIME_CONFIG = ")

        payload = json.loads(response.text.removeprefix("window.RUNTIME_CONFIG = ").rstrip(";"))
        assert payload["alertVlmModel"] == "InternVL2-1B"
        assert payload["deepAnalyzerEnabled"] is True
        assert payload["webrtcSignalingPort"] == 8889
