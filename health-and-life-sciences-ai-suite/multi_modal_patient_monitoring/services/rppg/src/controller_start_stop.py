"""Control server for RPPG service - enables start/stop + data streaming via HTTP."""

from fastapi import FastAPI
import uvicorn
import threading
import os
import time
from typing import Optional, Dict, Any
import numpy as np

app = FastAPI(title="RPPG Control")

# Global state
_streaming_enabled: bool = False
_state_lock = threading.Lock()

# Data buffer (populated by RPPGService, consumed by /stream_next)
_latest_data: Optional[Dict[str, Any]] = None
_data_lock = threading.Lock()


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


@app.get("/stream_next")
def stream_next():
    """
    Get next rPPG measurement for aggregator polling.
    
    Returns latest HR, RR, SpO2, and respiratory waveform.
    """
    with _data_lock:
        if _latest_data is None:
            return {
                "status": "no_data",
                "message": "Waiting for RPPG processing to start"
            }
        
        # Return a copy to avoid data races
        return dict(_latest_data)


def is_streaming_enabled() -> bool:
    """Return whether streaming is currently enabled."""
    with _state_lock:
        return _streaming_enabled


def update_latest_data(data: Dict[str, Any]) -> None:
    """
    Update the latest data buffer (called by RPPGService).
    
    Args:
        data: Dictionary with keys:
            - device_id (str)
            - metric (str): "RESP_RATE"
            - timestamp (int): milliseconds
            - HR (float): heart rate in BPM
            - RR (float): respiratory rate in BrPM
            - SpO2 (float): oxygen saturation (%)
            - waveform (list): respiratory waveform samples
            - waveform_frequency_hz (int): 30
    """
    global _latest_data
    
    # Convert numpy arrays to lists for JSON serialization
    if 'waveform' in data and isinstance(data['waveform'], np.ndarray):
        data['waveform'] = data['waveform'].tolist()
    
    with _data_lock:
        _latest_data = data


def start_control_server() -> None:
    """Start the RPPG control server."""
    port = int(os.getenv("RPPG_CONTROL_PORT", "8084"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    start_control_server()