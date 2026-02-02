"""Control server for RPPG service - enables start/stop via HTTP."""

from fastapi import FastAPI
import uvicorn
import threading
import os

app = FastAPI(title="RPPG Control")

# Global state
_streaming_enabled: bool = False
_state_lock = threading.Lock()


@app.post("/start")
def start_streaming():
    """Enable RPPG streaming."""
    global _streaming_enabled
    with _state_lock:
        _streaming_enabled = True
    return {"status": "ok", "message": "RPPG streaming started"}


@app.post("/stop")
def stop_streaming():
    """Disable RPPG streaming."""
    global _streaming_enabled
    with _state_lock:
        _streaming_enabled = False
    return {"status": "ok", "message": "RPPG streaming stopped"}


@app.get("/status")
def get_status():
    """Get current streaming status."""
    with _state_lock:
        enabled = _streaming_enabled
    return {"enabled": enabled}


def is_streaming_enabled() -> bool:
    """Return whether streaming is currently enabled."""
    with _state_lock:
        return _streaming_enabled


def start_control_server() -> None:
    """Start the RPPG control server.

    Runs a FastAPI app exposing /start, /stop, /status for the
    aggregator-service to control streaming.
    """
    port = int(os.getenv("RPPG_CONTROL_PORT", "8084"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    start_control_server()
