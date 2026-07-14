# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Metrics Manager-backed UI telemetry snippets."""

import os
import sys
import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest


ui_path = os.path.join(os.path.dirname(__file__), "..", "..", "src", "ui")


@pytest.fixture
def ui_app_module():
    saved_modules = {
        name: sys.modules.get(name)
        for name in ("app", "config", "data_loader", "models")
        if name in sys.modules
    }
    for name in ("app", "config", "data_loader", "models"):
        sys.modules.pop(name, None)

    sys.path.insert(0, ui_path)
    try:
        module = importlib.import_module("app")
        yield module
    finally:
        if ui_path in sys.path:
            sys.path.remove(ui_path)
        for name in ("app", "config", "data_loader", "models"):
            sys.modules.pop(name, None)
        sys.modules.update(saved_modules)


def test_metrics_panel_mentions_metrics_manager_and_npu(ui_app_module):
    html = ui_app_module._metrics_panel_html()

    assert "System Telemetry" in html
    assert "Metrics Manager" in html
    assert "NPU" in html


def test_metrics_js_uses_sse_and_metrics_manager_metric_names(ui_app_module):
    js = ui_app_module._metrics_js()

    assert "new EventSource(STREAM_URL)" in js
    assert "STREAM_URL = '/metrics/stream'" in js
    assert "new WebSocket" not in js
    assert "cpu_usage_user" in js
    assert "mem_used_percent" in js
    assert "gpu_engine_usage_usage" in js
    assert "npu_utilization" in js


def test_metrics_stream_proxy_forwards_sse_frame(monkeypatch, ui_app_module):
    captured = {}

    class FakeContent:
        async def iter_any(self):
            yield b'data: {"metrics":[]}\n\n'

    class FakeResponse:
        content = FakeContent()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def raise_for_status(self):
            return None

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def get(self, url, headers):
            captured["url"] = url
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setenv("METRICS_STREAM_URL", "http://metrics-manager:9090/metrics/stream")
    monkeypatch.setattr(ui_app_module.aiohttp, "ClientSession", FakeSession)

    app = FastAPI()
    ui_app_module._mount_metrics_stream_proxy(app)

    with TestClient(app) as client:
        response = client.get("/metrics/stream")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text == 'data: {"metrics":[]}\n\n'
    assert captured["url"] == "http://metrics-manager:9090/metrics/stream"
    assert captured["headers"] == {"Accept": "text/event-stream"}
