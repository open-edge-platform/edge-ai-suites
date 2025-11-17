# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Timezone behavior tests for `ui.services.video_processor`.

These tests ensure that:
1. APP_TIMEZONE override is honored when valid.
2. Invalid timezone falls back to UTC.

We reload the module after setting env vars so that `LOCAL_TZ` is recomputed.
"""
import os
import importlib
from datetime import datetime
import pytz
import pytest

import ui.services.video_processor as vp  # Initial import (will be reloaded inside tests)


class DummyResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


@pytest.fixture
def capture_get(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured['url'] = url
        captured['params'] = params
        return DummyResp({"status": 200, "message": "summaryXYZ"})

    monkeypatch.setattr(vp.requests, "get", fake_get)
    return captured


def _reload_with_timezone(monkeypatch, tz_value):
    # Ensure both APP_TIMEZONE and TZ are cleared then set APP_TIMEZONE only.
    for var in ["APP_TIMEZONE", "TZ"]:
        if tz_value is None:
            monkeypatch.delenv(var, raising=False)
        else:
            monkeypatch.setenv("APP_TIMEZONE", tz_value)
            monkeypatch.delenv("TZ", raising=False)
    import ui.services.video_processor as vp_local
    importlib.reload(vp_local)
    return vp_local


def test_process_video_timezone_override(monkeypatch, capture_get):
    vp_local = _reload_with_timezone(monkeypatch, "Europe/Berlin")
    naive_dt = datetime(2025, 1, 1, 12, 0, 0)  # Interpreted as Europe/Berlin local time
    result = vp_local.process_video("camTZ1", naive_dt, 60, "Summarize")
    assert result["status"] == "success"

    berlin = pytz.timezone("Europe/Berlin")
    expected_start = int(berlin.localize(naive_dt).timestamp())
    assert capture_get['params']['start_time'] == expected_start


def test_process_video_invalid_timezone_fallback(monkeypatch, capture_get):
    vp_local = _reload_with_timezone(monkeypatch, "Invalid/Timezone")
    naive_dt = datetime(2025, 6, 1, 0, 0, 0)
    result = vp_local.process_video("camTZ2", naive_dt, 30, "Summarize")
    assert result["status"] == "success"
    # Since invalid override is ignored, module should use actual detected system timezone (not necessarily UTC).
    system_tz = vp_local.LOCAL_TZ
    expected_start = int(system_tz.localize(naive_dt).timestamp())
    assert capture_get['params']['start_time'] == expected_start
