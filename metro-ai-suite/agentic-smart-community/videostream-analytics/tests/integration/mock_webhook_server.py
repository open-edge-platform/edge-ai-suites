"""Mock webhook server that records events posted by videostream-analytics.

Run standalone: python -m tests.integration.mock_webhook_server
Or via uvicorn: uvicorn tests.integration.mock_webhook_server:app --port 9999
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [mock-webhook] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Mock Webhook Server")

_recorded_events: list[dict[str, Any]] = []


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mock-webhook", "event_count": len(_recorded_events)}


def _ev_type(event: dict) -> str:
    """Phase 7 envelope reads `type`; tolerate legacy `event_type` for safety."""
    return event.get("type") or event.get("event_type") or "?"


@app.post("/events")
async def receive_event(event: dict[str, Any]):
    _recorded_events.append(event)
    logger.info("Received event: %s (total: %d)", _ev_type(event), len(_recorded_events))
    return {"status": "received"}


@app.get("/recorded_events")
async def get_recorded_events():
    return {"events": _recorded_events, "count": len(_recorded_events)}


@app.get("/recorded_events/motion")
async def get_motion_events():
    motion = [e for e in _recorded_events if _ev_type(e) == "motion"]
    return {"events": motion, "count": len(motion)}


@app.get("/recorded_events/recording")
async def get_recording_events():
    rec = [e for e in _recorded_events if _ev_type(e) == "recording"]
    return {"events": rec, "count": len(rec)}


@app.get("/recorded_events/static")
async def get_static_events():
    static = [e for e in _recorded_events if _ev_type(e) == "static"]
    return {"events": static, "count": len(static)}


@app.get("/recorded_events/status")
async def get_status_events():
    status = [e for e in _recorded_events if _ev_type(e) == "status"]
    return {"events": status, "count": len(status)}


@app.delete("/recorded_events")
async def clear_events():
    count = len(_recorded_events)
    _recorded_events.clear()
    return {"status": "cleared", "cleared_count": count}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9999)
