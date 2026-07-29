"""Run latch-detect-fp32 via OpenVINO to detect warmer latch state.

The model detects individual latch *clips* at the four corners of the warmer
hood.  When the clips are visible (detected) the hood is latched **closed**.
When no clips are detected, the hood is **open** (unlatched).

Decision rule:
  - detections >= CLIP_THRESHOLD  →  **closed**  (clips visible / latched)
  - detections <  CLIP_THRESHOLD  →  **open**    (clips absent / unlatched)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class LatchDetector:
    """Count-based latch detection via OpenVINO.

    Uses asymmetric hysteresis so the latch state is sticky:
      - closed → open : 2 consecutive "open" readings  (responsive)
      - open → closed  : 5 consecutive "closed" readings (resistant to
        false flips caused by scene changes such as a person leaving)
    """

    CLIP_THRESHOLD = 1        # ≥1 clip visible ➜ open (clips exposed = unlatched)
    CONFIRM_TO_OPEN = 2       # consecutive "open"  readings to transition
    CONFIRM_TO_CLOSE = 3      # consecutive "closed" readings to transition

    def __init__(self, model_xml: str, confidence: float = 0.20, device: str = "CPU") -> None:
        self._model_xml = model_xml
        self._confidence = confidence
        self._device = device
        self._engine: Any = None
        self._last_state: str = "unknown"
        self._run_count: int = 0   # consecutive same-raw-reading count
        self._run_value: str = "unknown"  # the raw value being counted
        self._last_clip_detections: list[dict] = []

    # ------------------------------------------------------------------
    @property
    def last_clip_detections(self) -> list[dict]:
        """Bounding boxes from the most recent inference."""
        return self._last_clip_detections

    def reset(self) -> None:
        """Clear detection history for a fresh session."""
        self._last_state = "unknown"
        self._run_count = 0
        self._run_value = "unknown"
        self._last_clip_detections = []

    # ------------------------------------------------------------------
    def _get_engine(self) -> Any:
        if self._engine is None:
            if not Path(self._model_xml).exists():
                logger.warning("Latch model not found: %s", self._model_xml)
                return None
            try:
                import openvino as ov  # noqa: PLC0415
                core = ov.Core()
                available = core.available_devices
                device = self._device if self._device in available else "CPU"
                if device != self._device:
                    logger.warning(
                        "Latch: device %s not available (%s), falling back to CPU",
                        self._device, available,
                    )
                self._engine = core.compile_model(self._model_xml, device)
                logger.info("Latch detector loaded: %s on %s", self._model_xml, device)
            except Exception:
                logger.exception("Failed to load latch model")
                return None
        return self._engine

    # ------------------------------------------------------------------
    def detect(self, jpeg: bytes) -> str:
        """Run latch detection on a JPEG frame.

        Returns ``"open"`` or ``"closed"``.
        """
        engine = self._get_engine()
        if engine is None:
            return self._last_state

        try:
            nparr = np.frombuffer(jpeg, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return self._last_state

            h, w = 800, 992
            resized = cv2.resize(frame, (w, h))
            blob = resized.transpose(2, 0, 1).astype(np.float32) / 255.0
            blob = np.expand_dims(blob, 0)

            result = engine({0: blob})
            boxes = result[engine.output(0)].squeeze(0)  # [N, 5]

            clip_dets: list[dict] = []
            for box in boxes:
                conf = float(box[4])
                if conf < self._confidence:
                    continue
                clip_dets.append({
                    "label": "latch",
                    "confidence": conf,
                    "bbox": {
                        "x1": float(box[0]) / w,
                        "y1": float(box[1]) / h,
                        "x2": float(box[2]) / w,
                        "y2": float(box[3]) / h,
                    },
                })
            self._last_clip_detections = clip_dets
            clip_count = len(clip_dets)

            raw = "closed" if clip_count >= self.CLIP_THRESHOLD else "open"

            # Asymmetric hysteresis: track consecutive same-value runs.
            if raw == self._run_value:
                self._run_count += 1
            else:
                self._run_value = raw
                self._run_count = 1

            if self._last_state == "unknown":
                # First reading — accept immediately
                self._last_state = raw
            elif raw != self._last_state:
                needed = (self.CONFIRM_TO_CLOSE
                          if raw == "closed"
                          else self.CONFIRM_TO_OPEN)
                if self._run_count >= needed:
                    self._last_state = raw

            logger.info("Latch: clips=%d raw=%s run=%d → %s",
                        clip_count, raw, self._run_count, self._last_state)
            return self._last_state

        except Exception:
            logger.exception("Latch detection failed")
            return self._last_state
