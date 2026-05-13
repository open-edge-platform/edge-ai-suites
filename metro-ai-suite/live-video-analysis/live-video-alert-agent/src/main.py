# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional

import cv2
import psutil
from fastapi import Body, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from src.core.agent_manager import AgentManager
from src.config import settings, setup_logging
from src.schemas.api import (
    HealthResponse,
    StreamAddRequest,
    StreamPatchRequest,
    StreamResponse,
    StreamStatus,
    SystemMetrics,
    ToolInvokeRequest,
    ToolInvokeResponse,
)
from src.schemas.monitor import AlertConfig
from src.agentic.mcp_client import (
    initialize_mcp_servers,
    shutdown_mcp_servers,
    get_mcp_server_status,
    get_mcp_tools,
)

setup_logging()
logger = logging.getLogger(__name__)

_startup_time: float = time.monotonic()

manager: Optional[AgentManager] = None
_manager_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global manager, _manager_task

    logger.info(
        f"Starting Live Video Alert Agent | VLM={settings.VLM_URL} "
        f"model={settings.MODEL_NAME} ADK={'on' if settings.USE_ADK else 'off'}"
    )

    # Initialize MCP servers if enabled
    mcp_tools = []
    mcp_schemas = []
    if settings.MCP_ENABLED:
        logger.info("Initializing MCP servers...")
        mcp_tools, mcp_schemas = await initialize_mcp_servers()
        if mcp_tools:
            # Register MCP tools with the alert agent
            from src.agentic import register_mcp_tools
            register_mcp_tools(mcp_tools, mcp_schemas)
        logger.info(f"MCP initialization complete: {len(mcp_tools)} tool(s) available")

    manager = AgentManager(
        vlm_url=settings.VLM_URL,
        model_name=settings.MODEL_NAME,
    )

    # If MCP tools were registered, augment alert configs and reinit ADK
    # so the agent prompt and tool list include MCP server details and tools.
    if settings.MCP_ENABLED and mcp_tools:
        manager.augment_alerts_with_mcp_tools()
        if settings.USE_ADK:
            manager.action_agent.reinit_adk()

    if settings.RTSP_URL:
        manager.add_stream("default", settings.RTSP_URL)

    # manager.start() keeps an internal keep-alive loop; wrap in a Task
    # and store a reference so we can handle its exceptions
    _manager_task = asyncio.create_task(manager.start(), name="manager-main")

    def _on_manager_done(t: asyncio.Task):
        if not t.cancelled() and t.exception():
            logger.critical(f"AgentManager crashed: {t.exception()}")

    _manager_task.add_done_callback(_on_manager_done)

    yield

    # Graceful shutdown
    logger.info("Shutting down ...")
    
    # Shutdown MCP servers and clear tools from alert agent
    if settings.MCP_ENABLED:
        logger.info("Shutting down MCP servers...")
        from src.agentic import clear_mcp_tools
        clear_mcp_tools()
        await shutdown_mcp_servers()
    
    if manager:
        manager.stop()
    if _manager_task and not _manager_task.done():
        _manager_task.cancel()
        try:
            await asyncio.wait_for(_manager_task, timeout=5)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass


app = FastAPI(
    title="Live Video Alert Agent",
    description=(
        "Real-time multi-camera alert detection powered by OpenVINO VLM "
        "and a Google ADK action agent."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "static")
if os.path.exists(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


def _require_manager() -> AgentManager:
    if manager is None:
        raise HTTPException(status_code=503, detail="Manager not initialised")
    return manager


@app.get("/health", response_model=HealthResponse, tags=["Observability"])
async def health():
    """Liveness probe — always returns 200 if the process is alive."""
    mgr = manager
    return HealthResponse(
        status="healthy",
        streams_active=len(mgr.streams) if mgr else 0,
        alerts_enabled=sum(1 for a in mgr.alerts if a.enabled) if mgr else 0,
        vlm_reachable=True,   # TODO: could ping OVMS /v1/config
        uptime_seconds=time.monotonic() - _startup_time,
        timestamp=datetime.now(tz=timezone.utc),
    )


@app.get("/ready", tags=["Observability"])
async def ready():
    """
    Readiness probe — returns 200 only when the manager is running and
    at least one alert is enabled.
    """
    if manager is None:
        raise HTTPException(status_code=503, detail="Manager not ready")
    enabled = sum(1 for a in manager.alerts if a.enabled)
    if enabled == 0:
        raise HTTPException(status_code=503, detail="No alerts enabled")
    return {"status": "ready", "streams": len(manager.streams), "alerts": enabled}


@app.get("/metrics", response_model=SystemMetrics, tags=["Observability"])
async def metrics():
    """System CPU/memory and per-stream inference counters."""
    mgr = _require_manager()
    stream_metrics = mgr.get_stream_metrics()
    return SystemMetrics(
        cpu_percent=psutil.cpu_percent(interval=None),
        memory_percent=psutil.virtual_memory().percent,
        streams=[
            {
                "stream_id": m["stream_id"],
                "analysis_count": m["analysis_count"],
                "alert_count": m["alert_count"],
                "last_inference_ms": m["last_inference_ms"],
            }
            for m in stream_metrics
        ],
    )


async def _event_generator(request: Request):
    """
    SSE generator yielding:
    - ``init``         — on connection (current streams + latest results)
    - ``analysis``     — per-stream VLM results
    - ``alert_action`` — enriched event when tools are invoked
    - ``keepalive``    — every 15 s to prevent proxy timeouts
    """
    mgr = manager
    if not mgr:
        yield {"event": "error", "data": json.dumps({"message": "Manager not initialised"})}
        return

    queue = await mgr.subscribe()
    try:
        yield {
            "event": "init",
            "data": json.dumps({
                "results": mgr.latest_results,
                "streams": list(mgr.streams.keys()),
            }),
        }

        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield {"event": event["event"], "data": json.dumps(event["data"])}
            except asyncio.TimeoutError:
                yield {"event": "keepalive", "data": json.dumps({"ts": time.monotonic()})}

    except (asyncio.CancelledError, GeneratorExit):
        pass
    except Exception as exc:
        logger.error(f"SSE error: {exc}")
        yield {"event": "error", "data": json.dumps({"message": str(exc)})}
    finally:
        await mgr.unsubscribe(queue)


@app.get("/events", tags=["Streaming"])
async def sse_events(request: Request):
    """Server-Sent Events stream for real-time analysis and alert actions."""
    return EventSourceResponse(
        _event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _mjpeg_generator(stream_id: str):
    while True:
        if manager is None:
            break
        frame = manager.get_latest_frame(stream_id)
        if frame is not None:
            ret, buf = cv2.imencode(
                ".jpg", frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), 80],
            )
            if ret:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + buf.tobytes()
                    + b"\r\n"
                )
            await asyncio.sleep(0.033)   # ~30 fps display cap
        else:
            await asyncio.sleep(0.1)


@app.get("/video_feed", tags=["Streaming"])
async def video_feed(stream_id: str = "default"):
    """MJPEG stream for the dashboard video tiles."""
    return StreamingResponse(
        _mjpeg_generator(stream_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/data", tags=["Streaming"])
async def get_data():
    """Polling endpoint returning latest VLM results enriched with runtime state."""
    if not manager:
        return JSONResponse(content={})

    enriched = {}
    for stream_id, alerts in manager.latest_results.items():
        runtime_states = manager.alert_state.get_runtime_states(stream_id)
        enriched_alerts = {}
        for alert_name, result in alerts.items():
            entry = dict(result)
            state = runtime_states.get(alert_name, {})
            entry["consecutive_yes"] = state.get("consecutive_yes", 0)
            entry["consecutive_no"] = state.get("consecutive_no", 0)
            entry["last_answer"] = state.get("last_answer", "NO")
            enriched_alerts[alert_name] = entry
        enriched[stream_id] = {
            "stream_name": manager.stream_names.get(stream_id, stream_id),
            "alerts": enriched_alerts,
        }
    return JSONResponse(content=enriched)



@app.get("/streams", tags=["Streams"])
async def get_streams():
    """List all active streams with health status."""
    mgr = _require_manager()
    result = []
    for sid, stream_mgr in mgr.streams.items():
        health = stream_mgr.get_health()
        result.append(
            StreamStatus(
                stream_id=sid,
                name=mgr.stream_names.get(sid, ""),
                url=stream_mgr.rtsp_url,
                connected=health.connected,
                fps=round(health.actual_capture_fps, 2),
                resolution=health.resolution,
                buffer_fill=health.buffer_fill,
                tools=mgr.stream_tools.get(sid, []),
                alerts=mgr.stream_alerts.get(sid, []),
            ).model_dump()
        )
    return JSONResponse(content={"streams": result})


@app.post("/streams", tags=["Streams"])
async def add_stream(
    data: StreamAddRequest = Body(...),
):
    """Register a new video stream."""
    mgr = _require_manager()
    stream_id = data.resolve_id()
    if stream_id in mgr.streams:
        raise HTTPException(status_code=409, detail=f"Stream '{stream_id}' already exists")
    try:
        mgr.add_stream(stream_id, data.url, name=data.name, tools=data.tools, alerts=data.alerts)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return JSONResponse(content={
        "status": "added",
        "stream_id": stream_id,
        "name": data.name,
    })


@app.delete("/streams/{stream_id}", tags=["Streams"])
async def remove_stream(
    stream_id: str,
):
    """Remove a registered stream."""
    mgr = _require_manager()
    if stream_id not in mgr.streams:
        raise HTTPException(status_code=404, detail=f"Stream '{stream_id}' not found")
    stream_name = mgr.stream_names.get(stream_id, "")
    mgr.remove_stream(stream_id)
    return JSONResponse(content={
        "status": "removed",
        "stream_id": stream_id,
        "name": stream_name,
    })


@app.patch("/streams/{stream_id}", tags=["Streams"])
async def patch_stream(
    stream_id: str,
    data: StreamPatchRequest = Body(...),
):
    """Update per-stream settings (e.g. alert filter)."""
    mgr = _require_manager()
    if stream_id not in mgr.streams:
        raise HTTPException(status_code=404, detail=f"Stream '{stream_id}' not found")
    if data.alerts is not None:
        mgr.update_stream_alerts(stream_id, data.alerts)
    return JSONResponse(content={
        "id": stream_id,
        "alerts": mgr.stream_alerts.get(stream_id, []),
    })


@app.get("/config/alerts", tags=["Configuration"])
async def get_alerts_config():
    """Return the current alert configurations."""
    mgr = _require_manager()
    return JSONResponse(content=mgr.get_alerts_config())


@app.post("/config/alerts", tags=["Configuration"])
async def update_alerts_config(
    data: List[dict] = Body(...),
):
    """
    Replace the full alert configuration.

    Each entry must conform to the AlertConfig schema:
    - name (str, required)
    - prompt (str, required)
    - enabled (bool, default true)
    - tools (list of tool names, default [\"log_alert\"])
    - escalation (optional: {threshold_consecutive, additional_tools})
    """
    mgr = _require_manager()
    try:
        mgr.save_alerts_config(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return JSONResponse(content={"status": "saved", "count": len(data)})


@app.get("/tools", tags=["Tools"])
async def list_tools():
    """List all registered action tools and their configuration status."""
    from src.agentic import get_available_tools
    tools = get_available_tools()
    return JSONResponse(content={"tools": tools})


@app.post("/tools/{tool_name}/invoke", tags=["Tools"])
async def invoke_tool(
    tool_name: str,
    request: ToolInvokeRequest = Body(default=None),
):
    """Manually invoke a registered tool for testing."""
    from src.agentic.alert_agent import _TOOL_MAP

    fn = _TOOL_MAP.get(tool_name)
    if fn is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    params = request.parameters if request else {}
    t0 = time.monotonic()
    try:
        result = await fn(**params)
        duration_ms = (time.monotonic() - t0) * 1000
        return ToolInvokeResponse(
            tool=tool_name,
            status="success",
            result=result,
            duration_ms=round(duration_ms, 1),
        )
    except Exception as exc:
        duration_ms = (time.monotonic() - t0) * 1000
        return ToolInvokeResponse(
            tool=tool_name,
            status="error",
            result={"error": str(exc)},
            duration_ms=round(duration_ms, 1),
        )


@app.post("/tools/reload", tags=["Tools"])
async def reload_tools_endpoint():
    """Reload tools from resources/tools.json without restarting the app."""
    from src.agentic import reload_tools
    count = reload_tools()
    if manager is not None:
        manager.reload_action_agent()
    return JSONResponse(content={"status": "ok", "tools_loaded": count})


@app.get("/mcp/status", tags=["MCP"])
async def mcp_status():
    """
    Get status of all configured MCP servers.
    
    Returns connection status, transport type, and available tools per server.
    """
    if not settings.MCP_ENABLED:
        return JSONResponse(content={
            "enabled": False,
            "servers": [],
            "total_tools": 0,
        })
    
    servers = get_mcp_server_status()
    tools = get_mcp_tools()
    
    return JSONResponse(content={
        "enabled": True,
        "servers": servers,
        "total_tools": len(tools),
    })


@app.get("/mcp/tools", tags=["MCP"])
async def mcp_tools():
    """
    List all tools available from connected MCP servers.
    
    Tools are prefixed with 'mcp_{server_name}_' to distinguish from built-in tools.
    """
    if not settings.MCP_ENABLED:
        return JSONResponse(content={"tools": [], "count": 0})
    
    tools = get_mcp_tools()
    tool_list = [
        {
            "name": t.name,
            "description": t.description,
            "server": t.server,
            "input_schema": t.input_schema,
        }
        for t in tools.values()
    ]
    
    return JSONResponse(content={"tools": tool_list, "count": len(tool_list)})


@app.post("/mcp/reload", tags=["MCP"])
async def mcp_reload():
    """Reload MCP server configuration and reconnect to all servers."""
    if not settings.MCP_ENABLED:
        return JSONResponse(content={
            "status": "skipped",
            "reason": "MCP is disabled",
            "tools_loaded": 0,
        })
    
    try:
        # Clear existing MCP tools from alert agent
        from src.agentic import clear_mcp_tools, register_mcp_tools
        clear_mcp_tools()
        
        # Reload MCP servers and get new tools
        from src.agentic.mcp_client import initialize_mcp_servers, shutdown_mcp_servers
        await shutdown_mcp_servers()
        mcp_tools, mcp_schemas = await initialize_mcp_servers()
        
        # Register new tools with alert agent
        if mcp_tools:
            register_mcp_tools(mcp_tools, mcp_schemas)
        if manager is not None:
            manager.reload_action_agent()
        
        return JSONResponse(content={
            "status": "ok",
            "tools_loaded": len(mcp_tools),
        })
    except Exception as exc:
        logger.error(f"MCP reload failed: {exc}")
        raise HTTPException(status_code=500, detail=f"MCP reload failed: {exc}")


@app.post("/mcp/tools/{tool_name}/invoke", tags=["MCP"])
async def invoke_mcp_tool(
    tool_name: str,
    request: ToolInvokeRequest = Body(default=None),
):
    """Manually invoke an MCP tool for testing."""
    if not settings.MCP_ENABLED:
        raise HTTPException(status_code=503, detail="MCP is disabled")
    
    tools = get_mcp_tools()
    tool = tools.get(tool_name)
    
    if tool is None:
        raise HTTPException(status_code=404, detail=f"MCP tool '{tool_name}' not found")
    
    # Get the server connection for this tool
    from src.agentic.mcp_client import get_mcp_servers
    servers = get_mcp_servers()
    server = servers.get(tool.server)
    
    if server is None:
        raise HTTPException(
            status_code=503,
            detail=f"MCP server '{tool.server}' is not connected"
        )
    
    params = request.parameters if request else {}
    t0 = time.monotonic()
    
    try:
        result = await server.call_tool(tool_name, params)
        duration_ms = (time.monotonic() - t0) * 1000
        return ToolInvokeResponse(
            tool=tool_name,
            status="success" if result.get("status") != "error" else "error",
            result=result,
            duration_ms=round(duration_ms, 1),
        )
    except Exception as exc:
        duration_ms = (time.monotonic() - t0) * 1000
        return ToolInvokeResponse(
            tool=tool_name,
            status="error",
            result={"error": str(exc)},
            duration_ms=round(duration_ms, 1),
        )

@app.get("/runtime-config.js")
async def runtime_config():
    payload = {"metricsPort": settings.METRICS_NODEPORT}
    body = f"window.RUNTIME_CONFIG = {json.dumps(payload)};"
    return Response(content=body, media_type="application/javascript")

@app.get("/", response_class=HTMLResponse, tags=["UI"])
async def read_root():
    ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "index.html")
    if not os.path.exists(ui_path):
        return HTMLResponse(content="<h1>UI not found</h1>", status_code=404)
    with open(ui_path) as fh:
        return HTMLResponse(content=fh.read())


@app.get("/api/metrics/status")
async def get_metrics_status():
    """Application-level metrics for monitoring."""
    return {
        "active_streams": len(manager.streams) if manager else 0,
        "active_agents": sum(1 for a in manager.agents_config if a.get('enabled', False)) if manager else 0,
        "total_alerts": sum(
            1 for results in (manager.latest_results.values() if manager else [])
            for r in results.values() if r.get('answer', '').lower() == 'yes'
        )
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)

