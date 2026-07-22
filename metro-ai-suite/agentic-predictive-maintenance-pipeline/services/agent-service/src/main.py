# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""FastAPI entry point for the agent-service."""

import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from .meta_agent import run_pipeline
from .mqtt_subscriber import start_subscriber
from .utility import storage_client
from .utility.dlstreamer_client import (
    run_pipeline_to_completion,
    list_available_videos,
    PipelineRunError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger(__name__)

# In-memory run store (keyed by run_id). Each run tracks a "phase" so the UI
# can show real progress across the two-stage detect-then-reason cycle:
#   "detecting" -> "reasoning" -> "completed" / "error"
_runs: dict[str, dict] = {}

_CONFIG_PATH  = os.environ.get("AGENTS_CONFIG_PATH", None)
_PROMPTS_DIR  = os.environ.get("USE_CASE_PROMPTS_DIR", None)
_DETECTION_TIMEOUT = float(os.environ.get("DLSTREAMER_RUN_TIMEOUT", "600"))
_APM_API_KEY = os.environ.get("APM_API_KEY", "")

# Only one detect-then-reason cycle may run at a time (single shared DL Streamer
# pipeline + shared LLM/OVMS backend). New /agents/run calls are rejected with
# 409 while a run is already in flight.
_run_lock = threading.Lock()
_active_run_id: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start MQTT subscriber (non-blocking background thread) so detection
    # events are persisted to storage whenever the DL Streamer pipeline runs.
    if os.environ.get("MQTT_DISABLED", "false").lower() != "true":
        start_subscriber()
    yield


app = FastAPI(
    title="APM Agent Service",
    description="Agentic Predictive Maintenance — multi-agent orchestration service",
    version="1.0.0",
    lifespan=lifespan,
)


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Enforce API key auth for control-plane endpoints."""
    if not _APM_API_KEY:
        return
    if x_api_key != _APM_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ── Request / Response models ─────────────────────────────────────────────────

class RunRequest(BaseModel):
    config_path: Optional[str] = None
    prompts_dir: Optional[str] = None
    device: Optional[str] = "CPU"
    video_filename: Optional[str] = None


class RunResponse(BaseModel):
    run_id: str
    status: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/agents/run", response_model=RunResponse, status_code=202)
async def trigger_run(
    req: RunRequest,
    background_tasks: BackgroundTasks,
    _auth: None = Depends(require_api_key),
):
    """Trigger one full detect-then-reason cycle (async background task).

    Mirrors the reference CLI: starts the DL Streamer pipeline, waits for it to
    finish processing the source video, then runs the 4-agent pipeline bounded
    to exactly the detections produced by this run. Rejects a new run with 409
    while one is already in flight.
    """
    global _active_run_id
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail={"message": "A run is already in progress", "run_id": _active_run_id},
        )

    device = (req.device or "CPU").upper()
    if device not in {"CPU", "GPU", "NPU"}:
        _run_lock.release()
        raise HTTPException(status_code=422, detail=f"Unsupported device: {req.device!r}")

    run_id = str(uuid.uuid4())
    _active_run_id = run_id
    _runs[run_id] = {"status": "running", "phase": "detecting", "result": None}
    background_tasks.add_task(
        _execute_detect_and_reason_run,
        run_id,
        req.config_path,
        req.prompts_dir,
        device,
        req.video_filename,
    )
    return RunResponse(run_id=run_id, status="running")


@app.get("/agents/status/{run_id}")
def get_status(run_id: str):
    """Return the status (and current phase) of a pipeline run."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    run = _runs[run_id]
    return {"run_id": run_id, "status": run["status"], "phase": run.get("phase")}


@app.get("/agents/results/{run_id}")
def get_results(run_id: str):
    """Return the results of a completed pipeline run."""
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


@app.get("/agents/videos")
def get_available_videos():
    """List video filenames available under the shared resources/videos directory."""
    return {"videos": list_available_videos()}


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

def _execute_detect_and_reason_run(
    run_id: str,
    config_path: str | None,
    prompts_dir: str | None,
    device: str = "CPU",
    video_filename: str | None = None,
):
    """Run one full detect-then-reason cycle for ``run_id``.

    1. Bookmark the current max detection id (start_id).
    2. Start the DL Streamer pipeline (on ``device``, optionally overriding the
       source video with ``video_filename``) and block until it finishes
       (COMPLETED/ERROR).
    3. Bookmark the max detection id again (end_id).
    4. Run the 4-agent pipeline bounded to (start_id, end_id] — exactly the
       detections produced by this run, regardless of any earlier history.
    """
    global _active_run_id
    try:
        try:
            start_id = storage_client.get_max_id().get("max_id", 0)
        except Exception as exc:
            log.warning("Could not resolve starting detection watermark, defaulting to 0: %s", exc)
            start_id = 0

        _runs[run_id]["phase"] = "detecting"
        log.info(
            "Run %s: starting DL Streamer pipeline (device=%s, video=%s, from detection id %d)...",
            run_id, device, video_filename or "<default>", start_id,
        )
        pipeline_status = run_pipeline_to_completion(
            device=device, video_filename=video_filename, timeout=_DETECTION_TIMEOUT
        )
        log.info("Run %s: detection finished (%s)", run_id, pipeline_status)

        try:
            end_id = storage_client.get_max_id().get("max_id", start_id)
        except Exception as exc:
            log.warning("Could not resolve ending detection watermark, defaulting to no upper bound: %s", exc)
            end_id = None

        _runs[run_id]["phase"] = "reasoning"
        log.info("Run %s: reasoning over detections (id>%s, id<=%s)...", run_id, start_id, end_id)
        result = run_pipeline(
            config_path=config_path or _CONFIG_PATH,
            prompts_dir=prompts_dir or _PROMPTS_DIR,
            min_id=start_id,
            max_id=end_id,
        )
        result["pipeline_status"] = pipeline_status
        _runs[run_id] = {"status": "completed", "phase": "completed", "result": result}
        log.info("Run %s completed", run_id)

    except PipelineRunError as exc:
        log.error("Run %s failed during detection: %s", run_id, exc)
        _runs[run_id] = {"status": "error", "phase": "error", "result": {"error": str(exc)}}
    except Exception as exc:
        log.error("Run %s failed: %s", run_id, exc)
        _runs[run_id] = {"status": "error", "phase": "error", "result": {"error": str(exc)}}
    finally:
        _active_run_id = None
        _run_lock.release()
