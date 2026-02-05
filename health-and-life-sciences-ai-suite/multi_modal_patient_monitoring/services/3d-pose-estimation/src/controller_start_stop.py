"""
Control server for 3D Pose service - enables start/stop via HTTP
"""
from fastapi import FastAPI
import uvicorn
import threading
import os

app = FastAPI(title="3D Pose Control")

# Global state
processing_enabled = False
processing_lock = threading.Lock()

@app.post("/start")
def start_processing():
    """Enable pose processing"""
    global processing_enabled
    with processing_lock:
        processing_enabled = True
    return {"status": "ok", "message": "3D Pose processing started"}

@app.post("/stop")
def stop_processing():
    """Disable pose processing"""
    global processing_enabled
    with processing_lock:
        processing_enabled = False
    return {"status": "ok", "message": "3D Pose processing stopped"}

@app.get("/status")
def get_status():
    """Get current processing status"""
    return {"enabled": processing_enabled}

def is_processing_enabled():
    """Check if processing is enabled"""
    with processing_lock:
        return processing_enabled

def start_control_server():
    """Start the control server in a background thread"""
    port = int(os.getenv("CONTROL_PORT", "8083"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

if __name__ == "__main__":
    start_control_server()