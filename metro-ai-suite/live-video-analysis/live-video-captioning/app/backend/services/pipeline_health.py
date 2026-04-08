# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Background service that periodically polls the dlstreamer-pipeline server.

A single ``GET /pipelines/status`` call returns the state of every active
pipeline instance at once, replacing the previous per-run polling approach.
This reduces HTTP overhead proportionally to the number of concurrent runs.

When the pipeline server crashes or is restarted, any in-memory runs that
reference a pipeline instance that no longer appears in the status response
are automatically marked as ``"error"`` so the frontend reflects the real state.

The polling interval is controlled by the ``PIPELINE_POLL_INTERVAL`` env var
(default **8 s**). Setting it to ``0`` disables the monitor entirely.

In addition, the SSE generator in ``routes/runs.py`` triggers an immediate
:func:`check_pipeline_health` call after 10 consecutive seconds of MQTT
silence, providing sub-10-second detection even when the poll interval is large.

Pipeline instance state transitions detected here:
- Server unreachable (connection error) → all ``"running"`` runs → ``"error"``
- Instance absent from ``/pipelines/status`` response → that run → ``"error"``
- Instance ``state`` is a terminal value (``error``, ``aborted``, ``completed``)
  → that run → ``"error"``
"""

import asyncio
import logging
from typing import Optional

from ..config import PIPELINE_POLL_INTERVAL, PIPELINE_SERVER_URL
from ..state import RUNS
from .http_client import try_get_json

logger = logging.getLogger("app.pipeline_health")

# States reported by the dlstreamer-pipeline server that indicate a pipeline
# instance is no longer actively processing frames.  Comparison is done after
# lowercasing the value returned by the server.
_TERMINAL_STATES = {"error", "aborted", "completed"}

_health_task: Optional[asyncio.Task] = None


def _fetch_pipeline_statuses() -> tuple[Optional[int], Optional[list]]:
    """Fetch all active pipeline statuses in a single HTTP request.

    Calls ``GET /pipelines/status`` which returns a JSON array of objects,
    each describing one running pipeline instance.

    Returns:
        A tuple of ``(status_code, body)`` where *body* is the parsed JSON
        list.  Returns ``(None, None)`` when the server cannot be reached.
    """
    url = f"{PIPELINE_SERVER_URL.rstrip('/')}/pipelines/status"
    return try_get_json(url, timeout=10)


async def check_pipeline_health() -> None:
    """Check all active runs against the pipeline server in a single request.

    ``GET /pipelines/status`` returns the state of every active pipeline
    instance at once.  Runs whose instance has disappeared or entered a
    terminal state are marked ``status="error"``.  If the server itself is
    unreachable, all currently ``"running"`` runs are marked ``"error"``
    immediately.
    """
    active_runs = [
        (run_id, run_info)
        for run_id, run_info in list(RUNS.items())
        if run_info.status == "running"
    ]

    if not active_runs:
        return

    status_code, body = await asyncio.to_thread(_fetch_pipeline_statuses)

    if status_code is None:
        logger.warning(
            "Pipeline server unreachable – marking all %d running run(s) as error.",
            len(active_runs),
        )
        for run_id, run_info in active_runs:
            run_info.status = "error"
            logger.warning("Run %s marked as error: pipeline server is unreachable.", run_id)
        return

    if status_code != 200 or not isinstance(body, list):
        logger.warning(
            "Unexpected response from GET /pipelines/status (HTTP %s) – skipping health check.",
            status_code,
        )
        return

    # Build a lookup: lowercase pipeline_id → lowercase state string.
    # The pipeline server uses uppercase state values (e.g. "RUNNING").
    active_pipeline_states: dict[str, str] = {
        item["id"].lower(): item.get("state", "").lower()
        for item in body
        if isinstance(item, dict) and "id" in item
    }

    for run_id, run_info in active_runs:
        pipeline_id = run_info.pipelineId.lower()
        state = active_pipeline_states.get(pipeline_id)

        if state is None:
            # Pipeline instance absent from the status list – it has been removed.
            run_info.status = "error"
            logger.warning(
                "Run %s (pipeline %s) not found in /pipelines/status – marking as error.",
                run_id,
                run_info.pipelineId,
            )
        elif state in _TERMINAL_STATES:
            run_info.status = "error"
            logger.warning(
                "Run %s (pipeline %s) is in terminal state '%s' – marking as error.",
                run_id,
                run_info.pipelineId,
                state,
            )


async def _pipeline_health_loop() -> None:
    """Infinite loop that calls :func:`check_pipeline_health` on a fixed interval."""
    logger.info(
        "Pipeline health monitor started (poll interval: %s s).",
        PIPELINE_POLL_INTERVAL,
    )
    while True:
        try:
            await check_pipeline_health()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Unexpected error during pipeline health check: %s", exc)
        await asyncio.sleep(PIPELINE_POLL_INTERVAL)


def start_pipeline_health_monitor() -> Optional[asyncio.Task]:
    """Start the background health-monitor task.

    Returns ``None`` when ``PIPELINE_POLL_INTERVAL`` is 0 (monitoring disabled).
    """
    global _health_task
    if PIPELINE_POLL_INTERVAL == 0:
        logger.info("Pipeline health monitor disabled (PIPELINE_POLL_INTERVAL=0).")
        return None
    _health_task = asyncio.create_task(
        _pipeline_health_loop(), name="pipeline-health-monitor"
    )
    return _health_task


async def stop_pipeline_health_monitor() -> None:
    """Cancel and await the background health-monitor task."""
    global _health_task
    if _health_task and not _health_task.done():
        _health_task.cancel()
        try:
            await _health_task
        except asyncio.CancelledError:
            pass
    _health_task = None
    logger.info("Pipeline health monitor stopped.")
