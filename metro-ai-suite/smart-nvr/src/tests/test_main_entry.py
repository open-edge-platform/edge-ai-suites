# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Tests for backend main entry point (uvicorn run logic)."""
import runpy
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
import importlib


def test_main_fastapi_startup_and_root(monkeypatch):
    # Patch external side-effect functions BEFORE importing main
    monkeypatch.setattr("src.main.restore_camera_watchers_from_redis", AsyncMock())
    monkeypatch.setattr("src.main.start_mqtt", AsyncMock())
    monkeypatch.setattr("src.main.redis.from_url", lambda *a, **k: AsyncMock())

    from src.main import app  # import after patches

    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "NVR Event Router" in resp.json()["message"]


def test_main_dunder_main_run(monkeypatch):
    # Simulate executing the module as a script, but prevent real uvicorn startup.
    calls = {}

    def fake_run(app_path: str, host: str, port: int, reload: bool, log_level: str):  # noqa: D401
        calls["invoked"] = True
        calls["app_path"] = app_path
        calls["host"] = host
        calls["port"] = port
        calls["reload"] = reload
        calls["log_level"] = log_level
        return None

    monkeypatch.setattr("uvicorn.run", fake_run, raising=False)

    runpy.run_module("src.main", run_name="__main__")

    assert calls.get("invoked"), "Expected uvicorn.run to be invoked in __main__ block"
    assert calls.get("app_path") == "main:app"
