# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Additional tests for interface module functions (polling, processing)."""
import pytest
import threading
import types
from datetime import datetime, timedelta

import ui.interface.interface as iface


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(iface.time, "sleep", lambda *a, **k: None, raising=False)


def test_refresh_summary_status_dict(monkeypatch):
    monkeypatch.setattr(iface, "fetch_summary_status", lambda sid: {"status": "ok", "value": 42})
    md, toast_hide, close_hide = iface.refresh_summary_status("sum1")
    assert "Summary ID" in md
    assert toast_hide["visible"] is False
    assert close_hide["visible"] is False


def test_refresh_summary_status_string_json(monkeypatch):
    import json
    monkeypatch.setattr(iface, "fetch_summary_status", lambda sid: json.dumps({"status": "ok"}))
    md, _, _ = iface.refresh_summary_status("sum2")
    assert "```json" in md


def test_refresh_summary_status_error(monkeypatch):
    monkeypatch.setattr(iface, "fetch_summary_status", lambda sid: (_ for _ in ()).throw(RuntimeError("boom")))
    md, toast_show, close_show = iface.refresh_summary_status("sum3")
    assert "Error fetching status" in md
    assert toast_show["visible"] is True
    assert close_show["visible"] is True


def test_wrapper_fn_success(monkeypatch):
    # Provide a fake process_and_poll that returns a successful summarize result
    def fake_process_and_poll(camera, start, duration, action, status_output):
        return {"status": "success", "summary_id": {"abc": 1}, "message": "All good"}
    monkeypatch.setattr(iface, "process_and_poll", fake_process_and_poll)
    now = datetime.now() - timedelta(minutes=1)
    result, toast, close_btn, summary_id, status_output, polling_enabled = iface.wrapper_fn(
        camera="cam1",
        start=now,
        duration=10,
        action="Summarize",
        status_output_box=None,
        previous_summary_id=None,
    )
    assert result["status"] == "success"
    assert summary_id == "abc"
    assert polling_enabled is True
    assert "All good" in toast["value"]


def test_process_and_poll_add_to_search(monkeypatch):
    # process_video returns a dict w/o starting thread
    monkeypatch.setattr(iface, "process_video", lambda *a, **k: {"status": "success", "summary_id": {"xyz": 1}, "message": "indexed"})
    out = iface.process_and_poll("cam1", datetime.now(), 5, "Add to Search", None)
    assert out["message"] == "indexed"


def test_process_and_poll_summarize_thread_spawn(monkeypatch):
    # Track if thread would be started
    started = {}

    class DummyThread:
        def __init__(self, target, args, daemon):
            self._target = target
            self._args = args
            self._daemon = daemon
        def start(self):
            started["started"] = True

    monkeypatch.setattr(iface.threading, "Thread", DummyThread)
    monkeypatch.setattr(iface, "process_video", lambda *a, **k: {"status": "success", "summary_id": {"s123": 1}, "message": "summarize"})
    # Prevent poll loop from sleeping long
    monkeypatch.setattr(iface, "poll_summary_status", lambda *a, **k: None)
    out = iface.process_and_poll("cam1", datetime.now(), 3, "Summarize", None)
    assert out["message"] == "summarize"
    assert started.get("started") is True


def test_poll_summary_status_single_iteration(monkeypatch):
    # Ensure it breaks immediately with status completed
    monkeypatch.setattr(iface, "fetch_summary_status", lambda sid: {"status": "completed", "x": 1})
    # Provide dummy status_output and stop_event
    stop_event = types.SimpleNamespace(is_set=lambda: False)
    iface.poll_summary_status("abc", None, stop_event)  # Should return quickly without exception


def test_ui_builder_callable(monkeypatch):
    # create_ui should build a Blocks object without launching the server
    monkeypatch.setattr(iface, "fetch_cameras_with_labels", lambda: (["c1"], {"c1": ["person"]}))
    monkeypatch.setattr(iface, "fetch_cameras", lambda: ["c1"])  # fallback not used
    monkeypatch.setattr(iface, "fetch_camera_watcher_mapping", lambda: {"c1": True})
    monkeypatch.setattr(iface, "fetch_rule_responses", lambda: {})
    monkeypatch.setattr(iface, "fetch_search_responses", lambda: {})
    ui_obj = iface.create_ui()
    assert ui_obj is not None
