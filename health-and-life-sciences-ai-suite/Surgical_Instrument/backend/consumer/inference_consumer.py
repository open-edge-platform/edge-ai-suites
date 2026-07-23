"""Backend-side consumer for the DL Streamer control plane.

The pipeline container now owns rendering and latency collection. This class
keeps the old worker-shaped interface but sources its state directly from the
pipeline HTTP control plane.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from .pipeline_client import PipelineClient

log = logging.getLogger(__name__)


class InferenceConsumer:
    def __init__(
        self,
        *,
        device: str = "GPU",
        source_kind: str | None = None,
        source_arg: str | None = None,
        pipeline_host: str | None = None,
        pipeline_port: int | None = None,
    ) -> None:
        self._device = str(device).upper()
        self._source_kind = source_kind
        self._source_arg  = source_arg
        self._pipeline_host = pipeline_host or os.environ.get("PIPELINE_HOST", "surgical-pipeline")
        self._pipeline_port = int(pipeline_port or os.environ.get("PIPELINE_PORT", "8000"))

        self._client = PipelineClient(self._pipeline_host, self._pipeline_port)

        self._lock = threading.Lock()
        self._running = False
        self._started_at: float | None = None
        self._last_latency: dict[str, Any] = {"available": False, "samples": 0}
        self._last_health: dict[str, Any] = {
            "status": "idle",
            "pid": None,
            "device": self._device,
            "source_kind": self._source_kind,
            "source_arg": self._source_arg,
        }

    def _mark_not_running(self) -> None:
        with self._lock:
            self._running = False

    # ---------------------------------------------------------------- start
    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._started_at = time.time()

        try:
            self._client.start(
                self._device,
                source_kind=self._source_kind,
                source_arg=self._source_arg,
            )
            self._refresh_snapshots()
        except Exception:
            with self._lock:
                self._running = False
            raise

    # ----------------------------------------------------------------- stop
    def stop(self, timeout: float = 5.0) -> None:  # noqa: ARG002 — mirror old sig
        with self._lock:
            if not self._running:
                return
            self._running = False

        try:
            self._client.stop()
        except Exception as exc:  # noqa: BLE001
            log.warning("pipeline stop error: %s", exc)
        self._refresh_snapshots()

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def _refresh_snapshots(self) -> None:
        try:
            self._last_health = self._client.health()
            # Keep internal running flag aligned with control-plane truth.
            if self._last_health.get("status") != "running" and not self._last_health.get("wanted_running", False):
                self._mark_not_running()
        except Exception as exc:  # noqa: BLE001
            log.debug("pipeline health fetch failed: %s", exc)
            self._mark_not_running()
        try:
            self._last_latency = self._client.latency()
        except Exception as exc:  # noqa: BLE001
            log.debug("pipeline latency fetch failed: %s", exc)

    # ---------------------------------------------------------------- stats
    def stats(self) -> dict[str, Any]:
        self._refresh_snapshots()
        lat = self._last_latency or {}
        health = self._last_health or {}
        uptime_s = 0.0
        if self._started_at is not None:
            uptime_s = max(0.0, time.time() - self._started_at)
        pipeline_running = health.get("status") == "running"
        wanted_running = bool(health.get("wanted_running", False))
        running = self.is_running() and pipeline_running
        fps = 60.0 if running else 0.0
        return {
            "running": running,
            "pipeline_running": pipeline_running,
            "wanted_running": wanted_running,
            "source_kind": health.get("source_kind", self._source_kind),
            "source_arg": health.get("source_arg", self._source_arg),
            "delivered_fps": fps,
            "infer_mean_ms": 0.0,
            "infer_p50_ms": 0.0,
            "infer_p90_ms": 0.0,
            "infer_p95_ms": 0.0,
            "infer_p99_ms": 0.0,
            "processing_mean_ms": float(lat.get("mean_ms", 0.0)),
            "processing_p50_ms": float(lat.get("p50_ms", 0.0)),
            "processing_p90_ms": float(lat.get("p90_ms", 0.0)),
            "processing_p95_ms": float(lat.get("p95_ms", 0.0)),
            "processing_p99_ms": float(lat.get("p99_ms", 0.0)),
            "e2e_mean_ms": 0.0,
            "e2e_p50_ms": 0.0,
            "e2e_p90_ms": 0.0,
            "e2e_p95_ms": 0.0,
            "e2e_p99_ms": 0.0,
            "total_mean_ms": float(lat.get("mean_ms", 0.0)),
            "total_p99_ms": float(lat.get("p99_ms", 0.0)),
            "frame_id": int(lat.get("samples", 0)),
            "uptime_s": uptime_s,
            "cumulative_detections": 0,
            "frames_with_detection": 0,
            "detection_rate": 0.0,
            "peak_confidence": 0.0,
            "distinct_polyps": 0,
        }

    def latest_detections(self) -> dict[str, Any]:
        return {"detections": []}

    def latest_frame_jpeg(self) -> bytes | None:
        return None
