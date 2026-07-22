# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for the agent-service's reasoning-only run flow.

The agent-service must never talk to a detector directly. It reasons either:
(1) when it receives a "batch-complete" MQTT event from the detection layer
(``status: completed`` -> reason over the event's id window under the same
run_id; ``status: error`` -> skip reasoning and record the failure as-is), or
(2) via an explicit ``POST /agents/run`` call bounded by an optional
``min_id``/``max_id`` window, for standalone use without a detection layer.
"""

import os

os.environ.setdefault("MQTT_DISABLED", "true")

import src.main as main_mod  # noqa: E402


def _reset_run_state():
    main_mod._runs.clear()
    main_mod._active_run_id = None
    if main_mod._reasoning_lock.locked():
        main_mod._reasoning_lock.release()


def test_execute_reasoning_run_success(monkeypatch):
    _reset_run_state()

    captured = {}

    def fake_run_pipeline(config_path=None, prompts_dir=None, min_id=None, max_id=None):
        captured["min_id"] = min_id
        captured["max_id"] = max_id
        return {"policy": {}, "analysis": {}, "evidence": {}, "ticket": {}, "error": None,
                "window": {"min_id": min_id, "max_id": max_id}}

    monkeypatch.setattr(main_mod, "run_pipeline", fake_run_pipeline)

    run_id = "run-1"
    main_mod._runs[run_id] = {"status": "running", "phase": "reasoning", "result": None}
    main_mod._reasoning_lock.acquire()
    main_mod._active_run_id = run_id

    main_mod._execute_reasoning_run(run_id, None, None, 10, 42)

    assert captured["min_id"] == 10
    assert captured["max_id"] == 42
    assert main_mod._runs[run_id]["status"] == "completed"
    assert main_mod._runs[run_id]["phase"] == "completed"
    # Lock and active run id must be released so a subsequent run can start.
    assert main_mod._active_run_id is None
    assert not main_mod._reasoning_lock.locked()


def test_handle_batch_complete_event_success_triggers_reasoning(monkeypatch):
    _reset_run_state()

    captured = {}

    def fake_run_pipeline(config_path=None, prompts_dir=None, min_id=None, max_id=None):
        captured["min_id"] = min_id
        captured["max_id"] = max_id
        return {"policy": {}, "analysis": {}, "evidence": {}, "ticket": {}, "error": None,
                "window": {"min_id": min_id, "max_id": max_id}}

    monkeypatch.setattr(main_mod, "run_pipeline", fake_run_pipeline)

    event = {"run_id": "run-2", "status": "completed", "start_id": 5, "end_id": 20,
              "pipeline_status": {"state": "COMPLETED"}}
    main_mod._handle_batch_complete_event(event)

    # Reasoning is dispatched on a background thread — wait for it to finish.
    import time
    for _ in range(50):
        if main_mod._runs.get("run-2", {}).get("status") != "running":
            break
        time.sleep(0.05)

    assert captured["min_id"] == 5
    assert captured["max_id"] == 20
    assert main_mod._runs["run-2"]["status"] == "completed"
    assert main_mod._runs["run-2"]["result"]["pipeline_status"]["state"] == "COMPLETED"


def test_handle_batch_complete_event_error_skips_reasoning(monkeypatch):
    _reset_run_state()

    called = {"run_pipeline": False}

    def fake_run_pipeline(**kwargs):
        called["run_pipeline"] = True
        return {}

    monkeypatch.setattr(main_mod, "run_pipeline", fake_run_pipeline)

    event = {"run_id": "run-3", "status": "error", "error": "NPU device not found"}
    main_mod._handle_batch_complete_event(event)

    assert main_mod._runs["run-3"]["status"] == "error"
    assert main_mod._runs["run-3"]["phase"] == "error"
    assert main_mod._runs["run-3"]["result"]["error"] == "NPU device not found"
    # Reasoning must never run if the detection run itself failed.
    assert called["run_pipeline"] is False


def test_trigger_run_rejects_concurrent_run(monkeypatch):
    from fastapi.testclient import TestClient

    _reset_run_state()

    # Prevent the background task from actually executing during this test.
    monkeypatch.setattr(main_mod, "_execute_reasoning_run", lambda *a, **k: None)

    client = TestClient(main_mod.app)

    first = client.post("/agents/run", json={})
    assert first.status_code == 202
    first_run_id = first.json()["run_id"]

    # Simulate the run still being in-flight (lock not released, since we
    # stubbed out the background task above).
    second = client.post("/agents/run", json={})
    assert second.status_code == 409
    assert second.json()["detail"]["run_id"] == first_run_id

    _reset_run_state()
