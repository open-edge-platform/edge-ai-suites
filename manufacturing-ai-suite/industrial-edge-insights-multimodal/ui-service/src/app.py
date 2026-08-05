# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""UI service — FastAPI web application for the Agentic Weld Quality Analysis blueprint.

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
import time
import uuid
import json
import threading
from typing import Optional

import httpx
import paho.mqtt.client as mqtt
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import PlainTextResponse

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

_AGENT_URL     = os.environ.get("AGENT_SERVICE_URL",     "http://apm-agent:5002")
_DETECTION_URL = os.environ.get("DETECTION_SERVICE_URL", "http://apm-detection:5004")
_STORAGE_URL   = os.environ.get("STORAGE_SERVICE_URL",   "http://ia-fusion-analytics:8080")
_USE_CASE_ID   = os.environ.get("USE_CASE_ID",           "unknown")
_TIMEOUT       = 15.0
_MQTT_HOST     = os.environ.get("MQTT_HOST",             "ia-mqtt-broker")
_MQTT_PORT     = int(os.environ.get("MQTT_PORT",         "1883"))
_MQTT_TOPIC    = os.environ.get("MQTT_BATCH_TOPIC",      "apm/batch-complete")
_MQTT_QOS      = int(os.environ.get("MQTT_QOS",          "1"))
_MQTT_KEEPALIVE = int(os.environ.get("MQTT_KEEPALIVE",   "60"))
_MQTT_CLIENT_ID = os.environ.get("MQTT_CLIENT_ID",       "apm-ui-service")
_MQTT_DISABLED = os.environ.get("MQTT_DISABLED",         "false").lower() == "true"


_start_time = time.time()
_request_count = 0

REST_API_ROOT_PATH = os.getenv('REST_API_ROOT_PATH', '')
app = FastAPI(
    title="APM UI",
    docs_url=None,
    redoc_url=None,
    root_path=REST_API_ROOT_PATH
)

_src_dir = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(_src_dir, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(_src_dir, "templates"))

_mqtt_client: Optional[mqtt.Client] = None
_mqtt_connected = threading.Event()


def _on_mqtt_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        _mqtt_connected.set()
        log.info("MQTT connected to %s:%s", _MQTT_HOST, _MQTT_PORT)
    else:
        _mqtt_connected.clear()
        log.error("MQTT connect failed (reason_code=%s)", reason_code)


def _on_mqtt_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    _mqtt_connected.clear()
    log.warning("MQTT disconnected (reason_code=%s)", reason_code)


@app.on_event("startup")
def _startup_mqtt_connection() -> None:
    """Initialize MQTT connection during app startup for publish reuse."""
    global _mqtt_client

    if _MQTT_DISABLED:
        log.info("MQTT startup connect skipped because MQTT_DISABLED=true")
        return

    _mqtt_client = None
    _mqtt_connected.clear()

    max_attempts = 60
    retry_delay_s = 5

    for attempt in range(1, max_attempts + 1):
        client: Optional[mqtt.Client] = None
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=_MQTT_CLIENT_ID)
            client.on_connect = _on_mqtt_connect
            client.on_disconnect = _on_mqtt_disconnect
            client.connect(_MQTT_HOST, _MQTT_PORT, _MQTT_KEEPALIVE)
            client.loop_start()

            if _mqtt_connected.wait(timeout=retry_delay_s):
                _mqtt_client = client
                log.info("MQTT client initialized on attempt %s/%s", attempt, max_attempts)
                return

            log.warning(
                "MQTT connect attempt %s/%s timed out after %ss",
                attempt,
                max_attempts,
                retry_delay_s,
            )
        except Exception:
            log.exception("MQTT startup attempt %s/%s failed", attempt, max_attempts)
        finally:
            # Ensure failed attempts don't leave a background network loop running.
            if client is not None and _mqtt_client is None:
                try:
                    client.loop_stop()
                    client.disconnect()
                except Exception:
                    log.debug("Ignoring MQTT client cleanup error on failed startup attempt")

        if attempt < max_attempts:
            time.sleep(retry_delay_s)

    log.error("Failed to initialize MQTT client after %s attempts", max_attempts)


@app.on_event("shutdown")
def _shutdown_mqtt_connection() -> None:
    """Close MQTT connection on app shutdown."""
    global _mqtt_client

    if _mqtt_client is None:
        return

    try:
        _mqtt_client.loop_stop()
        _mqtt_client.disconnect()
    except Exception:
        log.exception("Error while shutting down MQTT client")
    finally:
        _mqtt_client = None
        _mqtt_connected.clear()


def _time_range_to_ns(time_range: str) -> int:
    """Convert compact time ranges like '30s', '1m', '5m', '10m', '30m' to ns."""
    units = {
        "s": 1_000_000_000,
        "m": 60 * 1_000_000_000,
    }

    if not time_range:
        return 5 * units["m"]

    suffix = time_range[-1]
    if suffix not in units:
        raise HTTPException(status_code=400, detail=f"Unsupported time_range: {time_range}")

    try:
        value = int(time_range[:-1])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid time_range: {time_range}") from exc

    if value <= 0:
        raise HTTPException(status_code=400, detail=f"Invalid time_range: {time_range}")

    return value * units[suffix]


def _publish_batch_complete(payload: dict) -> None:
    """Publish one batch-complete event to MQTT for agent consumption."""
    if _MQTT_DISABLED:
        log.info("MQTT publish skipped because MQTT_DISABLED=true")
        return

    if _mqtt_client is None:
        raise HTTPException(status_code=503, detail="MQTT client is not initialized")

    if not _mqtt_connected.is_set():
        raise HTTPException(status_code=503, detail="MQTT client is not connected")

    try:
        info = _mqtt_client.publish(
            topic=_MQTT_TOPIC,
            payload=json.dumps(payload, separators=(",", ":")),
            qos=_MQTT_QOS,
        )
        info.wait_for_publish(timeout=5)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"publish failed with rc={info.rc}")
        log.info("Published batch event to MQTT topic '%s'", _MQTT_TOPIC)
    except Exception as exc:
        log.exception("Failed to publish MQTT batch event")
        raise HTTPException(status_code=502, detail=f"Failed to publish MQTT batch event: {exc}") from exc


def _redirect_path(request: Request, route_name: str, **path_params: str) -> str:
    """Build a proxy-safe relative redirect path, preserving root_path and avoiding host/port issues."""
    root_path = request.scope.get("root_path", "")
    return f"{root_path}{app.url_path_for(route_name, **path_params)}"


# ── Run merging helpers ────────────────────────────────────────────────────────

def _merge_runs(agent_runs: list[dict]) -> list[dict]:
    """Merge the detection layer's run list with the agent layer's run list.

    The detection-service is the canonical source of run existence/order
    (every run starts there); the agent-service only knows about runs whose
    detection phase already completed and whose batch-complete event it has
    processed. Returns a list shaped like ``{"run_id", "status", "phase"}``,
    matching what the templates and live-status.js already expect.
    """
    # agent_by_id = {r["run_id"]: r for r in agent_runs}
    merged = []
    for run in agent_runs:
        run_id = run["run_id"]
        merged.append({"run_id": run_id, "status": run["status"], "phase": "reasoning" if run["status"] == "running" else "completed"})
    log.debug(f"Merged runs: {merged}")
    return merged


async def _fetch_summary_and_runs(client: httpx.AsyncClient):
    try:
        summary_r = await client.get(f"{_STORAGE_URL}/detections/summary")
        log.debug(f"Fetched summary from {_STORAGE_URL}/detections/summary: {summary_r.status_code} data: {summary_r.text}")
        summary = summary_r.json() if summary_r.status_code == 200 else {}
    except Exception:
        summary = {}

    try:
        agent_r = await client.get(f"{_AGENT_URL}/agents/runs")
        log.debug(f"Fetched agent runs from {_AGENT_URL}/agents/runs: {agent_r.status_code} data: {agent_r.text}")
        agent_runs = agent_r.json() if agent_r.status_code == 200 else []
    except Exception:
        agent_runs = []

    runs = _merge_runs(agent_runs)
    return summary, runs


async def _fetch_videos(client: httpx.AsyncClient):
    try:
        r = await client.get(f"{_DETECTION_URL}/detection/videos")
        return r.json().get("videos", []) if r.status_code == 200 else []
    except Exception:
        return []


async def _fetch_run_view(client: httpx.AsyncClient, run_id: str) -> dict:
    """Return the merged ``{"phase", "result"}`` view of one run for the results page."""
    try:
        results_r = await client.get(f"{_AGENT_URL}/agents/status/{run_id}")
        result = results_r.json() if results_r.status_code == 200 else {}
        phase = "completed" if result.get("status") == "completed" else "reasoning"
        if phase == "completed":
            results_r = await client.get(f"{_AGENT_URL}/agents/results/{run_id}")
            result = results_r.json() if results_r.status_code == 200 else {"error": "Result unavailable"}
    except Exception as exc:
        result = {"error": str(exc)}
        phase = "error"
    log.info(f"Fetched run view for run_id={run_id}: phase={phase}, result={result}")
    return {"phase": phase, "result": result}


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

    by_class = list(summary.values()) if summary else []
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
    request: Request,
    time_range: str = Form(""),
):
    """Trigger a new detect-then-reason run by starting the detection layer.

    The agent-service reasons on its own once it observes the resulting
    "batch-complete" MQTT event — this endpoint never calls the agent-service.
    If a detection run is already in progress, redirect to its results page
    instead of erroring — only one run can be in flight at a time.
    """
    payload: dict = {}
    if time_range:
        payload["time_range"] = time_range

    run_id = str(uuid.uuid4())
    log.info(f"Triggering new run with payload: {payload}")

    time_end = time.time_ns()
    time_start = time_end - _time_range_to_ns(time_range)
    trigger_payload = {
        "run_id": run_id,
        "status": "completed",
        "device": "dummy",
        "video_filename": "welding",
        "start_id": time_start,
        "end_id": time_end,
        "pipeline_status": "running",
    }
    log.info(f"Computed trigger payload: {trigger_payload}")
    _publish_batch_complete(trigger_payload)
    
    return RedirectResponse(url=_redirect_path(request, "results_page", run_id=run_id), status_code=303)
    # mosquitto_pub -h localhost -p 1883  -t "apm/batch-complete" -m '{"run_id":"1","status":"completed","device":"CPU","video_filename":"welding","start_id":1785384705037648000,"end_id":1785384706008029000,"pipeline_status":"running"}'

# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "ui-service", "use_case_id": _USE_CASE_ID}

@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    global _start_time, _request_count
    uptime = time.time() - _start_time
    count = 0
    return (
        f"# HELP apm_storage_detections_total Total detections stored\n"
        f"# TYPE apm_storage_detections_total gauge\n"
        f"apm_storage_detections_total {count}\n"
        f"# HELP apm_storage_requests_total Total HTTP requests handled\n"
        f"# TYPE apm_storage_requests_total counter\n"
        f"apm_storage_requests_total {_request_count}\n"
        f"# HELP apm_storage_uptime_seconds Service uptime in seconds\n"
        f"# TYPE apm_storage_uptime_seconds gauge\n"
        f"apm_storage_uptime_seconds {uptime:.1f}\n"
    )