# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for the detection-service's bounded "detect" run and its handoff to
the agent layer via the "batch-complete" MQTT event.

Each detection run should: (1) start the DL Streamer pipeline and block until
it reaches a terminal state, (2) publish exactly one "batch-complete" event
describing the outcome (id window on success, error on failure) — the
detection-service never calls the agent-service directly — and (3) reject a
concurrent second run with 409 while one is already in flight.
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


def test_execute_detection_run_success_publishes_batch_complete(monkeypatch):
    _reset_run_state()

    max_ids = iter([{"max_id": 10}, {"max_id": 42}])
    monkeypatch.setattr(main_mod.storage_client, "get_max_id", lambda: next(max_ids))

    monkeypatch.setattr(
        main_mod, "run_pipeline_to_completion",
        lambda device=None, video_filename=None, timeout=None:
            {"id": "abc", "state": "COMPLETED", "elapsed_time": 73.7},
    )

    published = {}

    def fake_publish(event):
        published.update(event)

    monkeypatch.setattr(main_mod, "publish_batch_complete", fake_publish)

    run_id = "run-1"
    main_mod._runs[run_id] = {"status": "running", "phase": "detecting", "result": None}
    main_mod._run_lock.acquire()
    main_mod._active_run_id = run_id

    main_mod._execute_detection_run(run_id, "CPU", None)

    assert main_mod._runs[run_id]["status"] == "completed"
    assert main_mod._runs[run_id]["phase"] == "completed"
    assert main_mod._runs[run_id]["result"]["start_id"] == 10
    assert main_mod._runs[run_id]["result"]["end_id"] == 42

    assert published["run_id"] == run_id
    assert published["status"] == "completed"
    assert published["start_id"] == 10
    assert published["end_id"] == 42

    # Run lock and active run id must be released so a subsequent run can start.
    assert main_mod._active_run_id is None
    assert not main_mod._run_lock.locked()


def test_execute_detection_run_failure_publishes_error_event(monkeypatch):
    _reset_run_state()

    monkeypatch.setattr(main_mod.storage_client, "get_max_id", lambda: {"max_id": 0})

    def failing_run_to_completion(device=None, video_filename=None, timeout=None):
        raise PipelineRunError("pipeline did not reach a terminal state")

    monkeypatch.setattr(main_mod, "run_pipeline_to_completion", failing_run_to_completion)

    published = {}
    monkeypatch.setattr(main_mod, "publish_batch_complete", lambda event: published.update(event))

    run_id = "run-2"
    main_mod._runs[run_id] = {"status": "running", "phase": "detecting", "result": None}
    main_mod._run_lock.acquire()
    main_mod._active_run_id = run_id

    main_mod._execute_detection_run(run_id, "NPU", None)

    assert main_mod._runs[run_id]["status"] == "error"
    assert main_mod._runs[run_id]["phase"] == "error"
    assert published["status"] == "error"
    assert "pipeline did not reach a terminal state" in published["error"]
    assert main_mod._active_run_id is None
    assert not main_mod._run_lock.locked()


def test_trigger_run_rejects_concurrent_run(monkeypatch):
    from fastapi.testclient import TestClient

    _reset_run_state()

    # Prevent the background task from actually executing during this test.
    monkeypatch.setattr(main_mod, "_execute_detection_run", lambda *a, **k: None)

    client = TestClient(main_mod.app)

    first = client.post("/detection/run", json={})
    assert first.status_code == 202
    first_run_id = first.json()["run_id"]

    # Simulate the run still being in-flight (lock not released, since we
    # stubbed out the background task above).
    second = client.post("/detection/run", json={})
    assert second.status_code == 409
    assert second.json()["detail"]["run_id"] == first_run_id

    _reset_run_state()
