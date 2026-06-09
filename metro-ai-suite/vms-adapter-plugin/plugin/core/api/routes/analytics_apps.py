# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Analytics App discovery + generic run-lifecycle API.

This router gives the UI a unified contract to:

* discover every Analytics App registered with the I/O plugin
  ``GET  /v1/analytics-apps/discover``
* fetch a Analytics App's parameter schema as JSON Schema
  ``GET  /v1/analytics-apps/{app_id}/schema``
* start / stop / list pipeline runs — **generic, works for any app_id**
  ``POST   /v1/analytics-apps/{app_id}/runs``
  ``GET    /v1/analytics-apps/{app_id}/runs``
  ``GET    /v1/analytics-apps/{app_id}/runs/{run_id}``
  ``DELETE /v1/analytics-apps/{app_id}/runs/{run_id}``
* stream live results (captions, detections, …) from the analytics app
  ``GET  /v1/analytics-apps/{app_id}/results/stream``
* fetch dynamic dropdown options (models, pipelines, …)
  ``GET  /v1/analytics-apps/{app_id}/options/{option_type}``

Adding a **new analytics app** requires only a new shim class implementing
``IAnalyticsAppShim`` — zero route changes needed here.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator, Optional

import httpx
import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from sqlalchemy.ext.asyncio import AsyncSession

from plugin.core.api.deps import get_analytics_app_shims, get_db_session, require_analytics_app_shim
from plugin.core.db import repository as repo
from plugin.base.interfaces import IAnalyticsAppShim

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/analytics-apps", tags=["Analytics Apps"])


# ── helpers ───────────────────────────────────────────────────────────────────

def _shim_descriptor(
    shim: IAnalyticsAppShim,
    available: bool,
    schema: dict | None,
    error: str | None = None,
) -> dict[str, Any]:
    """Serialise a shim into the discovery payload."""
    desc: dict[str, Any] = {
        "app_id": shim.app_id,
        "display_name": shim.display_name,
        "available": available,
        "params_schema": schema,
    }
    if error:
        desc["error"] = error
    return desc


def _require_shim(app_id: str) -> IAnalyticsAppShim:
    return require_analytics_app_shim(app_id)


# ── Discovery & schema ────────────────────────────────────────────────────────

@router.get("/discover")
async def discover_analytics_apps(
    shims: dict[str, IAnalyticsAppShim] = Depends(get_analytics_app_shims),
) -> list[dict[str, Any]]:
    """List every registered Analytics App with its live availability and schema.

    When a Analytics App is unreachable:
    - ``available`` is ``false``
    - ``params_schema`` is ``null``
    - ``error`` contains the reason (displayed in the UI)

    All shims are probed in parallel so discovery time equals the slowest
    single app, not the sum of all apps.
    """
    async def _probe(shim: IAnalyticsAppShim) -> dict[str, Any]:
        error_msg: str | None = None
        try:
            available = await shim.is_available()
        except Exception as exc:
            logger.warning("analytics_app_availability_check_failed", app_id=shim.app_id, error=str(exc))
            available = False
            error_msg = str(exc)

        schema: dict | None = None
        if available:
            try:
                schema = await shim.fetch_schema()
            except Exception as exc:
                logger.warning("analytics_app_fetch_schema_failed", app_id=shim.app_id, error=str(exc))
                schema = None
                error_msg = str(exc)
        else:
            if not error_msg:
                error_msg = f"{shim.display_name} backend is not reachable"

        logger.info(
            "analytics_app_discovered",
            app_id=shim.app_id,
            available=available,
            has_schema=schema is not None,
        )
        return _shim_descriptor(shim, available, schema, error_msg)

    results = await asyncio.gather(*[_probe(shim) for shim in shims.values()])
    return list(results)


@router.get("/{app_id}/schema")
async def get_analytics_app_schema(app_id: str) -> dict[str, Any]:
    """Return the live JSON Schema for a Analytics App's start parameters.

    Returns 503 if the schema has not been loaded yet (call GET /discover first).
    """
    shim = _require_shim(app_id)
    try:
        return await shim.fetch_schema()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ── Run lifecycle — POST / GET / DELETE /{app_id}/runs ────────────────────────

@router.post("/{app_id}/runs")
async def start_analytics_app_run(
    app_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Validate ``payload`` against the app's live Pydantic schema and start a run.

    Pre-validation transformations applied (in order):
    1. **Camera resolution** — camera_id values (``x-vms-source: "camera-id"``) are
       resolved to RTSP stream_urls via the camera DB.
    2. **Frame resolution** — the ``frameResolution`` dropdown value is converted to
       ``frameWidth`` / ``frameHeight`` integers (matching LVC's ``frameQualitySelect``
       logic) and then stripped from the payload.
    3. **Synthetic field removal** — any remaining synthetic fields are removed so
       Pydantic only validates the real LVC API fields.

    Returns 503 if the schema has not been loaded yet (call GET /discover first).
    Returns 422 with per-field errors if payload fails validation.
    Returns 502 if the analytics app backend returns an error.
    """
    shim = _require_shim(app_id)

    try:
        model = shim.param_model
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    resolved_payload = dict(payload)

    # 1. Resolve camera-id values → RTSP stream_urls
    camera_field_set = set(shim.camera_fields())
    for field_name in camera_field_set:
        cam_value = resolved_payload.get(field_name)
        if cam_value and isinstance(cam_value, str):
            camera = await repo.get_camera(db, cam_value)
            if camera and camera.stream_url:
                # Preserve original camera_id for shims that need it (e.g. OD MQTT topic)
                resolved_payload[f"{field_name}_ref"] = cam_value
                resolved_payload[field_name] = camera.stream_url
                logger.info(
                    "analytics_app_camera_resolved",
                    field=field_name,
                    camera_id=cam_value,
                )
            else:
                raise HTTPException(
                    status_code=422,
                    detail=f"Camera '{cam_value}' not found or has no stream URL",
                )

    # 2. Expand frameResolution dropdown → frameWidth / frameHeight (matches LVC UI logic)
    _FRAME_PRESETS: dict[str, tuple[int, int]] = {
        "1280x720": (1280, 720),
        "640x480":  (640, 480),
        "480x360":  (480, 360),
    }
    frame_res = resolved_payload.pop("frameResolution", None)
    if frame_res and frame_res != "default":
        preset = _FRAME_PRESETS.get(frame_res)
        if preset:
            resolved_payload["frameWidth"]  = preset[0]
            resolved_payload["frameHeight"] = preset[1]

    # 3. Remove any remaining synthetic/ui-only keys unknown to the Pydantic model
    # Preserve captionHistory before stripping — it's a UI display setting returned in result
    caption_history = resolved_payload.pop("captionHistory", 3)
    # Collect camera_id refs before stripping (used for Nx write-back after start).
    camera_id_for_run = ""
    for field_name in camera_field_set:
        camera_id_for_run = resolved_payload.get(f"{field_name}_ref", "") or ""
        if camera_id_for_run:
            break
    model_fields = set(model.model_fields.keys())
    for key in list(resolved_payload.keys()):
        if key not in model_fields:
            resolved_payload.pop(key)

    try:
        params = model.model_validate(resolved_payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    try:
        result = await shim.start(params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Register run→camera mapping for Nx Witness write-back (LVC only).
    run_id = result.get("runId", "")
    if run_id and camera_id_for_run and hasattr(shim, "register_run"):
        shim.register_run(run_id, camera_id_for_run)

    # Attach captionHistory so the UI knows how many captions to display
    result["captionHistory"] = caption_history
    return result


@router.get("/{app_id}/runs")
async def list_analytics_app_runs(app_id: str) -> list[dict[str, Any]]:
    """List all active runs for a analytics app."""
    shim = _require_shim(app_id)
    return await shim.list_runs()


@router.get("/{app_id}/runs/{run_id}")
async def get_analytics_app_run(app_id: str, run_id: str) -> dict[str, Any]:
    """Get details of a single run."""
    shim = _require_shim(app_id)
    run = await shim.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run


@router.delete("/{app_id}/runs/{run_id}", status_code=204, response_class=Response)
async def stop_analytics_app_run(app_id: str, run_id: str) -> Response:
    """Stop a running pipeline run."""
    shim = _require_shim(app_id)
    ok = await shim.stop_run(run_id)
    if not ok:
        raise HTTPException(status_code=502, detail=f"Failed to stop run '{run_id}'")
    return Response(status_code=204)


@router.post("/{app_id}/runs/stop-all", status_code=204, response_class=Response)
async def stop_all_analytics_app_runs(app_id: str) -> Response:
    """Stop every active run for a Analytics App.

    Called by the UI via ``navigator.sendBeacon`` on page unload/refresh so that
    pipelines are cleaned up automatically when the user leaves the dashboard.
    Returns 204 even if some stops fail (best-effort).
    """
    shim = _require_shim(app_id)
    runs = await shim.list_runs()
    for run in runs:
        run_id = run.get("runId") or run.get("run_id") or run.get("id", "")
        if not run_id:
            continue
        try:
            await shim.stop_run(run_id)
            logger.info("stop_all_run_stopped", app_id=app_id, run_id=run_id)
        except Exception as exc:
            logger.warning("stop_all_run_failed", app_id=app_id, run_id=run_id, error=str(exc))
    return Response(status_code=204)


# ── Results stream ────────────────────────────────────────────────────────────

@router.get("/{app_id}/results/stream")
async def stream_analytics_app_results(
    app_id: str,
    run_id: Optional[str] = Query(default=None, description="Filter results to a specific run ID"),
) -> StreamingResponse:
    """Stream live inference results (captions, detections, …) as Server-Sent Events.

    **Per-shim MQTT queue (preferred):** If the Analytics App shim owns an aiomqtt
    subscriber (e.g. LVC), results are served from the shim's per-run queue —
    no global MQTT client needed.

    **SSE proxy fallback:** If the shim has no queue the route proxies the Core
    App's own SSE endpoint (legacy behaviour).

    The ``run_id`` query parameter narrows the stream to a single run's results.
    Without it, all results for the app are broadcast (backwards-compatible).

    Returns 501 if the app does not support streaming at all.
    """
    shim = _require_shim(app_id)

    # ── Per-shim MQTT queue (aiomqtt subscriber, e.g. LVC) ───────────────────
    if run_id:
        queue: asyncio.Queue | None = shim.subscribe_run(run_id)
    else:
        queue = shim.get_broadcast_queue()

    if queue is not None:
        async def _mqtt_sse() -> AsyncIterator[bytes]:
            heartbeat_interval = 1.0
            last_heartbeat = time.monotonic()
            try:
                while True:
                    now = time.monotonic()
                    timeout = max(0.05, heartbeat_interval - (now - last_heartbeat))
                    try:
                        envelope = await asyncio.wait_for(queue.get(), timeout=timeout)
                        yield f"data: {json.dumps(envelope)}\n\n".encode()
                    except asyncio.TimeoutError:
                        heartbeat = json.dumps({"type": "heartbeat", "app_id": app_id})
                        yield f"data: {heartbeat}\n\n".encode()
                        last_heartbeat = time.monotonic()
            except asyncio.CancelledError:
                pass
            finally:
                if run_id:
                    shim.release_run(run_id)

        return StreamingResponse(
            _mqtt_sse(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # ── SSE proxy fallback ───────────────────────────────────────────────────
    try:
        sse_url = await shim.results_stream_url()
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc

    async def _proxy() -> AsyncIterator[bytes]:
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream("GET", sse_url) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except httpx.HTTPError as exc:
                logger.error("analytics_app_sse_proxy_error", app_id=app_id, error=str(exc))
                yield b'data: {"error": "stream disconnected"}\n\n'

    return StreamingResponse(
        _proxy(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Options (dynamic dropdowns) ───────────────────────────────────────────────

@router.get("/{app_id}/options/{option_type}")
async def get_analytics_app_options(app_id: str, option_type: str) -> list[Any]:
    """Return a list of options for a named dropdown (e.g. 'models', 'pipelines').

    Each analytics app shim implements ``get_options(option_type)`` and returns
    a list of strings or ``{label, value}`` objects.
    Returns an empty list for unknown option types.
    """
    shim = _require_shim(app_id)
    return await shim.get_options(option_type)
