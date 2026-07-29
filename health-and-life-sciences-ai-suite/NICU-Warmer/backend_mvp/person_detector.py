"""Frame-accurate person and patient detection via OpenVINO.

Runs person-detect-fp32 and patient-detect-fp32 directly in the backend
to produce frame-synchronized bounding boxes and classification.

Previous approach read DLSPS detections.jsonl which was always desynced
from the backend's own video reader — causing ghost detections, wrong
bounding-box positions, and stale patient/caretaker status.

Now: all inference runs locally at 1 Hz (status-poll cadence).  The 30 fps
frame loop only *draws* the last known detections (fast, no inference).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class PersonDetector:
    """Direct OpenVINO inference for person + patient detection.

    Uses two models:
      - person-detect-fp32  → finds all persons in the frame
      - patient-detect-fp32 → finds the patient (infant) specifically

    Classification:
      - A person bbox that overlaps (IoU > 0.3) with a patient bbox → "patient"
      - A person bbox with no patient overlap → "caretaker"
      - A patient bbox with no person overlap → "patient" (fallback)
    """

    INPUT_H, INPUT_W = 800, 992  # model input resolution
    MAX_BBOX_AREA = 0.40          # reject full-frame artifacts

    def __init__(
        self,
        person_model_xml: str,
        patient_model_xml: str,
        confidence: float = 0.30,
        device: str = "CPU",
    ) -> None:
        self._person_model_xml = person_model_xml
        self._patient_model_xml = patient_model_xml
        self._confidence = confidence
        self._device = device
        self._person_engine: Any = None
        self._patient_engine: Any = None
        self._last_detections: list[dict] = []

    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        return Path(self._person_model_xml).exists()

    # ------------------------------------------------------------------
    def _ensure_loaded(self) -> None:
        if self._person_engine is not None:
            return
        try:
            import openvino as ov  # noqa: PLC0415
            core = ov.Core()
            available = core.available_devices
            device = self._device if self._device in available else "CPU"
            if device != self._device:
                logger.warning(
                    "Device %s not available (%s), falling back to CPU",
                    self._device, available,
                )
            self._person_engine = core.compile_model(self._person_model_xml, device)
            self._patient_engine = core.compile_model(self._patient_model_xml, device)
            logger.info(
                "PersonDetector loaded (person + patient) on %s", device
            )
        except Exception:
            logger.exception("Failed to load person/patient models")

    # ------------------------------------------------------------------
    @staticmethod
    def _preprocess(frame: np.ndarray) -> np.ndarray:
        resized = cv2.resize(frame, (PersonDetector.INPUT_W, PersonDetector.INPUT_H))
        blob = resized.transpose(2, 0, 1).astype(np.float32) / 255.0
        return np.expand_dims(blob, 0)

    def _run_model(self, engine: Any, blob: np.ndarray) -> list[dict]:
        result = engine({0: blob})
        boxes = result[engine.output(0)].squeeze(0)  # [N, 5]
        detections: list[dict] = []
        for box in boxes:
            conf = float(box[4])
            if conf < self._confidence:
                continue
            # Normalize pixel coords → [0, 1]
            x1 = float(box[0]) / self.INPUT_W
            y1 = float(box[1]) / self.INPUT_H
            x2 = float(box[2]) / self.INPUT_W
            y2 = float(box[3]) / self.INPUT_H
            area = (x2 - x1) * (y2 - y1)
            if area > self.MAX_BBOX_AREA or area < 0.001:
                continue
            detections.append({
                "confidence": conf,
                "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
            })
        return detections

    @staticmethod
    def _iou(a: dict, b: dict) -> float:
        ix1 = max(a["x1"], b["x1"])
        iy1 = max(a["y1"], b["y1"])
        ix2 = min(a["x2"], b["x2"])
        iy2 = min(a["y2"], b["y2"])
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        aa = (a["x2"] - a["x1"]) * (a["y2"] - a["y1"])
        ab = (b["x2"] - b["x1"]) * (b["y2"] - b["y1"])
        union = aa + ab - inter
        return inter / union if union > 0 else 0.0

    # ------------------------------------------------------------------
    def detect(self, jpeg: bytes) -> list[dict]:
        """Run person + patient inference on a JPEG frame.

        Returns list of ``{"label": "patient"|"caretaker", "confidence": float,
        "bbox": {"x1","y1","x2","y2"}}`` in normalised [0,1] coordinates.
        """
        self._ensure_loaded()
        if self._person_engine is None:
            return self._last_detections

        nparr = np.frombuffer(jpeg, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return self._last_detections

        blob = self._preprocess(frame)
        person_dets = self._run_model(self._person_engine, blob)
        patient_dets = self._run_model(self._patient_engine, blob)

        detections: list[dict] = []
        matched_patient_idxs: set[int] = set()

        for pdet in person_dets:
            is_patient = False
            for pi, patdet in enumerate(patient_dets):
                if self._iou(pdet["bbox"], patdet["bbox"]) > 0.3:
                    is_patient = True
                    matched_patient_idxs.add(pi)
                    break
            detections.append({
                "label": "patient" if is_patient else "caretaker",
                "confidence": pdet["confidence"],
                "bbox": pdet["bbox"],
            })

        # Patient detections not matched by person-detect (fallback)
        for pi, patdet in enumerate(patient_dets):
            if pi not in matched_patient_idxs:
                detections.append({
                    "label": "patient",
                    "confidence": patdet["confidence"],
                    "bbox": patdet["bbox"],
                })

        self._last_detections = detections
        return detections

    # ------------------------------------------------------------------
    def annotate(self, frame: np.ndarray, detections: list[dict]) -> np.ndarray:
        """Draw bounding boxes and labels on a BGR frame (in-place)."""
        h, w = frame.shape[:2]
        for det in detections:
            bb = det["bbox"]
            x1, y1 = int(bb["x1"] * w), int(bb["y1"] * h)
            x2, y2 = int(bb["x2"] * w), int(bb["y2"] * h)
            # Green for patient, orange for caretaker, magenta for latch
            if det["label"] == "patient":
                color = (0, 255, 0)
            elif det["label"] == "latch":
                color = (255, 0, 255)
            else:
                color = (0, 165, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f'{det["label"]} {det["confidence"]:.0%}'
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw, y1), color, -1)
            cv2.putText(
                frame, label, (x1, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA,
            )
        return frame

    def detect_and_annotate(self, jpeg: bytes) -> tuple[bytes, list[dict]]:
        """Convenience: detect + annotate in one call."""
        detections = self.detect(jpeg)
        if not detections:
            return jpeg, []

        nparr = np.frombuffer(jpeg, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return jpeg, detections

        self.annotate(frame, detections)
        ok, buf = cv2.imencode(".jpg", frame)
        return (buf.tobytes() if ok else jpeg), detections

    def annotate_jpeg(self, jpeg: bytes, detections: list[dict]) -> bytes:
        """Draw stored detections on a JPEG frame (no inference)."""
        if not detections:
            return jpeg
        nparr = np.frombuffer(jpeg, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return jpeg
        self.annotate(frame, detections)
        ok, buf = cv2.imencode(".jpg", frame)
        return buf.tobytes() if ok else jpeg

    # ------------------------------------------------------------------
    def close(self) -> None:
        self._last_detections = []

    def reset(self) -> None:
        self._last_detections = []
