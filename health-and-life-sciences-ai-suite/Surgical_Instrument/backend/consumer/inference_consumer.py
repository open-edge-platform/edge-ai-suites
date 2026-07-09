"""Consumer façade — drop-in replacement for the deleted
`backend.pipeline.inference.InferenceWorker`.

The old inline pipeline (OpenCV decode + Ultralytics infer + PIL annotate)
has moved into the `surgical-pipeline` container (DL Streamer). This class
just glues the three consumers together:

* `PipelineClient`  — POST /start /stop to the pipeline container
* `MQTTSubscriber`  — receive per-frame detection metadata over MQTT
* `LatencyTail`     — parse GStreamer latency_tracer log
* `FrameReader`     — read annotated JPEG from the shared `/frames` volume

Public interface — matches the old InferenceWorker so nothing else changes:
    start()                 -> None
    stop(timeout=5.0)       -> None
    is_running()            -> bool
    stats()                 -> dict[str, Any]
    latest_detections()     -> dict[str, Any]
    latest_frame_jpeg()     -> bytes | None
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from .frame_reader import FrameReader
from .latency_tail import LatencyTail
from .mqtt_subscriber import MQTTSubscriber
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
        mqtt_host: str | None = None,
        mqtt_port: int | None = None,
        mqtt_topic: str | None = None,
        frame_dir: str | None = None,
        min_track_len: int = 5,
    ) -> None:
        self._device = str(device).upper()
        self._source_kind = source_kind
        self._source_arg  = source_arg
        self._pipeline_host = pipeline_host or os.environ.get("PIPELINE_HOST", "surgical-pipeline")
        self._pipeline_port = int(pipeline_port or os.environ.get("PIPELINE_PORT", "8000"))
        self._mqtt_host = mqtt_host or os.environ.get("MQTT_HOST", "surgical-mqtt")
        self._mqtt_port = int(mqtt_port or os.environ.get("MQTT_PORT", "1883"))
        self._mqtt_topic = mqtt_topic or os.environ.get("MQTT_TOPIC", "surgical/detections")
        self._frame_dir = frame_dir or os.environ.get("FRAME_DIR", "/frames")

        self._client = PipelineClient(self._pipeline_host, self._pipeline_port)
        self._mqtt = MQTTSubscriber(
            self._mqtt_host, self._mqtt_port, self._mqtt_topic,
            min_track_len=min_track_len,
        )
        self._latency = LatencyTail(f"{self._frame_dir}/latency.log")
        self._frames = FrameReader(f"{self._frame_dir}/latest.jpg")

        self._lock = threading.Lock()
        self._running = False
        self._started_at: float | None = None

    # ---------------------------------------------------------------- start
    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._started_at = time.time()

        # Consumers first — they must be ready before the pipeline starts
        # publishing, otherwise we drop the first few frames on the floor.
        self._mqtt.start()
        self._latency.start()
        self._frames.clear()

        try:
            self._client.start(
                self._device,
                source_kind=self._source_kind,
                source_arg=self._source_arg,
            )
        except Exception:
            # Bring the consumers back down if the pipeline refuses to start.
            self._mqtt.stop()
            self._latency.stop()
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
        self._mqtt.stop()
        self._latency.stop()

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    # ---------------------------------------------------------------- stats
    def stats(self) -> dict[str, Any]:
        m = self._mqtt.snapshot()
        lat = self._latency.snapshot()
        return {
            "running": self.is_running(),
            "delivered_fps": m["delivered_fps"],
            "infer_mean_ms": lat["infer_mean_ms"],
            "infer_p99_ms":  lat["infer_p99_ms"],
            # Processing-chain sum: gvadetect + gvatrack + gvametaconvert +
            # gvawatermark + jpegenc. This is what the customer sees as
            # "camera-to-screen" on a live source, and what the <30 ms
            # requirement is against.
            "processing_mean_ms": lat["processing_mean_ms"],
            "processing_p99_ms": lat["processing_p99_ms"],
            # Full source→sink residence — diagnostics only.
            "e2e_mean_ms":   lat["e2e_mean_ms"],
            "e2e_p99_ms":    lat["e2e_p99_ms"],
            "total_mean_ms": lat["e2e_mean_ms"],
            "total_p99_ms":  lat["e2e_p99_ms"],
            "frame_id": m["frame_id"],
            "uptime_s": m["uptime_s"],
            "cumulative_detections": m["cumulative_detections"],
            "frames_with_detection": m["frames_with_detection"],
            "detection_rate": m["detection_rate"],
            "peak_confidence": m["peak_confidence"],
            "distinct_polyps": m["distinct_polyps"],
        }

    def latest_detections(self) -> dict[str, Any]:
        return self._mqtt.latest_detections()

    def latest_frame_jpeg(self) -> bytes | None:
        return self._frames.latest_jpeg()
