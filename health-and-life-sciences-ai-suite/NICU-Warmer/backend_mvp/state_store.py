from __future__ import annotations

import copy
import threading
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuntimeStateStore:
    """In-memory live source of truth for MVP runtime state."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {
            "lifecycle": "initializing",
            "analytics": {
                "patient_presence": False,
                "caretaker_presence": False,
                "latch_status": "unknown",
            },
            "rppg": {
                "heart_rate_bpm": None,
                "respiration_rate_bpm": None,
                "signal_confidence": 0.0,
                "status": "idle",
            },
            "frame": {
                "available": False,
                "timestamp": None,
            },
            "metrics": {
                "fps": 0.0,
                "latency_ms": 0.0,
                "frame_count": 0,
                "loop_count": 0,
                "runtime_status": "idle",
            },
            "checks": {
                "models_ready": False,
                "video_ready": False,
                "pipeline_ready": False,
                "dlsps_reachable": False,
            },
            "errors": [],
            "updated_at": _utc_now(),
        }

    def patch(self, patch: dict[str, Any]) -> None:
        with self._lock:
            self._deep_update(self._state, patch)
            self._state["updated_at"] = _utc_now()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    @staticmethod
    def _deep_update(dest: dict[str, Any], patch: dict[str, Any]) -> None:
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(dest.get(key), dict):
                RuntimeStateStore._deep_update(dest[key], value)
            else:
                dest[key] = value
