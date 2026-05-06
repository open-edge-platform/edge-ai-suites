from __future__ import annotations

import argparse
import base64
import copy
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

from .aggregator import RuntimeAggregator
from .asset_preparation import AssetPreparationService
from .dlsps_controller import DLSPSController, DLSPSControllerConfig
from .frame_service import FrameService
from .lifecycle import Lifecycle, LifecycleManager
from .person_detector import PersonDetector
from .latch_detector import LatchDetector
from .state_store import RuntimeStateStore


class MVPBackend:
    def __init__(self, config_path: Path) -> None:
        self.lifecycle = LifecycleManager()
        self.state = RuntimeStateStore()
        self.config_path = config_path
        self.prepare_service = AssetPreparationService(config_path)
        self.frame_service = FrameService()
        self.aggregator = RuntimeAggregator()
        self._rppg_pipeline: Any = None  # lazy: created after assets prepared
        self._event_seq = 0
        self._event_seq_lock = threading.Lock()
        self._resolved_pipeline_path: str | None = None
        self._rppg_model_path: str | None = None
        self._status_poll_interval_s = 1.0
        self._frame_thread: threading.Thread | None = None
        self._inference_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_frame_count = 0
        self._video_path: str | None = None
        self._local_video_cap: Any = None
        self._video_total_frames: int = 0
        self._video_looping = False  # guard against multiple loop restarts
        self._person_detector: PersonDetector | None = None
        self._latch_detector: LatchDetector | None = None
        # Shared between frame thread and inference thread
        self._latest_raw_jpeg: bytes | None = None
        self._latest_raw_lock = threading.Lock()
        self._cached_detections: list[dict] = []
        self._cached_detections_lock = threading.Lock()

        cfg = self.prepare_service.load_config()
        dlsps_cfg = cfg.get("dlsps", {})
        self._inference_mode = dlsps_cfg.get("inference_mode", "direct")  # "direct" | "dlsps" | "hybrid"
        self._assume_dlsps_reachable = bool(dlsps_cfg.get("assume_reachable", False))
        # MQTT settings for DLSPS mode
        self._mqtt_broker = dlsps_cfg.get("mqtt_broker", "")
        self._mqtt_topic = dlsps_cfg.get("mqtt_topic", "nicu/detections")
        self._mqtt_client_id = dlsps_cfg.get("mqtt_client_id", "nicu-backend")
        self._mqtt_client: Any = None
        self._mqtt_latest_data: dict | None = None
        self._mqtt_data_lock = threading.Lock()
        self._mqtt_frame_gen = 0          # bumped each MQTT frame
        self._annotated_jpeg: bytes | None = None  # cached annotated frame
        self._annotated_gen = -1          # gen of cached annotated frame
        self._mqtt_fps_times: list[float] = []  # timestamps for FPS calc
        self._mqtt_last_ts: float = 0.0   # last MQTT message time (for staleness)
        self._mqtt_rppg_latest: dict | None = None  # rPPG from DLSPS gvapython
        self._mqtt_action_latest: dict | None = None  # action from DLSPS gvapython
        self._pipeline_devices: dict[str, str] = {}   # workload → device (set on start)
        # Per-workload inference latency (ms) from extension metadata
        self._workload_latency: dict[str, float] = {}  # e.g. {"rppg": 2.3, "action": 5.1}
        # User-configurable settings (set via /config/* endpoints before starting)
        self._user_config: dict = {
            "video_file": None,       # uploaded filename or None (use default)
            "roi": {                  # rPPG face ROI (normalised 0-1)
                "top": 0.10,
                "left": 0.30,
                "bottom": 0.56,
                "right": 0.70,
            },
            "roi_custom": False,      # True when user has explicitly set ROI
            "devices": {              # per-model device assignments (from env profile)
                "detect": os.environ.get("DETECTION_DEVICE", "GPU"),
                "rppg": os.environ.get("RPPG_DEVICE", "CPU"),
                "action": os.environ.get("ACTION_DEVICE", "NPU"),
            },
        }
        # In DLSPS inference mode, use the tee pipeline for full-speed frames
        pipeline_version = dlsps_cfg.get("pipeline_version")
        if self._inference_mode in ("dlsps", "hybrid"):
            pipeline_version = "nicu_tee"
        self.dlsps = DLSPSController(
            DLSPSControllerConfig(
                base_url=dlsps_cfg.get("base_url", "http://localhost:8080"),
                timeout_seconds=float(dlsps_cfg.get("timeout_seconds", 2.0)),
                pipeline_name=dlsps_cfg.get("pipeline_name"),
                pipeline_version=pipeline_version,
                detections_path=dlsps_cfg.get("detections_path", "/shared/detections.jsonl"),
                mqtt_broker=self._mqtt_broker if self._inference_mode in ("dlsps", "hybrid") else "",
                mqtt_topic=self._mqtt_topic,
            )
        )
        self._detections_path = dlsps_cfg.get("detections_path", "/shared/detections.jsonl")
        self._status_poll_interval_s = float(dlsps_cfg.get("status_poll_interval_seconds", 1.0))
        # In DLSPS mode, poll detections faster to match DLSPS pipeline FPS (~9)
        if self._inference_mode in ("dlsps", "hybrid"):
            self._status_poll_interval_s = min(self._status_poll_interval_s, 0.1)

    def bootstrap(self) -> None:
        try:
            self.lifecycle.transition(Lifecycle.PREPARING)
            prep = self.prepare_service.prepare()
            checks = prep.checks.copy()
            checks["dlsps_reachable"] = (
                True if self._assume_dlsps_reachable else self.dlsps.is_reachable()
            )
            errors = list(prep.errors)
            if not checks["dlsps_reachable"]:
                errors.append(
                    {
                        "code": "DLSPS_UNREACHABLE",
                        "message": "DLSPS is not reachable",
                    }
                )

            self._resolved_pipeline_path = prep.resolved_manifest.get("resolved_pipeline")
            self._video_path = prep.resolved_manifest.get("video_path")
            self._rppg_model_path = prep.resolved_manifest.get("rppg", {}).get(
                "xml", prep.resolved_manifest.get("rppg_model_path")
            )
            self.state.patch(
                {
                    "lifecycle": Lifecycle.PREPARING.value,
                    "checks": checks,
                    "errors": errors,
                }
            )

            if errors:
                self.lifecycle.mark_error("; ".join([e["message"] for e in errors]))
                self.state.patch(
                    {
                        "lifecycle": Lifecycle.ERROR.value,
                        "metrics": {"runtime_status": "error"},
                    }
                )
                return

            # Initialise person detector — runs person-detect + patient-detect
            # directly via OpenVINO for frame-accurate bounding boxes.
            dlsps_cfg = self.prepare_service.load_config().get("dlsps", {})
            inference_device = dlsps_cfg.get("device", "CPU")

            if self._inference_mode == "direct":
                logger.info("Inference mode: DIRECT (OpenVINO in backend)")
            elif self._inference_mode == "hybrid":
                logger.info("Inference mode: HYBRID (local OpenVINO detection + DLSPS metrics)")
            else:
                logger.info("Inference mode: DLSPS (MQTT-based detection from DLSPS pipeline)")

            # In direct and hybrid modes, initialise local OpenVINO detectors
            # for frame-accurate bounding boxes.
            # In dlsps mode, detections come via MQTT — no local models needed.
            if self._inference_mode in ("direct", "hybrid"):
                person_model = str(Path(self.config_path).parent.parent / "person-detect-fp32.xml")
                patient_model = str(Path(self.config_path).parent.parent / "patient-detect-fp32.xml")
                self._person_detector = PersonDetector(
                    person_model_xml=person_model,
                    patient_model_xml=patient_model,
                    confidence=float(
                        dlsps_cfg.get("thresholds", {}).get("patient_presence", 0.3)
                    ),
                    device=inference_device,
                )

                latch_model = str(Path(self.config_path).parent.parent / "latch-detect-fp32.xml")
                latch_conf = float(
                    dlsps_cfg.get("thresholds", {}).get("latch_detection", 0.20)
                )
                self._latch_detector = LatchDetector(
                    latch_model, confidence=latch_conf, device=inference_device,
                )

            self.lifecycle.transition(Lifecycle.READY)
            self.state.patch(
                {
                    "lifecycle": Lifecycle.READY.value,
                    "metrics": {"runtime_status": "ready"},
                }
            )
        except Exception as exc:
            self.lifecycle.mark_error(str(exc))
            self.state.patch(
                {
                    "lifecycle": Lifecycle.ERROR.value,
                    "errors": [{"code": "BOOTSTRAP_ERROR", "message": str(exc)}],
                    "metrics": {"runtime_status": "error"},
                }
            )

    def next_event_seq(self) -> int:
        with self._event_seq_lock:
            self._event_seq += 1
            return self._event_seq

    def start_status_poller(self) -> None:
        if self._frame_thread and self._frame_thread.is_alive():
            return
        self._stop_event.clear()
        # Start MQTT subscriber for DLSPS mode (must start before loops)
        if self._inference_mode == "dlsps" and self._mqtt_broker:
            self._start_mqtt_subscriber()
        self._frame_thread = threading.Thread(
            target=self._frame_loop, daemon=True, name="frame-loop",
        )
        self._inference_thread = threading.Thread(
            target=self._inference_loop, daemon=True, name="inference-loop",
        )
        self._frame_thread.start()
        self._inference_thread.start()

    def stop_status_poller(self) -> None:
        self._stop_event.set()
        self._stop_mqtt_subscriber()
        for t in (self._frame_thread, self._inference_thread):
            if t and t.is_alive():
                t.join(timeout=5.0)
                if t.is_alive():
                    logger.warning("Thread %s did not exit within timeout", t.name)
        self._frame_thread = None
        self._inference_thread = None
        self._release_local_video_cap()
        if self._person_detector:
            self._person_detector.close()
        self._rppg_pipeline = None
        self.aggregator._last_hr = None
        self.aggregator._last_rr = None
        if self._latch_detector:
            self._latch_detector.reset()
        with self._cached_detections_lock:
            self._cached_detections = []
        with self._latest_raw_lock:
            self._latest_raw_jpeg = None

    def _release_local_video_cap(self) -> None:
        cap = self._local_video_cap
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        self._local_video_cap = None

    def _on_video_loop(self) -> None:
        """Called when the local video reaches EOF and loops back to frame 0.

        Resets the person detector's stale-file tracking and restarts DLSPS
        so it re-processes the video and writes fresh detection metadata.
        The old detections file is truncated to avoid ghost detections from
        the previous loop.
        """
        logger.info("Video looped — restarting DLSPS and clearing stale detections")
        self._restart_dlsps()

    def _maybe_restart_dlsps(self) -> None:
        """Restart DLSPS if it has completed and detections are stale.

        In MQTT mode: track staleness via last MQTT message timestamp.
        In file mode: track staleness via detections file mtime.
        """
        if self._inference_mode == "dlsps":
            # MQTT-based staleness detection
            if self._mqtt_last_ts == 0.0:
                return  # haven't received any MQTT messages yet
            stale_seconds = time.time() - self._mqtt_last_ts
            if stale_seconds < 5.0:
                return  # MQTT messages still flowing
            logger.info("MQTT detections stale for %.0fs — restarting DLSPS", stale_seconds)
            self._restart_dlsps()
            return

        import os as _os  # noqa: PLC0415
        try:
            stat = _os.stat(self._detections_path)
            stale_seconds = time.time() - stat.st_mtime
            if stale_seconds < 5.0:
                return  # DLSPS is still actively writing
            if stat.st_size == 0:
                return  # already truncated, restart in progress
        except FileNotFoundError:
            return  # file doesn't exist yet

        # DLSPS has stopped writing for >5s — restart it
        logger.info("Detections stale for %.0fs — restarting DLSPS", stale_seconds)
        self._restart_dlsps()

    def _restart_dlsps(self) -> None:
        """Truncate stale detections and start a fresh DLSPS pipeline."""
        import os as _os  # noqa: PLC0415

        # Reset MQTT staleness tracking so we don't re-trigger immediately
        self._mqtt_last_ts = 0.0
        self._mqtt_fps_times = []
        self._mqtt_rppg_latest = None
        self._mqtt_action_latest = None

        # Truncate stale detections so PersonDetector reads fresh data
        try:
            _os.truncate(self._detections_path, 0)
        except Exception as exc:
            logger.warning("Could not truncate detections file: %s", exc)

        # Reset person detector file tracking but keep held detections
        # so the UI doesn't flash "not detected" during the brief gap
        if self._person_detector:
            self._person_detector.reset()

        # Restart DLSPS pipeline
        try:
            self.dlsps.stop()
        except Exception:
            pass
        try:
            pipeline_path = self._resolved_pipeline_path or ""
            ok, msg = self.dlsps.start(pipeline_path, self._user_config)
            logger.info("DLSPS restart: ok=%s msg=%s", ok, msg)
        except Exception as exc:
            logger.warning("Failed to restart DLSPS: %s", exc)

    def _get_local_fallback_frame(self) -> bytes | None:
        """Return a JPEG from configured video file when DLSPS frame API is absent.

        Some DLSPS builds expose status APIs but do not expose a frame endpoint.
        For end-to-end UI validation we fall back to the configured local video
        source and stream JPEGs from it.
        """
        if not self._video_path:
            return None
        try:
            import cv2  # noqa: PLC0415

            if self._local_video_cap is None:
                self._local_video_cap = cv2.VideoCapture(self._video_path)
                self._video_total_frames = int(
                    self._local_video_cap.get(cv2.CAP_PROP_FRAME_COUNT)
                )
            cap = self._local_video_cap
            if cap is None or not cap.isOpened():
                self._release_local_video_cap()
                return None

            # Detect end-of-video by frame position (cv2 doesn't always
            # return False at EOF for all codecs).
            pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            if pos >= self._video_total_frames - 1:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                if not self._video_looping:
                    self._video_looping = True
                    self._on_video_loop()

            ok, frame = cap.read()
            if not ok or frame is None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                if not self._video_looping:
                    self._video_looping = True
                    self._on_video_loop()
                ok, frame = cap.read()
            else:
                self._video_looping = False
            if not ok or frame is None:
                return None

            ok_enc, buf = cv2.imencode(".jpg", frame)
            if not ok_enc:
                return None
            return buf.tobytes()
        except Exception:
            return None

    def _get_rppg_pipeline(self) -> Any:
        """Lazy-create the rPPG pipeline after assets are confirmed present."""
        if self._rppg_pipeline is None and self._rppg_model_path:
            try:
                import sys, os  # noqa: E401
                sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
                from pipelines.nicu_rppg_custom import RppgPipeline  # noqa: PLC0415
                self._rppg_pipeline = RppgPipeline(
                    model_xml=self._rppg_model_path,
                    device=self.prepare_service.load_config()
                    .get("dlsps", {})
                    .get("device", "CPU"),
                )
            except Exception:
                pass  # pipeline unavailable; rPPG will emit idle status
        return self._rppg_pipeline

    def _read_dlsps_detections(self) -> list[dict]:
        """Convenience wrapper — returns detections only."""
        dets, _ = self._read_dlsps_detections_with_ts()
        return dets

    def _read_dlsps_detections_with_ts(self) -> tuple[list[dict], int]:
        """Read the latest detection line from DLSPS detections.jsonl.

        Returns (detections, timestamp_ns).  timestamp_ns is the GStreamer
        buffer timestamp in nanoseconds from the DLSPS output — it maps
        exactly to the video position that was analysed.

        Classification logic (mirrors direct-mode PersonDetector):
          1. Collect all "Patient" (patient-detect) boxes first.
          2. For each "person" box, if it overlaps a patient box (IoU > 0.3)
             drop it; otherwise label "caretaker".
          3. Latch detections are region-gated to the known latch area.
        """
        import os as _os  # noqa: PLC0415
        try:
            if not _os.path.exists(self._detections_path):
                return [], 0
            with open(self._detections_path, "rb") as f:
                f.seek(0, 2)
                fsize = f.tell()
                if fsize == 0:
                    return [], 0
                read_size = min(8192, fsize)
                f.seek(fsize - read_size)
                tail = f.read(read_size).decode("utf-8", errors="replace")

            lines = tail.strip().split("\n")
            if not lines:
                return [], 0

            last_line = lines[-1].strip()
            if not last_line:
                return [], 0

            # DLSPS writes a JSON array: first line starts with '[{',
            # subsequent lines are '{...},' (trailing comma), and the
            # final line is '{...}]'.  Strip leading '[' and trailing ','/']'
            # so we get a clean JSON object.
            last_line = last_line.lstrip("[").rstrip(",]").strip()
            if not last_line:
                return [], 0

            data = json.loads(last_line)
            objects = data.get("objects", [])
            ts_ns = int(data.get("timestamp", 0))

            dlsps_cfg = self.prepare_service.load_config().get("dlsps", {})
            thresholds = dlsps_cfg.get("thresholds", {})
            person_thresh = float(thresholds.get("patient_presence", 0.3))
            latch_thresh = float(thresholds.get("latch_detection", 0.2))

            patient_dets: list[dict] = []
            patient_boxes: list[list[float]] = []
            person_dets: list[dict] = []
            latch_dets: list[dict] = []

            for obj in objects:
                detection = obj.get("detection", {})
                confidence = float(detection.get("confidence", 0.0))
                roi_type = (obj.get("roi_type", "") or "").lower()
                bbox = detection.get("bounding_box", {})
                box = [
                    float(bbox.get("x_min", 0)),
                    float(bbox.get("y_min", 0)),
                    float(bbox.get("x_max", 0)),
                    float(bbox.get("y_max", 0)),
                ]

                if roi_type == "patient":
                    if confidence < person_thresh:
                        continue
                    patient_dets.append({"label": "patient", "bbox": box, "confidence": confidence})
                    patient_boxes.append(box)
                elif roi_type == "person":
                    if confidence < person_thresh:
                        continue
                    person_dets.append({"label": "caretaker", "bbox": box, "confidence": confidence})
                elif roi_type == "latch":
                    if confidence < latch_thresh:
                        continue
                    if box[3] < 0.25 and 0.20 <= box[0] <= 0.55:
                        latch_dets.append({"label": "latch", "bbox": box, "confidence": confidence})

            caretaker_dets: list[dict] = []
            for det in person_dets:
                overlaps_patient = False
                if patient_boxes:
                    for pbox in patient_boxes:
                        if self._iou(det["bbox"], pbox) > 0.3:
                            overlaps_patient = True
                            break
                if not overlaps_patient:
                    caretaker_dets.append(det)

            all_dets = patient_dets + caretaker_dets + latch_dets
            logger.info(
                "DLSPS parse: raw_objs=%d → patient=%d caretaker=%d latch=%d  labels=[%s]",
                len(objects), len(patient_dets), len(caretaker_dets), len(latch_dets),
                ", ".join(d["label"] for d in all_dets),
            )
            return all_dets, ts_ns
        except Exception:
            logger.debug("Failed to read DLSPS detections", exc_info=True)
            return [], 0

    @staticmethod
    def _iou(box_a: list[float], box_b: list[float]) -> float:
        """Compute IoU between two normalised [x_min, y_min, x_max, y_max] boxes."""
        x1 = max(box_a[0], box_b[0])
        y1 = max(box_a[1], box_b[1])
        x2 = min(box_a[2], box_b[2])
        y2 = min(box_a[3], box_b[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
        area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    def _parse_dlsps_objects(self, data: dict) -> list[dict]:
        """Parse a single DLSPS detection JSON message into labelled detections.

        Handles two formats:
          1. Direct gvametapublish: {"objects": [...], "timestamp": ...}
          2. MQTTPublisher metadata: may contain "objects" directly or
             nested under gva_meta messages. Also handles list-of-regions
             format from gvametaconvert.

        Classification logic:
          1. Collect all "Patient" boxes first.
          2. "person" boxes overlapping a patient (IoU > 0.3) are dropped;
             the rest become "caretaker".
          3. Latch detections are region-gated to the known latch area.
        """
        objects = data.get("objects", [])
        # MQTTPublisher may nest detections under gva_meta or resolution
        if not objects and "gva_meta" in data:
            gva = data["gva_meta"]
            if isinstance(gva, list):
                for item in gva:
                    objects.extend(item.get("objects", []))
            elif isinstance(gva, dict):
                objects = gva.get("objects", [])
        dlsps_cfg = self.prepare_service.load_config().get("dlsps", {})
        thresholds = dlsps_cfg.get("thresholds", {})
        person_thresh = float(thresholds.get("patient_presence", 0.3))
        latch_thresh = float(thresholds.get("latch_detection", 0.2))

        patient_dets: list[dict] = []
        patient_boxes: list[list[float]] = []
        person_dets: list[dict] = []
        latch_dets: list[dict] = []

        # Resolution from MQTTPublisher metadata (pixel coords → normalized)
        res = data.get("resolution", {})
        img_w = float(res.get("width", 1))
        img_h = float(res.get("height", 1))

        for obj in objects:
            roi_type = (obj.get("roi_type", "") or "").lower()

            # Two bbox formats:
            # A) gvametapublish: detection.bounding_box.{x_min,y_min,x_max,y_max} (normalized)
            # B) MQTTPublisher via gvametaconvert: {x,y,w,h} (pixels) at object root
            detection = obj.get("detection", {})
            bbox = detection.get("bounding_box", {})
            if bbox:
                confidence = float(detection.get("confidence", 0.0))
                box = [
                    float(bbox.get("x_min", 0)),
                    float(bbox.get("y_min", 0)),
                    float(bbox.get("x_max", 0)),
                    float(bbox.get("y_max", 0)),
                ]
            elif "x" in obj and "w" in obj:
                # MQTTPublisher pixel format — normalize
                confidence = float(obj.get("confidence", 1.0))
                px, py = float(obj["x"]), float(obj["y"])
                pw, ph = float(obj["w"]), float(obj["h"])
                box = [px / img_w, py / img_h, (px + pw) / img_w, (py + ph) / img_h]
            else:
                continue

            if roi_type == "patient":
                if confidence < person_thresh:
                    continue
                patient_dets.append({"label": "patient", "bbox": box, "confidence": confidence})
                patient_boxes.append(box)
            elif roi_type == "person":
                if confidence < person_thresh:
                    continue
                person_dets.append({"label": "caretaker", "bbox": box, "confidence": confidence})
            elif roi_type == "latch":
                if confidence < latch_thresh:
                    continue
                # Region gate: only accept latch clips in the top 15% of frame.
                # Bottom-of-frame detections (y_norm > 0.15) are false positives
                # from equipment edges.
                if box[1] > 0.15:
                    continue
                latch_dets.append({"label": "latch", "bbox": box, "confidence": confidence})

        caretaker_dets: list[dict] = []
        for det in person_dets:
            overlaps_patient = any(
                self._iou(det["bbox"], pbox) > 0.3 for pbox in patient_boxes
            )
            if not overlaps_patient:
                caretaker_dets.append(det)

        return patient_dets + caretaker_dets + latch_dets

    # ---- MQTT subscriber (used when inference_mode == "dlsps") ----

    def _start_mqtt_subscriber(self) -> None:
        """Connect to the MQTT broker and subscribe to the detections topic.

        Each message from DLSPS is a per-frame JSON identical to what
        ``gvametapublish`` writes to file.  We parse it immediately and
        cache the result for the inference loop to pick up.
        """
        try:
            import paho.mqtt.client as mqtt  # noqa: PLC0415
        except ImportError:
            logger.error("paho-mqtt not installed — cannot use DLSPS MQTT mode")
            return

        def on_connect(client: Any, userdata: Any, flags: Any, rc: int) -> None:
            if rc == 0:
                logger.info("MQTT connected to %s — subscribing to %s",
                            self._mqtt_broker, self._mqtt_topic)
                client.subscribe(self._mqtt_topic, qos=0)
            else:
                logger.error("MQTT connect failed rc=%d", rc)

        def on_message(client: Any, userdata: Any, msg: Any) -> None:
            try:
                data = json.loads(msg.payload.decode("utf-8", errors="replace"))
                # Official MQTTPublisher format: {"metadata": {...}, "blob": "<base64 JPEG>"}
                metadata = data.get("metadata", data)
                dets = self._parse_dlsps_objects(metadata)
                with self._mqtt_data_lock:
                    self._mqtt_latest_data = {"dets": dets, "ts": time.time(), "metadata": metadata}
                with self._cached_detections_lock:
                    self._cached_detections = dets
                # Extract rPPG data from MQTT metadata (from RppgCallback gvapython)
                rppg_data = metadata.get("rppg")
                if rppg_data and isinstance(rppg_data, dict):
                    self._mqtt_rppg_latest = rppg_data
                    if "inference_ms" in rppg_data:
                        self._workload_latency["rppg"] = float(rppg_data["inference_ms"])
                # Extract action recognition data from MQTT metadata
                action_data = metadata.get("action")
                if action_data and isinstance(action_data, dict):
                    self._mqtt_action_latest = action_data
                    if "inference_ms" in action_data:
                        self._workload_latency["action"] = float(action_data["inference_ms"])
                # Track MQTT message timing for staleness & FPS
                now = time.time()
                self._mqtt_last_ts = now
                self._mqtt_fps_times.append(now)
                # Keep last 30 timestamps for FPS window
                if len(self._mqtt_fps_times) > 30:
                    self._mqtt_fps_times = self._mqtt_fps_times[-30:]
                # Extract base64 JPEG frame from blob field
                blob = data.get("blob", "")
                if blob:
                    try:
                        frame_bytes = base64.b64decode(blob)
                        if frame_bytes:
                            # Annotate bounding boxes onto the frame (once per MQTT frame)
                            annotated = self._annotate_dlsps_detections(frame_bytes, dets) if dets else frame_bytes
                            with self._latest_raw_lock:
                                self._latest_raw_jpeg = frame_bytes
                                self._mqtt_frame_gen += 1
                            self.frame_service.update(annotated)
                    except Exception:
                        logger.debug("Failed to decode MQTT frame blob", exc_info=True)
            except Exception:
                logger.debug("Failed to parse MQTT detection message", exc_info=True)

        broker_host = self._mqtt_broker.split(":")[0]
        broker_port = int(self._mqtt_broker.split(":")[1]) if ":" in self._mqtt_broker else 1883

        client = mqtt.Client(client_id=self._mqtt_client_id, clean_session=True)
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect_async(broker_host, broker_port, keepalive=60)
        client.loop_start()  # non-blocking background thread
        self._mqtt_client = client
        logger.info("MQTT subscriber started (broker=%s topic=%s)",
                     self._mqtt_broker, self._mqtt_topic)

    def _stop_mqtt_subscriber(self) -> None:
        if self._mqtt_client is not None:
            try:
                self._mqtt_client.loop_stop()
                self._mqtt_client.disconnect()
            except Exception:
                pass
            self._mqtt_client = None

    def _annotate_dlsps_detections(self, jpeg: bytes, dets: list[dict]) -> bytes:
        """Draw bounding boxes from DLSPS detections onto a JPEG frame.

        Used in DLSPS mode where PersonDetector is not initialised.
        Boxes use normalised [0,1] coordinates from DLSPS output.
        """
        try:
            import cv2  # noqa: PLC0415
            import numpy as np  # noqa: PLC0415

            nparr = np.frombuffer(jpeg, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return jpeg

            h, w = frame.shape[:2]
            for det in dets:
                bbox = det.get("bbox", [0, 0, 0, 0])
                label = det.get("label", "person")
                x1 = int(bbox[0] * w)
                y1 = int(bbox[1] * h)
                x2 = int(bbox[2] * w)
                y2 = int(bbox[3] * h)
                if label == "patient":
                    color = (0, 255, 0)       # green
                elif label == "caretaker":
                    color = (0, 165, 255)     # orange
                else:
                    color = (255, 0, 255)     # magenta for latch
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, label, (x1, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            ok, buf = cv2.imencode(".jpg", frame)
            return buf.tobytes() if ok else jpeg
        except Exception:
            return jpeg

    @staticmethod
    def _stamp_watermark(jpeg: bytes) -> bytes:
        """Burn a small semi-transparent watermark into the bottom-right of the frame."""
        try:
            import cv2  # noqa: PLC0415
            import numpy as np  # noqa: PLC0415

            nparr = np.frombuffer(jpeg, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return jpeg

            h, w = frame.shape[:2]
            text = "Intel NICU Warmer | Edge AI Suite"
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 0.5
            thickness = 1
            (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)

            # Position: bottom-right with 10px padding
            x = w - tw - 12
            y = h - 10

            # Semi-transparent dark background for legibility
            overlay = frame.copy()
            cv2.rectangle(overlay, (x - 6, y - th - 4), (x + tw + 6, y + baseline + 4),
                          (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

            # White text
            cv2.putText(frame, text, (x, y), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)

            ok, buf = cv2.imencode(".jpg", frame)
            return buf.tobytes() if ok else jpeg
        except Exception:
            return jpeg

    def _frame_loop(self) -> None:
        """Grab video frames, draw cached bounding boxes, push to frame_service.

        direct/hybrid : read from local cv2.VideoCapture at 30 FPS
        dlsps         : read from MQTT-delivered frames (zero desync)

        Detection overlays come from ``_cached_detections`` which the
        inference loop updates at its own cadence:
          direct/hybrid : ~1 Hz  (OpenVINO on current frame)
          dlsps         : real-time via MQTT callback
        """
        frame_interval = 1.0 / 30
        dlsps_mode = self._inference_mode == "dlsps"
        logger.info("Frame loop: 30fps  mode=%s", self._inference_mode)

        last_served_gen = -1

        while not self._stop_event.is_set():
            try:
                if dlsps_mode:
                    # In DLSPS mode, annotation happens in MQTT callback.
                    # Frame loop only patches state on new frames.
                    with self._latest_raw_lock:
                        cur_gen = self._mqtt_frame_gen
                    if cur_gen != last_served_gen:
                        last_served_gen = cur_gen
                        self.state.patch({"frame": {"available": True, "timestamp": time.time()}})
                else:
                    jpeg = self._get_local_fallback_frame()
                    if jpeg:
                        with self._latest_raw_lock:
                            self._latest_raw_jpeg = jpeg
                    if jpeg:
                        with self._cached_detections_lock:
                            dets = list(self._cached_detections)
                        if dets and self._person_detector:
                            jpeg = self._person_detector.annotate_jpeg(jpeg, dets)
                        self.frame_service.update(jpeg)
                        self.state.patch({"frame": {"available": True, "timestamp": time.time()}})
            except Exception:
                logger.exception("Error in frame loop")
            self._stop_event.wait(frame_interval)

    def _inference_loop(self) -> None:
        """Slow loop: run detection and rPPG, update analytics state.

        direct/hybrid : runs OpenVINO models locally (~1 Hz)
        dlsps         : detections arrive via MQTT callback (already cached);
                        this loop just reads them and updates analytics + latch
        """
        current_latch = "unknown"
        LATCH_CLIP_THRESHOLD = 1
        # Sliding window: track latch counts from last N MQTT updates
        latch_window: list[int] = []  # recent latch-count-per-frame
        LATCH_WINDOW_SIZE = 15  # ~2s at 7fps
        LATCH_OPEN_RATIO = 0.5  # >50% frames have clips → open
        dlsps_mqtt = self._inference_mode == "dlsps"
        last_mqtt_gen_seen = -1  # track which MQTT frame we last processed
        logger.info("Inference loop: mode=%s", self._inference_mode)

        while not self._stop_event.is_set():
          try:
            # Grab the latest raw frame
            with self._latest_raw_lock:
                raw_jpeg = self._latest_raw_jpeg

            # Auto-restart DLSPS when detections go stale
            self._maybe_restart_dlsps()

            # Metrics: prefer MQTT-derived FPS in DLSPS mode, fall back to REST status
            mqtt_fps = 0.0
            if dlsps_mqtt and len(self._mqtt_fps_times) >= 2:
                span = self._mqtt_fps_times[-1] - self._mqtt_fps_times[0]
                if span > 0:
                    mqtt_fps = (len(self._mqtt_fps_times) - 1) / span

            ok, payload = self.dlsps.status()
            if not ok:
                payload = {
                    "runtime_status": "running",
                    "fps": 0.0,
                    "latency_ms": 0.0,
                    "frame_count": self._last_frame_count,
                }

            # DLSPS status API may not include frame_count; use MQTT gen counter instead
            if dlsps_mqtt:
                frame_count = self._mqtt_frame_gen
            else:
                frame_count = int(payload.get("frame_count", self._last_frame_count))
            loop_increment = 1 if frame_count < self._last_frame_count else 0
            self._last_frame_count = frame_count

            reported_fps = mqtt_fps if (dlsps_mqtt and mqtt_fps > 0) else float(payload.get("fps", 0.0) or 0.0)

            metrics_patch: dict[str, Any] = {
                "frame_count": frame_count,
                "fps": round(reported_fps, 2),
                "latency_ms": float(payload.get("latency_ms", 0.0) or 0.0),
                "runtime_status": "running",
            }
            if loop_increment:
                current_loop = int(self.state.snapshot()["metrics"].get("loop_count", 0))
                metrics_patch["loop_count"] = current_loop + loop_increment

            # --- Detection ---
            if dlsps_mqtt:
                # MQTT callback already cached detections in _cached_detections.
                # Just read the latest for analytics.
                with self._cached_detections_lock:
                    new_dets = list(self._cached_detections)
            elif self._person_detector and raw_jpeg:
                # direct / hybrid: local OpenVINO, frame-accurate
                new_dets = self._person_detector.detect(raw_jpeg)
            else:
                with self._cached_detections_lock:
                    new_dets = list(self._cached_detections)

            patient_detected = any(d["label"] == "patient" for d in new_dets)
            caretaker_detected = any(d["label"] == "caretaker" for d in new_dets)
            payload["patient_presence"] = patient_detected
            payload["caretaker_presence"] = caretaker_detected

            # Latch status
            latch_boxes: list[dict] = []
            if dlsps_mqtt:
                # Only update latch window when a new MQTT frame arrives
                cur_gen = self._mqtt_frame_gen
                if cur_gen != last_mqtt_gen_seen:
                    last_mqtt_gen_seen = cur_gen
                    latch_count = sum(1 for d in new_dets if d["label"] == "latch")
                    latch_window.append(latch_count)
                    if len(latch_window) > LATCH_WINDOW_SIZE:
                        latch_window = latch_window[-LATCH_WINDOW_SIZE:]
                # Decide based on sliding window majority
                # Clips detected at top of frame = latched (closed); no clips = open
                if len(latch_window) >= 3:
                    latched_frames = sum(1 for c in latch_window if c >= LATCH_CLIP_THRESHOLD)
                    ratio = latched_frames / len(latch_window)
                    current_latch = "closed" if ratio >= LATCH_OPEN_RATIO else "open"
            elif self._latch_detector and raw_jpeg:
                current_latch = self._latch_detector.detect(raw_jpeg)
                latch_boxes = self._latch_detector.last_clip_detections
            payload["latch_status"] = current_latch

            # Single atomic write: person + patient + latch boxes together
            if not dlsps_mqtt:
                with self._cached_detections_lock:
                    self._cached_detections = new_dets + latch_boxes

            # rPPG — prefer MQTT-delivered data from DLSPS gvapython, fallback to local
            rppg_output: dict[str, Any] | None = None
            if dlsps_mqtt and self._mqtt_rppg_latest:
                rppg_output = self._mqtt_rppg_latest
            else:
                pipeline = self._get_rppg_pipeline()
                if pipeline is not None and raw_jpeg:
                    try:
                        import numpy as np  # noqa: PLC0415
                        import cv2  # noqa: PLC0415
                        nparr = np.frombuffer(raw_jpeg, np.uint8)
                        frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if frame_bgr is not None:
                            rppg_output = pipeline.process([frame_bgr])
                    except Exception:
                        pass

            patch = self.aggregator.normalize(payload, rppg_output)
            patch["metrics"] = metrics_patch

            # Include action recognition data if available from DLSPS
            if dlsps_mqtt and self._mqtt_action_latest:
                patch.setdefault("analytics", {})["action"] = self._mqtt_action_latest

            # Pipeline performance: per-workload device + FPS + latency + status
            current_fps = patch.get("metrics", {}).get("fps", 0.0) or 0.0
            lc = self.lifecycle.state()
            pipe_status = "running" if lc == Lifecycle.RUNNING else "stopped"
            # Map workload display names to latency keys
            _latency_map = {
                "rPPG (MTTS-CAN)": "rppg",
                "Action Recognition": "action",
            }
            workloads_list = []
            for name, dev in (self._pipeline_devices or {}).items():
                latency_key = _latency_map.get(name)
                latency_ms = self._workload_latency.get(latency_key, 0.0) if latency_key else None
                w_entry: dict[str, Any] = {
                    "name": name,
                    "device": dev,
                    "status": pipe_status,
                    "fps": round(current_fps, 1),
                }
                if latency_ms is not None:
                    w_entry["latency_ms"] = round(latency_ms, 1)
                workloads_list.append(w_entry)

            patch["pipeline_performance"] = {
                "workloads": workloads_list,
                "pipeline_fps": round(current_fps, 1),
                "decode": "decodebin3 (VA-API HW)",
            }

            if self.lifecycle.state() == Lifecycle.STARTING:
                self.lifecycle.transition(Lifecycle.RUNNING)
                patch["lifecycle"] = Lifecycle.RUNNING.value

            self.state.patch(patch)

          except Exception:
            logger.exception("Error in inference loop")

          self._stop_event.wait(self._status_poll_interval_s)


def _compute_delta(
    prev: dict[str, Any], current: dict[str, Any]
) -> dict[str, Any]:
    """Recursively compute changed fields between two state snapshots.

    Only fields whose value changed are included in the result.
    Nested dicts are diffed recursively.  Non-dict scalar changes
    are emitted as-is.
    """
    delta: dict[str, Any] = {}
    for key, cur_val in current.items():
        prev_val = prev.get(key)
        if isinstance(cur_val, dict) and isinstance(prev_val, dict):
            sub = _compute_delta(prev_val, cur_val)
            if sub:
                delta[key] = sub
        elif cur_val != prev_val:
            delta[key] = cur_val
    return delta


def create_app(config_path: str) -> Flask:
    app = Flask(__name__)
    CORS(app)

    backend = MVPBackend(Path(config_path))
    backend.bootstrap()
    app.config["MVP_BACKEND"] = backend

    # Track NPU fallback and pending config changes
    backend._npu_fallback: dict = {}  # {workload_key: {"original": "NPU", "fallback": "CPU"}}
    backend._has_pending_changes = False

    @app.get("/health")
    def health() -> Response:
        lifecycle = backend.lifecycle.snapshot().lifecycle
        status = "healthy" if lifecycle != Lifecycle.ERROR.value else "degraded"
        return jsonify({"status": status, "lifecycle": lifecycle})

    @app.get("/readiness")
    def readiness() -> Response:
        snapshot = backend.state.snapshot()
        lifecycle = backend.lifecycle.snapshot()
        ready = lifecycle.lifecycle == Lifecycle.READY.value
        return jsonify(
            {
                "lifecycle": lifecycle.lifecycle,
                "ready": ready,
                "checks": snapshot["checks"],
                "errors": snapshot["errors"],
                "last_error": lifecycle.last_error,
            }
        )

    @app.get("/status")
    def status() -> Response:
        snapshot = backend.state.snapshot()
        snapshot["lifecycle"] = backend.lifecycle.snapshot().lifecycle
        return jsonify(snapshot)

    @app.post("/start")
    def start() -> Response:
        if not backend.lifecycle.start_transition():
            snap = backend.lifecycle.snapshot()
            return jsonify({
                "error": "Start allowed only in ready state",
                "lifecycle": snap.lifecycle,
                "last_error": snap.last_error,
            }), 409

        try:
            backend.state.patch(
                {
                    "lifecycle": Lifecycle.STARTING.value,
                    "metrics": {"runtime_status": "starting"},
                }
            )

            pipeline_path = backend._resolved_pipeline_path or ""

            # If user uploaded a video but didn't set a custom ROI, log a notice
            _uc = backend._user_config
            if _uc.get("video_file") and not _uc.get("roi_custom"):
                logger.info(
                    "User uploaded video '%s' without custom ROI — using default rPPG ROI",
                    _uc["video_file"],
                )

            ok, message = backend.dlsps.start(pipeline_path, backend._user_config)
            if not ok:
                # NPU fallback: if any device is set to NPU and start failed,
                # retry with CPU. We don't try to match specific error
                # keywords because OpenVINO/DLSPS surface NPU failures with
                # widely varying messages ("Failed to compile model",
                # "ZE_RESULT_*", "loading network", etc.).
                _uc_devs = backend._user_config.get("devices", {})
                npu_keys = [k for k, v in _uc_devs.items() if v == "NPU"]
                if npu_keys:
                    logger.warning(
                        "NPU start failed (%s), falling back to CPU for: %s",
                        message, npu_keys,
                    )
                    fallback_config = dict(backend._user_config)
                    fallback_devices = dict(fallback_config.get("devices", {}))
                    for k in npu_keys:
                        fallback_devices[k] = "CPU"
                    fallback_config["devices"] = fallback_devices
                    ok, message = backend.dlsps.start(pipeline_path, fallback_config)
                    if ok:
                        backend._npu_fallback = {
                            k: {"original": "NPU", "fallback": "CPU"} for k in npu_keys
                        }
                        backend._user_config["devices"] = fallback_devices
                    else:
                        backend._npu_fallback = {}
                else:
                    backend._npu_fallback = {}
                if not ok:
                    raise RuntimeError(message)
            else:
                backend._npu_fallback = {}

            # Capture per-model device assignments for the UI
            try:
                _devs = backend._user_config.get("devices", {})
                _det_dev = _devs.get("detect", "GPU")
                _rppg_dev = _devs.get("rppg", "CPU")
                _act_dev = _devs.get("action", "NPU")
                backend._pipeline_devices = {
                    "Person Detection": _det_dev,
                    "Patient Detection": _det_dev,
                    "Latch Detection": _det_dev,
                    "rPPG (MTTS-CAN)": _rppg_dev,
                    "Action Recognition": _act_dev,
                }
            except Exception:
                backend._pipeline_devices = {
                    "Person Detection": "GPU",
                    "Patient Detection": "GPU",
                    "Latch Detection": "GPU",
                    "rPPG (MTTS-CAN)": "CPU",
                    "Action Recognition": "NPU",
                }

            backend.start_status_poller()
            backend._has_pending_changes = False
            backend.state.patch(
                {
                    "lifecycle": Lifecycle.STARTING.value,
                    "metrics": {"runtime_status": "starting"},
                    "rppg": {"status": "active"},
                }
            )
            response_data: dict = {"status": "starting", "message": message}
            if backend._npu_fallback:
                response_data["fallback"] = backend._npu_fallback
            return jsonify(response_data)
        except Exception as exc:
            backend.lifecycle.mark_error(str(exc))
            backend.state.patch(
                {
                    "lifecycle": Lifecycle.ERROR.value,
                    "errors": [{"code": "START_ERROR", "message": str(exc)}],
                    "metrics": {"runtime_status": "error"},
                }
            )
            return jsonify({"error": str(exc)}), 500

    @app.post("/stop")
    def stop() -> Response:
        state = backend.lifecycle.state()
        # Allow stop from any "active" state (STARTING/RUNNING/ERROR) so the
        # user can always recover. If the pipeline is already idle, no-op.
        if state in {Lifecycle.READY, Lifecycle.PREPARING, Lifecycle.INITIALIZING}:
            return jsonify({"status": "noop", "message": "Backend is not running"})

        # Try to stop DLSPS but don't block the stop flow if it fails
        # (the pipeline may already be completed/aborted, or the start may
        # have failed mid-flight leaving us in ERROR).
        try:
            backend.dlsps.stop()
        except Exception as exc:
            logger.warning("DLSPS stop raised during /stop: %s", exc)

        try:
            backend.stop_status_poller()
        except Exception as exc:
            logger.warning("stop_status_poller raised during /stop: %s", exc)

        backend._last_frame_count = 0
        backend.frame_service.clear()

        # Force lifecycle back to READY regardless of current state. The
        # transition table now allows STARTING/RUNNING/ERROR -> READY.
        try:
            backend.lifecycle.transition(Lifecycle.READY)
        except ValueError:
            # Last-resort: if the transition is somehow disallowed, log and
            # leave state as-is rather than 500-ing the stop request.
            logger.error(
                "Could not transition lifecycle %s -> READY during /stop",
                backend.lifecycle.state().value,
            )
        backend.state.patch(
            {
                "lifecycle": Lifecycle.READY.value,
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
                    "pulse_waveform": [],
                    "resp_waveform": [],
                },
                "frame": {
                    "available": False,
                    "timestamp": None,
                },
                "metrics": {
                    "runtime_status": "ready",
                    "frame_count": 0,
                    "fps": 0.0,
                    "latency_ms": 0.0,
                    "loop_count": 0,
                },
            }
        )
        return jsonify({"status": "ready", "message": "stopped"})

    @app.get("/metrics")
    def metrics() -> Response:
        snap = backend.state.snapshot()
        m = snap["metrics"].copy()
        m["lifecycle"] = backend.lifecycle.snapshot().lifecycle
        return jsonify(m)

    @app.get("/hardware-metrics")
    def hardware_metrics() -> Response:
        """Proxy to the metrics-collector service (CPU/GPU/NPU/memory/power).

        Returns the raw payload from metrics-collector so the UI can render
        the same hardware performance panel as multi-modal patient monitoring.
        Falls back to an empty structure when the collector is not reachable.
        """
        import urllib.request  # noqa: PLC0415
        import urllib.error    # noqa: PLC0415
        cfg = backend.prepare_service.load_config()
        collector_url = cfg.get("metrics_collector", {}).get(
            "base_url", "http://localhost:9100"
        )
        MAX_POINTS = 120  # ~2 minutes of 1-second data
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            req = opener.open(f"{collector_url.rstrip('/')}/metrics", timeout=30)
            # Read in chunks to handle large payloads from long-running collectors
            chunks = []
            while True:
                chunk = req.read(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            data = json.loads(b"".join(chunks).decode())
            # Limit each time-series to the most recent MAX_POINTS entries
            # to prevent chart.js from choking on thousands of data points.
            for key in ("cpu_utilization", "gpu_utilization", "memory", "power", "npu_utilization"):
                if key in data and isinstance(data[key], list) and len(data[key]) > MAX_POINTS:
                    data[key] = data[key][-MAX_POINTS:]
            return jsonify(data)
        except Exception as exc:
            logger.warning("Metrics collector unreachable: %s", exc)
            return jsonify(
                {
                    "cpu_utilization": [],
                    "gpu_utilization": [],
                    "memory": [],
                    "power": [],
                    "npu_utilization": [],
                    "available": False,
                }
            )

    @app.get("/platform-info")
    def platform_info() -> Response:
        """Proxy platform-info from the metrics-collector service."""
        import urllib.request  # noqa: PLC0415
        import urllib.error    # noqa: PLC0415
        cfg = backend.prepare_service.load_config()
        collector_url = cfg.get("metrics_collector", {}).get(
            "base_url", "http://localhost:9100"
        )
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            req = opener.open(f"{collector_url.rstrip('/')}/platform-info", timeout=2)
            data = json.loads(req.read().decode())
            return jsonify(data)
        except Exception:
            return jsonify({"available": False})

    @app.get("/frame/latest")
    def frame_latest() -> Response:
        frame_bytes, is_fresh = backend.frame_service.get_latest()
        lifecycle = backend.lifecycle.snapshot().lifecycle

        if frame_bytes is None:
            return jsonify({"available": False, "fresh": False, "message": "No frame available"}), 200

        # Serve last-known frame even when stale so the UI doesn't flicker to
        # hard errors during short ingest gaps.  Clients can use `fresh` to
        # decide whether to overlay a stale indicator.
        if lifecycle not in {"starting", "running"}:
            return jsonify(
                {
                    "available": True,
                    "fresh": False,
                    "message": "Using last available frame",
                    "lifecycle": lifecycle,
                }
            ), 200

        if request.args.get("base64") == "1":
            return jsonify(
                {
                    "available": True,
                    "fresh": is_fresh,
                    "data": base64.b64encode(frame_bytes).decode("ascii"),
                    "content_type": "image/jpeg",
                }
            )

        return Response(frame_bytes, mimetype="image/jpeg")

    @app.get("/video_feed")
    def video_feed() -> Response:
        """MJPEG stream — drains FrameService and pushes annotated frames to the
        browser as multipart/x-mixed-replace so React can use a plain <img> tag."""

        def _placeholder_jpeg() -> bytes:
            """Generate a small black placeholder JPEG when no real frame is available."""
            try:
                import cv2 as _cv2  # noqa: PLC0415
                import numpy as _np  # noqa: PLC0415
                black = _np.zeros((480, 640, 3), dtype=_np.uint8)
                _cv2.putText(black, "Waiting for video...", (140, 250),
                             _cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
                ok, buf = _cv2.imencode(".jpg", black)
                return buf.tobytes() if ok else b""
            except Exception:
                return b""

        def generate():
            placeholder = _placeholder_jpeg()
            while True:
                frame_bytes, _ = backend.frame_service.get_latest()
                if not frame_bytes:
                    frame_bytes = placeholder
                if frame_bytes:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + frame_bytes
                        + b"\r\n"
                    )
                time.sleep(0.05)  # cap at ~20 FPS

        return Response(
            generate(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.get("/events")
    def events() -> Response:
        def event_stream() -> Iterator[str]:
            last_snapshot: dict[str, Any] | None = None
            ticks_since_full = 0
            HEARTBEAT_EVERY = 10  # ticks

            while True:
                seq = backend.next_event_seq()
                current = backend.state.snapshot()
                current["lifecycle"] = backend.lifecycle.snapshot().lifecycle

                # Every HEARTBEAT_EVERY ticks emit a full snapshot so
                # reconnecting clients always converge quickly.
                if last_snapshot is None or ticks_since_full >= HEARTBEAT_EVERY:
                    event_type = "full"
                    payload = current
                    ticks_since_full = 0
                else:
                    delta = _compute_delta(last_snapshot, current)
                    if delta:
                        event_type = "delta"
                        payload = delta
                    else:
                        # Nothing changed: still emit a heartbeat ping
                        ticks_since_full += 1
                        time.sleep(1.0)
                        continue

                last_snapshot = copy.deepcopy(current)
                ticks_since_full += 1

                data = json.dumps(payload)
                yield f"id: {seq}\n"
                yield f"event: {event_type}\n"
                yield f"data: {data}\n\n"
                time.sleep(1.0)

        return Response(event_stream(), mimetype="text/event-stream")

    # ── Configuration endpoints (set before starting pipeline) ───────

    ALLOWED_VIDEO_EXT = {".mp4", ".avi", ".mkv", ".mov", ".ts"}
    MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB

    @app.post("/config/video")
    def config_video_upload() -> Response:
        """Upload a video file to use as pipeline source."""
        if "file" not in request.files:
            return jsonify({"error": "No file part in request"}), 400
        f = request.files["file"]
        if not f.filename:
            return jsonify({"error": "No file selected"}), 400

        import os as _os  # noqa: PLC0415
        from werkzeug.utils import secure_filename as _sf  # noqa: PLC0415

        safe_name = _sf(f.filename)
        ext = _os.path.splitext(safe_name)[1].lower()
        if ext not in ALLOWED_VIDEO_EXT:
            return jsonify({"error": f"Invalid file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_VIDEO_EXT))}"}), 400

        upload_dir = Path(backend.config_path).parent.parent / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        dest = upload_dir / safe_name

        # Stream-save with size check
        written = 0
        with dest.open("wb") as out:
            while True:
                chunk = f.stream.read(8192)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    out.close()
                    dest.unlink(missing_ok=True)
                    return jsonify({"error": f"File exceeds {MAX_UPLOAD_BYTES // (1024*1024)} MB limit"}), 413
                out.write(chunk)

        backend._user_config["video_file"] = safe_name
        if backend.lifecycle.state() in {Lifecycle.STARTING, Lifecycle.RUNNING}:
            backend._has_pending_changes = True
        logger.info("Video uploaded: %s (%d bytes)", safe_name, written)
        return jsonify({"status": "ok", "video_file": safe_name, "size_bytes": written, "pending": backend._has_pending_changes})

    @app.delete("/config/video")
    def config_video_clear() -> Response:
        """Clear uploaded video — revert to default."""
        backend._user_config["video_file"] = None
        if backend.lifecycle.state() in {Lifecycle.STARTING, Lifecycle.RUNNING}:
            backend._has_pending_changes = True
        return jsonify({"status": "ok", "video_file": None, "pending": backend._has_pending_changes})

    @app.get("/config/video")
    def config_video_get() -> Response:
        return jsonify({
            "video_file": backend._user_config.get("video_file"),
            "default_video": "Warmer_Testbed_YTHD.mp4",
        })

    @app.post("/config/roi")
    def config_roi_set() -> Response:
        """Set rPPG face ROI (normalised 0-1 coordinates)."""
        data = request.get_json(silent=True) or {}
        try:
            roi = {
                "top": float(data["top"]),
                "left": float(data["left"]),
                "bottom": float(data["bottom"]),
                "right": float(data["right"]),
            }
            for k, v in roi.items():
                if not (0.0 <= v <= 1.0):
                    return jsonify({"error": f"ROI '{k}' must be between 0 and 1, got {v}"}), 400
            if roi["top"] >= roi["bottom"] or roi["left"] >= roi["right"]:
                return jsonify({"error": "ROI top must be < bottom and left must be < right"}), 400
        except (KeyError, TypeError, ValueError) as exc:
            return jsonify({"error": f"Invalid ROI data: {exc}. Provide top, left, bottom, right (0-1)."}), 400
        backend._user_config["roi"] = roi
        backend._user_config["roi_custom"] = True
        if backend.lifecycle.state() in {Lifecycle.STARTING, Lifecycle.RUNNING}:
            backend._has_pending_changes = True
        return jsonify({"status": "ok", "roi": roi, "pending": backend._has_pending_changes})

    @app.delete("/config/roi")
    def config_roi_clear() -> Response:
        """Reset ROI to defaults."""
        backend._user_config["roi"] = {"top": 0.10, "left": 0.30, "bottom": 0.56, "right": 0.70}
        backend._user_config["roi_custom"] = False
        if backend.lifecycle.state() in {Lifecycle.STARTING, Lifecycle.RUNNING}:
            backend._has_pending_changes = True
        return jsonify({"status": "ok", "roi": backend._user_config["roi"], "pending": backend._has_pending_changes})

    @app.get("/config/roi")
    def config_roi_get() -> Response:
        return jsonify({
            "roi": backend._user_config.get("roi"),
            "custom": backend._user_config.get("roi_custom", False),
        })

    @app.post("/config/devices")
    def config_devices_set() -> Response:
        """Set per-model device assignments (CPU/GPU/NPU)."""
        data = request.get_json(silent=True) or {}
        allowed = {"CPU", "GPU", "NPU"}
        devices = backend._user_config["devices"].copy()
        for key in ("detect", "rppg", "action"):
            if key in data:
                val = str(data[key]).upper()
                if val not in allowed:
                    return jsonify({"error": f"Invalid device '{val}' for {key}. Allowed: {sorted(allowed)}"}), 400
                devices[key] = val
        backend._user_config["devices"] = devices
        if backend.lifecycle.state() in {Lifecycle.STARTING, Lifecycle.RUNNING}:
            backend._has_pending_changes = True
        return jsonify({"status": "ok", "devices": devices, "pending": backend._has_pending_changes})

    @app.get("/config/devices")
    def config_devices_get() -> Response:
        return jsonify({"devices": backend._user_config.get("devices")})

    @app.get("/config/devices/available")
    def config_devices_available() -> Response:
        """Probe host for available accelerators."""
        import os as _os  # noqa: PLC0415
        available: dict[str, bool] = {"CPU": True}
        try:
            dri = _os.listdir("/dev/dri") if _os.path.isdir("/dev/dri") else []
            available["GPU"] = any(f.startswith("renderD") for f in dri)
        except OSError:
            available["GPU"] = False
        try:
            accel = _os.listdir("/dev/accel") if _os.path.isdir("/dev/accel") else []
            available["NPU"] = len(accel) > 0
        except OSError:
            available["NPU"] = False
        return jsonify({"devices": available})

    @app.post("/config/apply")
    def config_apply() -> Response:
        """Apply pending config changes by restarting the pipeline."""
        state = backend.lifecycle.state()
        # Treat ERROR like STARTING/RUNNING for the purpose of recovery —
        # stop whatever's left over and restart with the new config.
        if state in {Lifecycle.STARTING, Lifecycle.RUNNING, Lifecycle.ERROR}:
            # Stop current pipeline (best-effort; pipeline may already be down)
            try:
                backend.dlsps.stop()
            except Exception as exc:
                logger.warning("DLSPS stop raised during /config/apply: %s", exc)
            try:
                backend.stop_status_poller()
            except Exception as exc:
                logger.warning("stop_status_poller raised during /config/apply: %s", exc)
            backend._last_frame_count = 0
            backend.frame_service.clear()
            try:
                backend.lifecycle.transition(Lifecycle.READY)
            except ValueError:
                logger.error(
                    "Could not transition lifecycle %s -> READY during /config/apply",
                    backend.lifecycle.state().value,
                )

            # Re-start with updated config
            if not backend.lifecycle.start_transition():
                backend._has_pending_changes = False
                return jsonify({"status": "error", "message": "Failed to transition to starting state"}), 500

            try:
                pipeline_path = backend._resolved_pipeline_path or ""
                ok, message = backend.dlsps.start(pipeline_path, backend._user_config)
                if not ok:
                    # NPU fallback on restart too (always retry on CPU when
                    # any NPU device was requested; see /start for rationale).
                    _uc_devs = backend._user_config.get("devices", {})
                    npu_keys = [k for k, v in _uc_devs.items() if v == "NPU"]
                    if npu_keys:
                        logger.warning("NPU failed on apply (%s), falling back to CPU", message)
                        fallback_config = dict(backend._user_config)
                        fallback_devices = dict(fallback_config.get("devices", {}))
                        for k in npu_keys:
                            fallback_devices[k] = "CPU"
                        fallback_config["devices"] = fallback_devices
                        ok, message = backend.dlsps.start(pipeline_path, fallback_config)
                        if ok:
                            backend._npu_fallback = {
                                k: {"original": "NPU", "fallback": "CPU"} for k in npu_keys
                            }
                            backend._user_config["devices"] = fallback_devices
                    if not ok:
                        raise RuntimeError(message)

                # Update device assignments for UI
                _devs = backend._user_config.get("devices", {})
                backend._pipeline_devices = {
                    "Person Detection": _devs.get("detect", "GPU"),
                    "Patient Detection": _devs.get("detect", "GPU"),
                    "Latch Detection": _devs.get("detect", "GPU"),
                    "rPPG (MTTS-CAN)": _devs.get("rppg", "CPU"),
                    "Action Recognition": _devs.get("action", "NPU"),
                }
                backend.start_status_poller()
                backend._has_pending_changes = False
                backend.state.patch({
                    "lifecycle": Lifecycle.STARTING.value,
                    "metrics": {"runtime_status": "starting"},
                    "rppg": {"status": "active"},
                })
                return jsonify({"status": "restarting", "message": "Pipeline restarted with new config"})
            except Exception as exc:
                backend.lifecycle.mark_error(str(exc))
                backend._has_pending_changes = False
                return jsonify({"error": str(exc)}), 500
        else:
            # Not running — config already stored, will apply on next start
            backend._has_pending_changes = False
            return jsonify({"status": "applied", "message": "Config saved, will apply on next start"})

    @app.get("/config")
    def config_get() -> Response:
        """Get full user configuration state."""
        uc = backend._user_config
        return jsonify({
            "video_file": uc.get("video_file"),
            "default_video": "Warmer_Testbed_YTHD.mp4",
            "roi": uc.get("roi"),
            "roi_custom": uc.get("roi_custom", False),
            "devices": uc.get("devices"),
            "pending": backend._has_pending_changes,
            "fallback": backend._npu_fallback if backend._npu_fallback else None,
        })

    @app.get("/device-profile")
    def device_profile_get() -> Response:
        """Return active device assignments and the resolved pipeline optimizations.

        Uses the current user_config device selections (same as what the UI
        sets via /config/devices) and resolves the optimal decode, pre-process,
        and inference settings via the device_profiles lookup.
        """
        from backend_mvp.device_profiles import resolve_pipeline_settings as _resolve

        user_devs = backend._user_config.get("devices", {})
        # Use user-selected devices, fall back to env profile defaults
        devices = {
            "detect": user_devs.get("detect", os.environ.get("DETECTION_DEVICE", "GPU")),
            "rppg": user_devs.get("rppg", os.environ.get("RPPG_DEVICE", "CPU")),
            "action": user_devs.get("action", os.environ.get("ACTION_DEVICE", "NPU")),
        }
        resolved = _resolve(devices)

        # If DLSPS controller has resolved settings from last pipeline start, prefer those
        dlsps_resolved = getattr(backend.dlsps, "_resolved_settings", None)
        if dlsps_resolved:
            resolved = dlsps_resolved

        return jsonify({
            "devices": {
                "detection": resolved["detect_device"],
                "rppg": resolved["rppg_device"],
                "action": resolved["action_device"],
            },
            "optimizations": {
                "decode": resolved["decode"],
                "pre_process": resolved["pre_process"],
                "detection_options": resolved["detect"].get("inference_options", ""),
                "detection_precision": resolved["detect"].get("precision", "FP32"),
                "rppg_precision": resolved["rppg"].get("precision", "FP32"),
                "action_precision": resolved["action"].get("precision", "FP32"),
            },
            "deployment_profile": os.environ.get("DEVICE_PROFILE", "mixed-optimized"),
            "available_profiles": ["all-cpu", "all-gpu", "all-npu", "mixed-optimized"],
        })

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NICU Warmer MVP Backend")
    parser.add_argument(
        "--config",
        default="configs/mvp-backend.yaml",
        help="Path to MVP backend config file",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host interface")
    parser.add_argument("--port", type=int, default=5001, help="Port")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()
    app = create_app(args.config)
    app.run(host=args.host, port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
