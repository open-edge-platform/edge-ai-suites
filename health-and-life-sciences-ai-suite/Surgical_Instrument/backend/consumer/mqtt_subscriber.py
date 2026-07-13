"""Paho-MQTT subscriber that maintains live detection state.

The DL Streamer pipeline publishes one JSON payload per frame (via a
`gvapython` MQTTPublisher callback in the pipeline container). Each payload
follows the `gvametaconvert format=json` schema:

    {
      "objects": [
        {
          "detection": {
            "bounding_box": {"x_min":..,"y_min":..,"x_max":..,"y_max":..},
            "confidence": 0.90,
            "label": "Polyp",
            "label_id": 0
          },
          "x": 1089, "y": 239, "w": 415, "h": 534,
          "id": 1,              # gvatrack short-term-imageless track id
          "region_id": 1,
          "roi_type": "Polyp"
        }
      ],
      "resolution": {"width": 1920, "height": 1080},
      "timestamp": 366666666
    }

`MQTTSubscriber` translates that into the same detection dict shape the old
`InferenceWorker.latest_detections()` produced, so the rest of the backend
stays untouched.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)


class MQTTSubscriber:
    def __init__(self, host: str, port: int, topic: str,
                 min_track_len: int = 5) -> None:
        self._host = host
        self._port = port
        self._topic = topic
        self._min_track_len = int(min_track_len)

        self._client: mqtt.Client | None = None
        self._lock = threading.Lock()
        self._started_at: float | None = None

        # Snapshot state used by `latest_detections()` (mirrors InferenceWorker).
        self._latest_dets: dict[str, Any] = {
            "frame_id": 0, "ts": 0.0, "detections": [],
            "infer_ms": 0.0, "total_ms": 0.0,
        }
        # Rolling session counters.
        self._frame_id = 0
        self._frames_with_detection = 0
        self._cumulative_detections = 0
        self._peak_confidence = 0.0
        self._track_frame_counts: dict[int, int] = {}

    # -------------------------------------------------------------- lifecycle
    def start(self) -> None:
        if self._client is not None:
            return
        self._started_at = time.time()
        self._client = mqtt.Client(client_id="surgical-backend")
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.connect_async(self._host, self._port, keepalive=30)
        self._client.loop_start()
        log.info("MQTTSubscriber: connecting to %s:%d topic=%s",
                 self._host, self._port, self._topic)

    def stop(self) -> None:
        c = self._client
        self._client = None
        if c is None:
            return
        try:
            c.loop_stop()
            c.disconnect()
        except Exception as exc:  # noqa: BLE001
            log.warning("MQTTSubscriber stop error: %s", exc)

    # ------------------------------------------------------- paho callbacks
    def _on_connect(self, _c, _u, _f, rc):
        if rc == 0:
            self._client.subscribe(self._topic, qos=0)
            log.info("MQTTSubscriber: subscribed to %s", self._topic)
        else:
            log.error("MQTTSubscriber: connect rc=%s", rc)

    def _on_message(self, _c, _u, msg) -> None:
        try:
            payload = json.loads(msg.payload)
        except Exception as exc:  # noqa: BLE001
            log.debug("bad MQTT payload: %s", exc)
            return
        self._ingest(payload)

    # ------------------------------------------------------------- ingest
    def _ingest(self, payload: dict[str, Any]) -> None:
        objects = payload.get("objects") or []
        detections: list[dict[str, Any]] = []
        peak = 0.0
        for obj in objects:
            det = obj.get("detection") or {}
            label = det.get("label", obj.get("roi_type", ""))
            conf = float(det.get("confidence", 0.0))
            peak = max(peak, conf)
            bb = det.get("bounding_box") or {}
            # gvametaconvert gives normalised bbox in "bounding_box" AND pixel
            # coords in the top-level x/y/w/h fields. Downstream code wants
            # xyxy pixels — build them from the pixel fields.
            x = int(obj.get("x", 0))
            y = int(obj.get("y", 0))
            w = int(obj.get("w", 0))
            h = int(obj.get("h", 0))
            track_id = obj.get("id")
            detections.append({
                "class_id": int(det.get("label_id", 0)),
                "class_name": str(label),
                "confidence": conf,
                "bbox": [x, y, x + w, y + h],
                "track_id": int(track_id) if track_id is not None else None,
                # keep normalised box for callers that want it
                "bbox_norm": [
                    float(bb.get("x_min", 0.0)),
                    float(bb.get("y_min", 0.0)),
                    float(bb.get("x_max", 0.0)),
                    float(bb.get("y_max", 0.0)),
                ],
            })

        with self._lock:
            self._frame_id += 1
            if detections:
                self._frames_with_detection += 1
                self._cumulative_detections += len(detections)
                if peak > self._peak_confidence:
                    self._peak_confidence = peak
            for d in detections:
                tid = d["track_id"]
                if tid is not None:
                    self._track_frame_counts[tid] = self._track_frame_counts.get(tid, 0) + 1

            self._latest_dets = {
                "frame_id": self._frame_id,
                "ts": time.time(),
                "detections": detections,
                # Per-frame latency numbers live in the tracer log, not MQTT.
                # Fill zeros here; the app's `_snapshot_full()` reads latency
                # from `latency_tail`, not from `latest_detections`.
                "infer_ms": 0.0,
                "total_ms": 0.0,
            }

    # --------------------------------------------------------------- queries
    def latest_detections(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._latest_dets)

    def snapshot(self) -> dict[str, Any]:
        """Cheap read used by InferenceConsumer.stats()."""
        with self._lock:
            uptime = time.time() - (self._started_at or time.time())
            det_rate = (self._frames_with_detection / self._frame_id) if self._frame_id else 0.0
            distinct = sum(1 for n in self._track_frame_counts.values() if n >= self._min_track_len)
            return {
                "frame_id": self._frame_id,
                "uptime_s": uptime,
                "delivered_fps": (self._frame_id / uptime) if uptime > 0 else 0.0,
                "frames_with_detection": self._frames_with_detection,
                "cumulative_detections": self._cumulative_detections,
                "detection_rate": det_rate,
                "peak_confidence": self._peak_confidence,
                "distinct_polyps": distinct,
            }
