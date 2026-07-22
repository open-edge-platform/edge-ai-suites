# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for the on-demand "Run Pipeline" detect-then-reason cycle in main.py.

Each "Run Pipeline" trigger should: (1) start the DL Streamer pipeline and
block until it reaches a terminal state, (2) run the agent pipeline bounded to
exactly the detections produced by that run (start_id, end_id], and (3) reject
a concurrent second run with 409 while one is already in flight — mirroring
the reference CLI's "run inference once, then reason once" batch model.
"""

import os

os.environ.setdefault("MQTT_DISABLED", "true")

import src.main as main_mod  # noqa: E402
from src.utility.dlstreamer_client import PipelineRunError  # noqa: E402


def _reset_run_state():
    main_mod._runs.clear()
    main_mod._active_run_id = None
    if main_mod._run_lock.locked():
        main_mod._run_lock.release()


def test_execute_detect_and_reason_run_success(monkeypatch):
    _reset_run_state()

    max_ids = iter([{"max_id": 10}, {"max_id": 42}])
    monkeypatch.setattr(main_mod.storage_client, "get_max_id", lambda: next(max_ids))

    monkeypatch.setattr(
        main_mod, "run_pipeline_to_completion",
        lambda timeout=None: {"id": "abc", "state": "COMPLETED", "elapsed_time": 73.7},
    )

    captured = {}

    def fake_run_pipeline(config_path=None, prompts_dir=None, min_id=None, max_id=None):
        captured["min_id"] = min_id
        captured["max_id"] = max_id
        return {"policy": {}, "analysis": {}, "evidence": {}, "ticket": {}, "error": None,
                "window": {"min_id": min_id, "max_id": max_id}}

    monkeypatch.setattr(main_mod, "run_pipeline", fake_run_pipeline)

    run_id = "run-1"
    main_mod._runs[run_id] = {"status": "running", "phase": "detecting", "result": None}
    main_mod._run_lock.acquire()
    main_mod._active_run_id = run_id

    main_mod._execute_detect_and_reason_run(run_id, None, None)

    assert captured["min_id"] == 10
    assert captured["max_id"] == 42
    assert main_mod._runs[run_id]["status"] == "completed"
    assert main_mod._runs[run_id]["phase"] == "completed"
    assert main_mod._runs[run_id]["result"]["pipeline_status"]["state"] == "COMPLETED"
    # Run lock and active run id must be released so a subsequent run can start.
    assert main_mod._active_run_id is None
    assert not main_mod._run_lock.locked()


def test_execute_detect_and_reason_run_detection_failure(monkeypatch):
    _reset_run_state()

    monkeypatch.setattr(main_mod.storage_client, "get_max_id", lambda: {"max_id": 0})

    def failing_run_to_completion(timeout=None):
        raise PipelineRunError("pipeline did not reach a terminal state")

    monkeypatch.setattr(main_mod, "run_pipeline_to_completion", failing_run_to_completion)

    called = {"run_pipeline": False}

    def fake_run_pipeline(**kwargs):
        called["run_pipeline"] = True
        return {}

    monkeypatch.setattr(main_mod, "run_pipeline", fake_run_pipeline)

    run_id = "run-2"
    main_mod._runs[run_id] = {"status": "running", "phase": "detecting", "result": None}
    main_mod._run_lock.acquire()
    main_mod._active_run_id = run_id

    main_mod._execute_detect_and_reason_run(run_id, None, None)

    assert main_mod._runs[run_id]["status"] == "error"
    assert main_mod._runs[run_id]["phase"] == "error"
    # Agent reasoning must never run if detection itself failed.
    assert called["run_pipeline"] is False
    assert main_mod._active_run_id is None
    assert not main_mod._run_lock.locked()


def test_trigger_run_rejects_concurrent_run(monkeypatch):
    from fastapi.testclient import TestClient

    _reset_run_state()

    # Prevent the background task from actually executing during this test.
    monkeypatch.setattr(main_mod, "_execute_detect_and_reason_run", lambda *a, **k: None)

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
