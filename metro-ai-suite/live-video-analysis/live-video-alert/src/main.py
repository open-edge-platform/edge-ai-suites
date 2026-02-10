import cv2
import asyncio
import logging
import os
import sys
import json
from fastapi import FastAPI, Body, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from sse_starlette.sse import EventSourceResponse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.agent_manager import AgentManager
from src.config import settings, setup_logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

# Global Manager Instance
manager: AgentManager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the AgentManager
    global manager
    
    logger.info(f"Starting NVR Service... VLM: {settings.VLM_URL}")

    manager = AgentManager(
        vlm_url=settings.VLM_URL,
        vlm_api_key=settings.VLM_API_KEY,
        model_name=settings.MODEL_NAME          
    )

    # Add default stream if RTSP_URL is provided
    if settings.RTSP_URL:
        manager.add_stream("default", settings.RTSP_URL)

    # Start the manager in the background (uses dynamic agents from config)
    asyncio.create_task(manager.start())
    
    yield
    
    # Shutdown
    if manager:
        manager.stop()

app = FastAPI(lifespan=lifespan)

# Mount static files directory
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Frame Generator for MJPEG
async def generate_frames(stream_id: str):
    while True:
        if manager:
            frame = manager.get_latest_frame(stream_id)
            if frame is not None:
                ret, buffer = cv2.imencode('.jpg', frame)
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                await asyncio.sleep(0.01)
            else:
                await asyncio.sleep(0.05)
        else:
            break

@app.get("/video_feed")
async def video_feed(stream_id: str = "default"):
    return StreamingResponse(generate_frames(stream_id), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/data")
async def get_data():
    """Legacy polling endpoint - kept for fallback compatibility."""
    if manager:
        return JSONResponse(content=manager.latest_results)
    return JSONResponse(content={})

async def event_generator(request: Request):
    """
    SSE event generator with graceful disconnect handling.
    
    Events sent:
    - init: Initial state (streams list + latest results)
    - analysis: Real-time analysis results for a stream
    - keepalive: Heartbeat every 15s to prevent timeout
    """
    if not manager:
        yield {"event": "error", "data": json.dumps({"message": "Manager not initialized"})}
        return
    
    queue = await manager.subscribe()
    
    try:
        # Send initial state immediately upon connection
        yield {
            "event": "init",
            "data": json.dumps({
                "results": manager.latest_results,
                "streams": list(manager.streams.keys()),
                "message": "Connected to SSE"
            })
        }
        
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.info("SSE client disconnected")
                break
            
            try:
                # Wait for events with 15s timeout for keepalive
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"])
                }
            except asyncio.TimeoutError:
                # Send keepalive to prevent connection timeout
                yield {"event": "keepalive", "data": json.dumps({"ts": asyncio.get_event_loop().time()})}
                
    except asyncio.CancelledError:
        logger.info("SSE connection cancelled")
    except Exception as e:
        logger.error(f"SSE error: {e}")
        yield {"event": "error", "data": json.dumps({"message": str(e)})}
    finally:
        await manager.unsubscribe(queue)


@app.get("/events")
async def sse_events(request: Request):
    """SSE endpoint for real-time analysis results."""
    return EventSourceResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )

@app.get("/streams")
async def get_streams():
    if manager:
        return JSONResponse(content={"streams": list(manager.streams.keys())})
    return JSONResponse(content={"streams": []})

@app.post("/streams")
async def add_stream(data: dict = Body(...)):
    stream_id = data.get("id")
    url = data.get("url")
    if not stream_id or not url:
        raise HTTPException(status_code=400, detail="Missing id or url")
    if manager:
        manager.add_stream(stream_id, url)
        return JSONResponse(content={"status": "added", "id": stream_id})
    raise HTTPException(status_code=503, detail="Manager not initialized")

@app.delete("/streams/{stream_id}")
async def remove_stream(stream_id: str):
    if manager:
        manager.remove_stream(stream_id)
        return JSONResponse(content={"status": "removed", "id": stream_id})
    raise HTTPException(status_code=503, detail="Manager not initialized")

@app.get("/config/agents")
async def get_agents_config():
    """Get current agent configuration"""
    if manager:
        return JSONResponse(content=manager.get_agents_config())
    return JSONResponse(content=[])

@app.post("/config/agents")
async def update_agents_config(data: list = Body(...)):
    """Update agent configuration (max 4 agents)"""
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    
    if len(data) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 agents allowed")
    
    manager.save_agents_config(data)
    return JSONResponse(content={"status": "saved", "count": len(data)})

@app.get("/", response_class=HTMLResponse)
async def read_root():
    ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "index.html")
    if not os.path.exists(ui_path):
        return HTMLResponse(content="<h1>UI Not Found</h1>")
    with open(ui_path, "r") as f:
        return HTMLResponse(content=f.read())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)

