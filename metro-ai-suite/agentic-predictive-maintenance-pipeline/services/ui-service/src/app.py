# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""UI service — FastAPI web application for the agentic predictive maintenance blueprint.

Talks to the detection layer and the agent (reasoning) layer as two
independent backends, correlated only by a shared ``run_id``:

  * ``detection-service`` — owns starting/polling the detection run
    (device/video selection) and reports a "detecting"/"completed"/"error"
    phase for that half of the run.
  * ``agent-service`` — reacts to the detection layer's "batch-complete"
    MQTT event on its own and reports a "reasoning"/"completed"/"error"
    phase once it picks up the corresponding run_id.

This module merges the two into the single ``status``/``phase``/``result``
shape the templates and ``live-status.js`` already expect, so no detection-
vs-reasoning plumbing needs to leak into the UI layer itself.
"""

import logging
import os
from typing import Optional

import httpx
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

_AGENT_URL     = os.environ.get("AGENT_SERVICE_URL",     "http://apm-agent:5002")
_DETECTION_URL = os.environ.get("DETECTION_SERVICE_URL", "http://apm-detection:5004")
_STORAGE_URL   = os.environ.get("STORAGE_SERVICE_URL",   "http://apm-storage:5001")
_USE_CASE_ID   = os.environ.get("USE_CASE_ID",           "unknown")
_TIMEOUT       = 15.0

app = FastAPI(title="APM UI", docs_url=None, redoc_url=None)

_src_dir = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(_src_dir, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(_src_dir, "templates"))


# ── Run merging helpers ────────────────────────────────────────────────────────

def _merge_runs(det_runs: list[dict], agent_runs: list[dict]) -> list[dict]:
    """Merge the detection layer's run list with the agent layer's run list.

    The detection-service is the canonical source of run existence/order
    (every run starts there); the agent-service only knows about runs whose
    detection phase already completed and whose batch-complete event it has
    processed. Returns a list shaped like ``{"run_id", "status", "phase"}``,
    matching what the templates and live-status.js already expect.
    """
    agent_by_id = {r["run_id"]: r for r in agent_runs}
    merged = []
    for det in det_runs:
        run_id = det["run_id"]
        det_phase = det.get("phase")
        if det_phase == "detecting":
            merged.append({"run_id": run_id, "status": "running", "phase": "detecting"})
        elif det_phase == "error":
            merged.append({"run_id": run_id, "status": "error", "phase": "error"})
        else:  # detection completed -> reasoning phase owned by agent-service
            agent = agent_by_id.get(run_id)
            if agent is None:
                merged.append({"run_id": run_id, "status": "running", "phase": "reasoning"})
            else:
                merged.append({"run_id": run_id, "status": agent["status"], "phase": agent.get("phase")})
    return merged


async def _fetch_summary_and_runs(client: httpx.AsyncClient):
    try:
        summary_r = await client.get(f"{_STORAGE_URL}/detections/summary")
        summary = summary_r.json() if summary_r.status_code == 200 else {}
    except Exception:
        summary = {}

    try:
        det_r = await client.get(f"{_DETECTION_URL}/detection/runs")
        det_runs = det_r.json() if det_r.status_code == 200 else []
    except Exception:
        det_runs = []

    try:
        agent_r = await client.get(f"{_AGENT_URL}/agents/runs")
        agent_runs = agent_r.json() if agent_r.status_code == 200 else []
    except Exception:
        agent_runs = []

    runs = _merge_runs(det_runs, agent_runs)
    return summary, runs


async def _fetch_videos(client: httpx.AsyncClient):
    try:
        r = await client.get(f"{_DETECTION_URL}/detection/videos")
        return r.json().get("videos", []) if r.status_code == 200 else []
    except Exception:
        return []


async def _fetch_run_view(client: httpx.AsyncClient, run_id: str) -> dict:
    """Return the merged ``{"phase", "result"}`` view of one run for the results page."""
    det_r = await client.get(f"{_DETECTION_URL}/detection/status/{run_id}")
    if det_r.status_code == 404:
        raise HTTPException(status_code=404, detail="Run not found")
    det = det_r.json() if det_r.status_code == 200 else {}
    det_phase = det.get("phase")

    if det_phase == "detecting":
        return {"phase": "detecting", "result": {"status": "running"}}

    if det_phase == "error":
        error = (det.get("result") or {}).get("error", "Detection run failed")
        return {"phase": "error", "result": {"status": "error", "error": error}}

    # Detection completed — reasoning is owned by the agent-service from here.
    try:
        status_r = await client.get(f"{_AGENT_URL}/agents/status/{run_id}")
    except Exception:
        status_r = None

    if status_r is None or status_r.status_code == 404:
        # batch-complete event not yet processed by the agent-service
        return {"phase": "reasoning", "result": {"status": "running"}}

    agent_status = status_r.json()
    if agent_status.get("status") == "running":
        return {"phase": agent_status.get("phase", "reasoning"), "result": {"status": "running"}}

    try:
        results_r = await client.get(f"{_AGENT_URL}/agents/results/{run_id}")
        result = results_r.json() if results_r.status_code == 200 else {"error": "Result unavailable"}
    except Exception as exc:
        result = {"error": str(exc)}

    return {"phase": agent_status.get("phase"), "result": result}


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        summary, runs = await _fetch_summary_and_runs(client)
        videos = await _fetch_videos(client)

    active_run = next((r for r in reversed(runs) if r.get("status") == "running"), None)

    return templates.TemplateResponse(
        request=request, name="index.html",
        context={
            "use_case_id": _USE_CASE_ID,
            "summary": summary,
            "runs": runs,
            "active_run": active_run,
            "videos": videos,
            "devices": ["CPU", "GPU", "NPU"],
        },
    )


@app.get("/api/status")
async def api_status():
    """Lightweight JSON snapshot used by the dashboard to poll live pipeline status
    (detection counts + agent run counts) without a full page reload."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        summary, runs = await _fetch_summary_and_runs(client)

    by_class = summary.get("by_class", [])
    total_detections = sum(c.get("count", 0) for c in by_class)
    completed = sum(1 for r in runs if r.get("status") == "completed")
    running = sum(1 for r in runs if r.get("status") == "running")
    failed = sum(1 for r in runs if r.get("status") == "error")
    active_run = next((r for r in reversed(runs) if r.get("status") == "running"), None)

    return {
        "total_detections": total_detections,
        "by_class": by_class,
        "runs_total": len(runs),
        "runs_completed": completed,
        "runs_running": running,
        "runs_failed": failed,
        "active_run": active_run,
        "recent_runs": list(reversed(runs))[:10],
    }


@app.get("/detections", response_class=HTMLResponse)
async def detections_page(
    request: Request,
    label: Optional[str] = None,
    min_confidence: Optional[str] = None,
    limit: int = 100,
):
    # Treat empty string from form submission as no filter
    parsed_confidence: Optional[float] = None
    if min_confidence:
        try:
            parsed_confidence = float(min_confidence)
        except ValueError:
            pass

    params: dict = {"limit": limit}
    if label:
        params["label"] = label
    if parsed_confidence is not None:
        params["min_confidence"] = parsed_confidence

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            r = await client.get(f"{_STORAGE_URL}/detections", params=params)
            detections = r.json() if r.status_code == 200 else []
        except Exception:
            detections = []

        try:
            summary_r = await client.get(f"{_STORAGE_URL}/detections/summary")
            summary = summary_r.json() if summary_r.status_code == 200 else {}
            total_count = sum(c.get("count", 0) for c in summary.get("by_class", []))
        except Exception:
            total_count = None

    return templates.TemplateResponse(
        request=request, name="detections.html",
        context={
            "use_case_id": _USE_CASE_ID,
            "detections": detections,
            "filter_label": label or "",
            "filter_confidence": parsed_confidence if parsed_confidence is not None else "",
            "filter_limit": limit,
            "total_count": total_count,
        },
    )


@app.get("/results/{run_id}", response_class=HTMLResponse)
async def results_page(request: Request, run_id: str):
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        view = await _fetch_run_view(client, run_id)

    return templates.TemplateResponse(
        request=request, name="results.html",
        context={
            "use_case_id": _USE_CASE_ID, "run_id": run_id,
            "result": view["result"], "phase": view["phase"],
        },
    )


# ── Actions ───────────────────────────────────────────────────────────────────

@app.post("/run")
async def trigger_run(
    device: str = Form("CPU"),
    video_filename: str = Form(""),
):
    """Trigger a new detect-then-reason run by starting the detection layer.

    The agent-service reasons on its own once it observes the resulting
    "batch-complete" MQTT event — this endpoint never calls the agent-service.
    If a detection run is already in progress, redirect to its results page
    instead of erroring — only one run can be in flight at a time.
    """
    payload: dict = {"device": device}
    if video_filename:
        payload["video_filename"] = video_filename

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(f"{_DETECTION_URL}/detection/run", json=payload)
        if r.status_code == 409:
            active_run_id = (r.json().get("detail") or {}).get("run_id")
            if active_run_id:
                return RedirectResponse(url=f"/results/{active_run_id}", status_code=303)
            return RedirectResponse(url="/", status_code=303)
        r.raise_for_status()
        data = r.json()
    return RedirectResponse(url=f"/results/{data['run_id']}", status_code=303)


@app.post("/clear-detections")
async def clear_detections():
    """Clear all detections from storage."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        await client.delete(f"{_STORAGE_URL}/detections")
    return RedirectResponse(url="/", status_code=303)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "ui-service", "use_case_id": _USE_CASE_ID}
