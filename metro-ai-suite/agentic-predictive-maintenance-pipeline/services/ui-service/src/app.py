# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""UI service — FastAPI web application for the agentic predictive maintenance blueprint."""

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

_AGENT_URL   = os.environ.get("AGENT_SERVICE_URL",   "http://apm-agent:5002")
_STORAGE_URL = os.environ.get("STORAGE_SERVICE_URL", "http://apm-storage:5001")
_USE_CASE_ID = os.environ.get("USE_CASE_ID",         "unknown")
_TIMEOUT     = 15.0
_API_KEY     = os.environ.get("APM_API_KEY", "")
_SERVICE_HEADERS = {"X-API-Key": _API_KEY} if _API_KEY else {}

app = FastAPI(title="APM UI", docs_url=None, redoc_url=None)

_src_dir = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(_src_dir, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(_src_dir, "templates"))


# ── Pages ─────────────────────────────────────────────────────────────────────

async def _fetch_summary_and_runs(client: httpx.AsyncClient):
    try:
        summary_r = await client.get(f"{_STORAGE_URL}/detections/summary", headers=_SERVICE_HEADERS)
        summary = summary_r.json() if summary_r.status_code == 200 else {}
    except Exception:
        summary = {}

    try:
        runs_r = await client.get(f"{_AGENT_URL}/agents/runs", headers=_SERVICE_HEADERS)
        runs = runs_r.json() if runs_r.status_code == 200 else []
    except Exception:
        runs = []

    return summary, runs


async def _fetch_videos(client: httpx.AsyncClient):
    try:
        r = await client.get(f"{_AGENT_URL}/agents/videos", headers=_SERVICE_HEADERS)
        return r.json().get("videos", []) if r.status_code == 200 else []
    except Exception:
        return []


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
            r = await client.get(f"{_STORAGE_URL}/detections", params=params, headers=_SERVICE_HEADERS)
            detections = r.json() if r.status_code == 200 else []
        except Exception:
            detections = []

        try:
            summary_r = await client.get(f"{_STORAGE_URL}/detections/summary", headers=_SERVICE_HEADERS)
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
        try:
            status_r = await client.get(f"{_AGENT_URL}/agents/status/{run_id}", headers=_SERVICE_HEADERS)
            phase = status_r.json().get("phase") if status_r.status_code == 200 else None
        except Exception:
            phase = None

        try:
            r = await client.get(f"{_AGENT_URL}/agents/results/{run_id}", headers=_SERVICE_HEADERS)
            if r.status_code == 404:
                raise HTTPException(status_code=404, detail="Run not found")
            result = r.json() if r.status_code == 200 else {"status": "running"}
        except HTTPException:
            raise
        except Exception as exc:
            result = {"error": str(exc)}

    return templates.TemplateResponse(
        request=request, name="results.html",
        context={"use_case_id": _USE_CASE_ID, "run_id": run_id, "result": result, "phase": phase},
    )


# ── Actions ───────────────────────────────────────────────────────────────────

@app.post("/run")
async def trigger_run(
    device: str = Form("CPU"),
    video_filename: str = Form(""),
):
    """Trigger a new detect-then-reason pipeline run via the agent-service.

    If a run is already in progress, redirect to its results page instead of
    erroring — only one detect-then-reason cycle can run at a time.
    """
    payload: dict = {"device": device}
    if video_filename:
        payload["video_filename"] = video_filename

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(f"{_AGENT_URL}/agents/run", json=payload, headers=_SERVICE_HEADERS)
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
        await client.delete(f"{_STORAGE_URL}/detections", headers=_SERVICE_HEADERS)
    return RedirectResponse(url="/", status_code=303)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "ui-service", "use_case_id": _USE_CASE_ID}
