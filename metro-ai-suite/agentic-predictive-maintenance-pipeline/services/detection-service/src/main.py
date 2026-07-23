# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""FastAPI entry point for the detection-service.

Owns the entire detection lifecycle, independent of the agent/reasoning
layer: starting and polling the DL Streamer pipeline, subscribing to raw
detection events over MQTT and persisting them to the storage-service, and
publishing a "batch-complete" event once a run finishes so the (detection-
agnostic) agent-service can react without ever calling back into this
service.
"""

import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

from .mqtt_publisher import publish_batch_complete
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

# In-memory run store (keyed by run_id). Tracks only the detection half of a
# run: "detecting" -> "completed" / "error". The agent-service maintains its
# own store for the reasoning half, correlated by the same run_id.
_runs: dict[str, dict] = {}

_DETECTION_TIMEOUT = float(os.environ.get("DLSTREAMER_RUN_TIMEOUT", "600"))

# Only one detection run may be in flight at a time (single shared DL Streamer
# pipeline). New /detection/run calls are rejected with 409 while one is
# already running.
_run_lock = threading.Lock()
_active_run_id: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start MQTT subscriber (non-blocking background thread) so raw detection
    # events are persisted to storage whenever the DL Streamer pipeline runs.
    if os.environ.get("MQTT_DISABLED", "false").lower() != "true":
        start_subscriber()
    yield


app = FastAPI(
    title="APM Detection Service",
    description="Agentic Predictive Maintenance — detection layer (DL Streamer orchestration)",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Request / Response models ─────────────────────────────────────────────────

class DetectionRunRequest(BaseModel):
    device: Optional[str] = "CPU"
    video_filename: Optional[str] = None


class DetectionRunResponse(BaseModel):
    run_id: str
    status: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/detection/run", response_model=DetectionRunResponse, status_code=202)
async def trigger_detection_run(req: DetectionRunRequest, background_tasks: BackgroundTasks):
    """Start one bounded DL Streamer run in the background.

    On completion (successful or not), publishes a "batch-complete" MQTT event
    so the agent-service can react — this endpoint never calls the agent-service
    directly. Rejects a new run with 409 while one is already in flight.
    """
    global _active_run_id
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail={"message": "A detection run is already in progress", "run_id": _active_run_id},
        )

    device = (req.device or "CPU").upper()
    if device not in {"CPU", "GPU", "NPU"}:
        _run_lock.release()
        raise HTTPException(status_code=422, detail=f"Unsupported device: {req.device!r}")

    run_id = str(uuid.uuid4())
    _active_run_id = run_id
    _runs[run_id] = {"status": "running", "phase": "detecting", "result": None}
    background_tasks.add_task(_execute_detection_run, run_id, device, req.video_filename)
    return DetectionRunResponse(run_id=run_id, status="running")


@app.get("/detection/status/{run_id}")
def get_status(run_id: str):
    """Return the status, phase, and (once known) result of a detection run."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, **_runs[run_id]}


@app.get("/detection/runs")
def list_runs():
    """List all detection runs with their status/phase."""
    return [{"run_id": k, **v} for k, v in _runs.items()]


@app.get("/detection/videos")
def get_available_videos():
    """List video filenames available under the shared resources/videos directory."""
    return {"videos": list_available_videos()}


@app.get("/health")
def health():
    return {"status": "ok", "service": "detection-service", "run_count": len(_runs)}


@app.get("/metrics")
def metrics():
    total   = len(_runs)
    done    = sum(1 for r in _runs.values() if r["status"] == "completed")
    failed  = sum(1 for r in _runs.values() if r["status"] == "error")
    running = sum(1 for r in _runs.values() if r["status"] == "running")
    lines = [
        "# HELP apm_detection_runs_total Total detection runs",
        "# TYPE apm_detection_runs_total counter",
        f"apm_detection_runs_total {total}",
        "# HELP apm_detection_runs_completed Completed detection runs",
        "# TYPE apm_detection_runs_completed counter",
        f"apm_detection_runs_completed {done}",
        "# HELP apm_detection_runs_failed Failed detection runs",
        "# TYPE apm_detection_runs_failed counter",
        f"apm_detection_runs_failed {failed}",
        "# HELP apm_detection_runs_running Currently running detection runs",
        "# TYPE apm_detection_runs_running gauge",
        f"apm_detection_runs_running {running}",
    ]
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _execute_detection_run(run_id: str, device: str, video_filename: str | None):
    """Run one bounded DL Streamer detection run for ``run_id``.

    1. Bookmark the current max detection id (start_id).
    2. Start the DL Streamer pipeline (on ``device``, optionally overriding the
       source video with ``video_filename``) and block until it finishes.
    3. Bookmark the max detection id again (end_id).
    4. Publish a "batch-complete" MQTT event describing the outcome — this is
       the only handoff to the agent-service; this service never calls it.
    """
    global _active_run_id
    try:
        try:
            start_id = storage_client.get_max_id().get("max_id", 0)
        except Exception as exc:
            log.warning("Could not resolve starting detection watermark, defaulting to 0: %s", exc)
            start_id = 0

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

        result = {"pipeline_status": pipeline_status, "start_id": start_id, "end_id": end_id}
        _runs[run_id] = {"status": "completed", "phase": "completed", "result": result}
        publish_batch_complete({
            "run_id": run_id, "status": "completed", "device": device,
            "video_filename": video_filename, "start_id": start_id, "end_id": end_id,
            "pipeline_status": pipeline_status,
        })
        log.info("Run %s: detection completed", run_id)

    except PipelineRunError as exc:
        log.error("Run %s failed during detection: %s", run_id, exc)
        _runs[run_id] = {"status": "error", "phase": "error", "result": {"error": str(exc)}}
        publish_batch_complete({
            "run_id": run_id, "status": "error", "device": device,
            "video_filename": video_filename, "start_id": start_id, "end_id": None,
            "error": str(exc),
        })
    except Exception as exc:
        log.error("Run %s failed: %s", run_id, exc)
        _runs[run_id] = {"status": "error", "phase": "error", "result": {"error": str(exc)}}
        publish_batch_complete({
            "run_id": run_id, "status": "error", "device": device,
            "video_filename": video_filename, "start_id": None, "end_id": None,
            "error": str(exc),
        })
    finally:
        _active_run_id = None
        _run_lock.release()
