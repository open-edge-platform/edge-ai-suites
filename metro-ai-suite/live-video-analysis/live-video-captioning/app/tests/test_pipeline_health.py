# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for the pipeline health monitoring service."""

from unittest.mock import MagicMock, patch

import pytest

from backend.models.responses import RunInfo
from backend.state import RUNS


def _make_run(run_id: str = "run1", pipeline_id: str = "aabbccdd") -> RunInfo:
    return RunInfo(
        runId=run_id,
        pipelineId=pipeline_id,
        peerId="s1234567",
        mqttTopic="test-prefix",
        status="running",
    )


def _status_item(pipeline_id: str, state: str = "RUNNING") -> dict:
    """Build a minimal /pipelines/status item for a given pipeline ID."""
    return {"id": pipeline_id, "state": state, "avg_fps": 30.0}


# ---------------------------------------------------------------------------
# check_pipeline_health – high-level behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_active_runs_does_nothing():
    """Health check is a no-op when there are no running runs."""
    from backend.services.pipeline_health import check_pipeline_health

    RUNS.clear()
    # Should complete without error or side-effects and never call the server
    mock_fetch = MagicMock()
    with patch("backend.services.pipeline_health._fetch_pipeline_statuses", mock_fetch):
        await check_pipeline_health()

    mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_healthy_pipeline_keeps_status_running():
    """Runs whose pipeline appears in the status list with a live state stay 'running'."""
    from backend.services.pipeline_health import check_pipeline_health

    run = _make_run(pipeline_id="aabbccdd")
    RUNS[run.runId] = run

    with patch(
        "backend.services.pipeline_health._fetch_pipeline_statuses",
        return_value=(200, [_status_item("aabbccdd", "RUNNING")]),
    ):
        await check_pipeline_health()

    assert RUNS[run.runId].status == "running"


@pytest.mark.asyncio
async def test_missing_pipeline_marks_run_as_error():
    """A pipeline absent from /pipelines/status marks the run as error."""
    from backend.services.pipeline_health import check_pipeline_health

    run = _make_run(pipeline_id="aabbccdd")
    RUNS[run.runId] = run

    # Empty list – our pipeline is not present
    with patch(
        "backend.services.pipeline_health._fetch_pipeline_statuses",
        return_value=(200, []),
    ):
        await check_pipeline_health()

    assert RUNS[run.runId].status == "error"


@pytest.mark.asyncio
async def test_unreachable_server_marks_all_running_runs_as_error():
    """When the server is unreachable all running runs are marked as error."""
    from backend.services.pipeline_health import check_pipeline_health

    run1 = _make_run("run1", "aabb1111")
    run2 = _make_run("run2", "aabb2222")
    RUNS[run1.runId] = run1
    RUNS[run2.runId] = run2

    with patch(
        "backend.services.pipeline_health._fetch_pipeline_statuses",
        return_value=(None, None),
    ):
        await check_pipeline_health()

    assert RUNS["run1"].status == "error"
    assert RUNS["run2"].status == "error"


@pytest.mark.asyncio
async def test_already_errored_runs_are_skipped():
    """Runs already in error state are not re-checked."""
    from backend.services.pipeline_health import check_pipeline_health

    run = _make_run()
    run.status = "error"
    RUNS[run.runId] = run

    mock_fetch = MagicMock()
    with patch("backend.services.pipeline_health._fetch_pipeline_statuses", mock_fetch):
        await check_pipeline_health()

    mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_stopped_runs_are_skipped():
    """Runs already in stopped state are not re-checked."""
    from backend.services.pipeline_health import check_pipeline_health

    run = _make_run()
    run.status = "stopped"
    RUNS[run.runId] = run

    mock_fetch = MagicMock()
    with patch("backend.services.pipeline_health._fetch_pipeline_statuses", mock_fetch):
        await check_pipeline_health()

    mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_only_running_runs_affected_when_mixed_statuses():
    """Only runs in 'running' state are evaluated; others are ignored."""
    from backend.services.pipeline_health import check_pipeline_health

    running_run = _make_run("run_active", "aaaa1111")
    error_run = _make_run("run_err", "bbbb2222")
    error_run.status = "error"
    RUNS[running_run.runId] = running_run
    RUNS[error_run.runId] = error_run

    # Status response is empty – running_run's pipeline is missing
    with patch(
        "backend.services.pipeline_health._fetch_pipeline_statuses",
        return_value=(200, []),
    ):
        await check_pipeline_health()

    assert RUNS["run_active"].status == "error"
    assert RUNS["run_err"].status == "error"  # unchanged


@pytest.mark.asyncio
async def test_unexpected_http_status_skips_health_check():
    """A non-200 response from /pipelines/status is treated as a transient error."""
    from backend.services.pipeline_health import check_pipeline_health

    run = _make_run()
    RUNS[run.runId] = run

    with patch(
        "backend.services.pipeline_health._fetch_pipeline_statuses",
        return_value=(503, None),
    ):
        await check_pipeline_health()

    # Run status must remain unchanged – we skip the check on unexpected responses
    assert RUNS[run.runId].status == "running"


@pytest.mark.asyncio
async def test_pipeline_id_matching_is_case_insensitive():
    """Pipeline IDs are compared case-insensitively."""
    from backend.services.pipeline_health import check_pipeline_health

    run = _make_run(pipeline_id="AABBCCDD")
    RUNS[run.runId] = run

    # Server returns the same ID in lowercase
    with patch(
        "backend.services.pipeline_health._fetch_pipeline_statuses",
        return_value=(200, [_status_item("aabbccdd", "RUNNING")]),
    ):
        await check_pipeline_health()

    assert RUNS[run.runId].status == "running"


# ---------------------------------------------------------------------------
# _fetch_pipeline_statuses – unit-level
# ---------------------------------------------------------------------------


def test_fetch_pipeline_statuses_returns_list_on_success():
    from backend.services.pipeline_health import _fetch_pipeline_statuses

    items = [_status_item("aabb1111"), _status_item("aabb2222")]
    with patch(
        "backend.services.pipeline_health.try_get_json",
        return_value=(200, items),
    ):
        code, body = _fetch_pipeline_statuses()

    assert code == 200
    assert body == items


def test_fetch_pipeline_statuses_returns_none_on_connection_failure():
    from backend.services.pipeline_health import _fetch_pipeline_statuses

    with patch(
        "backend.services.pipeline_health.try_get_json",
        return_value=(None, None),
    ):
        code, body = _fetch_pipeline_statuses()

    assert code is None
    assert body is None


# ---------------------------------------------------------------------------
# Terminal state detection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("terminal_state", ["ERROR", "ABORTED", "COMPLETED"])
@pytest.mark.asyncio
async def test_terminal_state_marks_run_as_error(terminal_state):
    """Pipelines in terminal states are treated as gone."""
    from backend.services.pipeline_health import check_pipeline_health

    run = _make_run(pipeline_id="aabbccdd")
    RUNS[run.runId] = run

    with patch(
        "backend.services.pipeline_health._fetch_pipeline_statuses",
        return_value=(200, [_status_item("aabbccdd", terminal_state)]),
    ):
        await check_pipeline_health()

    assert RUNS[run.runId].status == "error"


# ---------------------------------------------------------------------------
# start / stop monitor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_returns_none_when_interval_is_zero(monkeypatch):
    """When PIPELINE_POLL_INTERVAL is 0, the monitor is disabled."""
    import backend.services.pipeline_health as ph

    monkeypatch.setattr(ph, "PIPELINE_POLL_INTERVAL", 0)
    task = ph.start_pipeline_health_monitor()
    assert task is None


@pytest.mark.asyncio
async def test_start_creates_task_when_interval_positive(monkeypatch):
    """When PIPELINE_POLL_INTERVAL > 0, a background task is returned."""
    import asyncio
    import backend.services.pipeline_health as ph

    monkeypatch.setattr(ph, "PIPELINE_POLL_INTERVAL", 60)
    task = ph.start_pipeline_health_monitor()
    assert task is not None
    assert isinstance(task, asyncio.Task)
    # Clean up
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_stop_monitor_cancels_task(monkeypatch):
    """stop_pipeline_health_monitor cancels the running background task."""
    import asyncio
    import backend.services.pipeline_health as ph

    monkeypatch.setattr(ph, "PIPELINE_POLL_INTERVAL", 60)
    ph.start_pipeline_health_monitor()
    assert ph._health_task is not None

    await ph.stop_pipeline_health_monitor()
    assert ph._health_task is None
