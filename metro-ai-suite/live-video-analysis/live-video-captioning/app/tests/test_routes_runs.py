# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.routes.runs, run lifecycle endpoints."""

from unittest.mock import patch

from backend.state import RUNS
from backend.models.responses import RunInfo


# ===================================================================
# POST /api/runs, start a new run
# ===================================================================
class TestStartRun:
    """POST /api/runs endpoint."""

    def test_start_run_success(self, client):
        """A valid request creates a run and returns RunInfo."""
        with patch("backend.routes.runs.http_json", return_value='"pipeline-abc"'):
            resp = client.post(
                "/api/runs",
                json={"rtspUrl": "rtsp://10.0.0.1/stream"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "runId" in body
        assert body["pipelineId"] == "pipeline-abc"

    def test_start_run_with_custom_name(self, client):
        """A run with a custom runName uses it as the run ID."""
        with patch("backend.routes.runs.http_json", return_value='"p1"'):
            resp = client.post(
                "/api/runs",
                json={
                    "rtspUrl": "rtsp://10.0.0.1/stream",
                    "runName": "My Run",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["runId"] == "My_Run"
        assert body["runName"] == "My_Run"

    def test_start_run_sanitizes_name(self, client):
        """Special characters in runName are removed."""
        with patch("backend.routes.runs.http_json", return_value='"p1"'):
            resp = client.post(
                "/api/runs",
                json={
                    "rtspUrl": "rtsp://10.0.0.1/stream",
                    "runName": "test@run!#",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["runId"] == "testrun"

    def test_start_run_duplicate_name_gets_suffix(self, client):
        """Duplicate run names get an incremented suffix."""
        RUNS["demo"] = RunInfo(
            runId="demo", pipelineId="p0", peerId="peer0", mqttTopic="t/demo"
        )
        with patch("backend.routes.runs.http_json", return_value='"p2"'):
            resp = client.post(
                "/api/runs",
                json={
                    "rtspUrl": "rtsp://10.0.0.1/stream",
                    "runName": "demo",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["runId"] == "demo_1"

    def test_start_run_pipeline_empty_response(self, client):
        """An empty pipeline ID from the server returns 502."""
        with patch("backend.routes.runs.http_json", return_value='""'):
            resp = client.post(
                "/api/runs",
                json={"rtspUrl": "rtsp://10.0.0.1/stream"},
            )
        assert resp.status_code == 502

    def test_start_run_invalid_rtsp_url(self, client):
        """An invalid RTSP URL returns 422 (validation error)."""
        resp = client.post(
            "/api/runs",
            json={"rtspUrl": "http://not-rtsp.com/stream"},
        )
        assert resp.status_code == 422

    def test_start_run_stores_in_runs(self, client):
        """The newly created run is stored in the global RUNS dict."""
        with patch("backend.routes.runs.http_json", return_value='"p-store"'):
            resp = client.post(
                "/api/runs",
                json={"rtspUrl": "rtsp://10.0.0.1/stream"},
            )
        run_id = resp.json()["runId"]
        assert run_id in RUNS


# ===================================================================
# GET /api/runs, list all runs
# ===================================================================
class TestListRuns:
    """GET /api/runs endpoint."""

    def test_list_runs_empty(self, client):
        """Returns an empty list when no runs exist."""
        resp = client.get("/api/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_runs_returns_active_runs(self, client):
        """Returns all active runs."""
        RUNS["r1"] = RunInfo(
            runId="r1", pipelineId="p1", peerId="peer1", mqttTopic="t/r1"
        )
        RUNS["r2"] = RunInfo(
            runId="r2", pipelineId="p2", peerId="peer2", mqttTopic="t/r2"
        )
        resp = client.get("/api/runs")
        assert resp.status_code == 200
        ids = {r["runId"] for r in resp.json()}
        assert ids == {"r1", "r2"}


# ===================================================================
# GET /api/runs/{run_id}, get single run
# ===================================================================
class TestGetRun:
    """GET /api/runs/{run_id} endpoint."""

    def test_get_existing_run(self, client):
        """Returns details for an existing run."""
        RUNS["r1"] = RunInfo(
            runId="r1", pipelineId="p1", peerId="peer1", mqttTopic="t/r1"
        )
        resp = client.get("/api/runs/r1")
        assert resp.status_code == 200
        assert resp.json()["runId"] == "r1"

    def test_get_nonexistent_run_returns_404(self, client):
        """Returns 404 when the run ID does not exist."""
        resp = client.get("/api/runs/nonexistent")
        assert resp.status_code == 404


# ===================================================================
# DELETE /api/runs/{run_id}, stop a run
# ===================================================================
class TestStopRun:
    """DELETE /api/runs/{run_id} endpoint."""

    def test_stop_existing_run(self, client):
        """Stopping an existing run removes it and returns 'stopped'."""
        RUNS["r1"] = RunInfo(
            runId="r1", pipelineId="p1", peerId="peer1", mqttTopic="t/r1"
        )
        with patch("backend.routes.runs.http_json", return_value=""):
            resp = client.delete("/api/runs/r1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"
        assert "r1" not in RUNS

    def test_stop_nonexistent_run_returns_404(self, client):
        """Returns 404 when trying to stop a non-existent run."""
        resp = client.delete("/api/runs/nonexistent")
        assert resp.status_code == 404

    def test_stop_run_pipeline_error_still_cleans_up(self, client):
        """Even if the upstream DELETE fails, the run is removed locally."""
        from fastapi import HTTPException

        RUNS["r1"] = RunInfo(
            runId="r1", pipelineId="p1", peerId="peer1", mqttTopic="t/r1"
        )
        with patch(
            "backend.routes.runs.http_json",
            side_effect=HTTPException(status_code=502, detail="gone"),
        ):
            resp = client.delete("/api/runs/r1")
        assert resp.status_code == 200
        assert "r1" not in RUNS
