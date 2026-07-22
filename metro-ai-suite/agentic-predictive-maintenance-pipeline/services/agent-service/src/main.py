# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""FastAPI entry point for the agent-service.

Detection-agnostic by design: this service never starts or polls DL Streamer
(or any other detector) directly. It reasons over detections already present
in the storage-service, triggered in one of two ways:

  1. Event-driven (primary) — a "batch-complete" MQTT event from the
     detection layer names an id window (``start_id``/``end_id``) that is
     ready to reason over; see ``batch_event_subscriber.py``.
  2. Explicit (fallback) — a direct ``POST /agents/run`` call with an
     optional ``min_id``/``max_id`` window, useful for standalone testing
     without a detection layer at all.
"""

import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

from .meta_agent import run_pipeline
from .batch_event_subscriber import start_subscriber, set_on_batch_complete

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger(__name__)

# In-memory run store (keyed by run_id). Each run tracks a "phase":
#   "reasoning" -> "completed" / "error"
# For event-driven runs, run_id is supplied by the detection layer (carried in
# the batch-complete event) so the UI can correlate the detection and
# reasoning halves of the same run.
_runs: dict[str, dict] = {}

_CONFIG_PATH  = os.environ.get("AGENTS_CONFIG_PATH", None)
_PROMPTS_DIR  = os.environ.get("USE_CASE_PROMPTS_DIR", None)

# Reasoning is serialized (single shared LLM/OVMS backend) whether triggered
# by an MQTT event or an explicit API call. Callers must acquire this lock
# (and set _active_run_id) before invoking `_execute_reasoning_run`, which
# always releases both in a `finally` block.
_reasoning_lock = threading.Lock()
_active_run_id: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Subscribe to "batch-complete" events from the detection layer (non-
    # blocking background thread) so reasoning runs whenever a detection run
    # finishes, without this service ever calling into the detection layer.
    if os.environ.get("MQTT_DISABLED", "false").lower() != "true":
        set_on_batch_complete(_handle_batch_complete_event)
        start_subscriber()
    yield


app = FastAPI(
    title="APM Agent Service",
    description="Agentic Predictive Maintenance — multi-agent reasoning service (detection-agnostic)",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Request / Response models ─────────────────────────────────────────────────

class RunRequest(BaseModel):
    config_path: Optional[str] = None
    prompts_dir: Optional[str] = None
    min_id: Optional[int] = None
    max_id: Optional[int] = None


class RunResponse(BaseModel):
    run_id: str
    status: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/agents/run", response_model=RunResponse, status_code=202)
async def trigger_run(req: RunRequest, background_tasks: BackgroundTasks):
    """Explicitly trigger one reasoning pass over an (optional) id window.

    This is a fallback trigger for standalone use (no detection layer
    involved) — the primary trigger is the "batch-complete" MQTT event
    handled by ``_handle_batch_complete_event``. Rejects a new run with 409
    while one is already in flight.
    """
    global _active_run_id
    if not _reasoning_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail={"message": "A reasoning run is already in progress", "run_id": _active_run_id},
        )

    run_id = str(uuid.uuid4())
    _active_run_id = run_id
    _runs[run_id] = {"status": "running", "phase": "reasoning", "result": None}
    background_tasks.add_task(
        _execute_reasoning_run, run_id, req.config_path, req.prompts_dir, req.min_id, req.max_id,
    )
    return RunResponse(run_id=run_id, status="running")


@app.get("/agents/status/{run_id}")
def get_status(run_id: str):
    """Return the status (and current phase) of a reasoning run."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    run = _runs[run_id]
    return {"run_id": run_id, "status": run["status"], "phase": run.get("phase")}


@app.get("/agents/results/{run_id}")
def get_results(run_id: str):
    """Return the results of a completed reasoning run."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    run = _runs[run_id]
    if run["status"] == "running":
        raise HTTPException(status_code=202, detail=f"Run still in progress (phase={run.get('phase')})")
    return {"run_id": run_id, **run["result"]}


@app.get("/agents/runs")
def list_runs(id: Optional[str] = None):
    """List all runs with their status/phase. Optionally filter by run id."""
    if id is not None:
        if id not in _runs:
            raise HTTPException(status_code=404, detail="Run not found")
        return [{"run_id": id, "status": _runs[id]["status"], "phase": _runs[id].get("phase")}]
    return [{"run_id": k, "status": v["status"], "phase": v.get("phase")} for k, v in _runs.items()]


@app.get("/health")
def health():
    return {"status": "ok", "service": "agent-service", "run_count": len(_runs)}


@app.get("/metrics")
def metrics():
    total   = len(_runs)
    done    = sum(1 for r in _runs.values() if r["status"] == "completed")
    failed  = sum(1 for r in _runs.values() if r["status"] == "error")
    running = sum(1 for r in _runs.values() if r["status"] == "running")
    lines = [
        "# HELP apm_agent_runs_total Total pipeline runs",
        "# TYPE apm_agent_runs_total counter",
        f"apm_agent_runs_total {total}",
        "# HELP apm_agent_runs_completed Completed pipeline runs",
        "# TYPE apm_agent_runs_completed counter",
        f"apm_agent_runs_completed {done}",
        "# HELP apm_agent_runs_failed Failed pipeline runs",
        "# TYPE apm_agent_runs_failed counter",
        f"apm_agent_runs_failed {failed}",
        "# HELP apm_agent_runs_running Currently running pipeline runs",
        "# TYPE apm_agent_runs_running gauge",
        f"apm_agent_runs_running {running}",
    ]
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _handle_batch_complete_event(event: dict):
    """React to a "batch-complete" event published by the detection layer.

    On ``status: completed``, run reasoning bounded to the event's
    (``start_id``, ``end_id``] window, under the *same* ``run_id`` the
    detection layer used — this lets the UI correlate the detecting and
    reasoning phases of one end-to-end run.

    On ``status: error`` (the detection run itself failed), reasoning is
    skipped entirely and the run is recorded as failed — the agent-service
    must never reason over stale/unrelated detections just because a batch-
    complete event arrived.
    """
    global _active_run_id
    run_id = event.get("run_id")
    if not run_id:
        log.warning("Ignoring batch-complete event with no run_id: %s", event)
        return

    if event.get("status") != "completed":
        log.info("Run %s: detection failed (%s) — skipping reasoning", run_id, event.get("error"))
        _runs[run_id] = {
            "status": "error", "phase": "error",
            "result": {"error": event.get("error", "Detection run failed")},
        }
        return

    # Serialize actual reasoning execution (shared LLM/OVMS backend) without
    # blocking the MQTT event loop thread itself.
    def _acquire_and_run():
        global _active_run_id
        _reasoning_lock.acquire()
        _active_run_id = run_id
        _runs[run_id] = {"status": "running", "phase": "reasoning", "result": None}
        _execute_reasoning_run(
            run_id, None, None, event.get("start_id"), event.get("end_id"),
            pipeline_status=event.get("pipeline_status"),
        )

    threading.Thread(target=_acquire_and_run, daemon=True).start()


def _execute_reasoning_run(
    run_id: str,
    config_path: str | None,
    prompts_dir: str | None,
    min_id: int | None,
    max_id: int | None,
    pipeline_status: dict | None = None,
):
    """Run the 4-agent pipeline bounded to (``min_id``, ``max_id``] and store the result.

    Always releases ``_reasoning_lock`` and clears ``_active_run_id`` — every
    caller must acquire the lock and set ``_active_run_id`` before invoking
    this function.
    """
    global _active_run_id
    try:
        log.info("Run %s: reasoning over detections (id>%s, id<=%s)...", run_id, min_id, max_id)
        result = run_pipeline(
            config_path=config_path or _CONFIG_PATH,
            prompts_dir=prompts_dir or _PROMPTS_DIR,
            min_id=min_id,
            max_id=max_id,
        )
        if pipeline_status is not None:
            result["pipeline_status"] = pipeline_status
        _runs[run_id] = {"status": "completed", "phase": "completed", "result": result}
        log.info("Run %s completed", run_id)
    except Exception as exc:
        log.error("Run %s failed: %s", run_id, exc)
        _runs[run_id] = {"status": "error", "phase": "error", "result": {"error": str(exc)}}
    finally:
        _active_run_id = None
        _reasoning_lock.release()
