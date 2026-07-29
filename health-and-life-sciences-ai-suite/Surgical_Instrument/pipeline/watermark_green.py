"""gvapython callback in the JPEG-encode branch. Draws a single-color
green bounding box + confidence value for every detection region.
Replaces `gvawatermark`'s per-track-ID rainbow with one consistent
medical-neutral green so the surgical UI shows a uniform highlight for
every polyp regardless of tracker ID or class.

The element is named `drawer` in the pipeline so
`backend/consumer/latency_tail.py`'s processing-chain sum finds its
element-latency ticks in the tracer log.
"""
from __future__ import annotations

import logging
import os

import cv2

log = logging.getLogger("green_watermark")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# BGR — bright but not fluorescent; reads clearly over pink/red endoscopic
# tissue without dominating the frame.
_COLOR = (0, 200, 0)
_THICKNESS = int(os.environ.get("BBOX_THICKNESS", "3"))
_FONT = cv2.FONT_HERSHEY_SIMPLEX
_FONT_SCALE = float(os.environ.get("BBOX_FONT_SCALE", "0.7"))
_FONT_THICKNESS = 2


class GreenWatermark:
    def __init__(self) -> None:
        log.info(
            "GreenWatermark: color(BGR)=%s thickness=%d font_scale=%.2f",
            _COLOR, _THICKNESS, _FONT_SCALE,
        )

    def process_frame(self, frame) -> bool:
        try:
            with frame.data() as mat:
                for region in frame.regions():
                    rect = region.rect()
                    x, y = int(rect.x), int(rect.y)
                    w, h = int(rect.w), int(rect.h)
                    cv2.rectangle(mat, (x, y), (x + w, y + h), _COLOR, _THICKNESS)
                    try:
                        conf = float(region.confidence())
                    except Exception:  # noqa: BLE001
                        conf = 0.0
                    label = f"{conf:.2f}"
                    (_, th), _base = cv2.getTextSize(
                        label, _FONT, _FONT_SCALE, _FONT_THICKNESS
                    )
                    ty = max(y - 6, th + 4)
                    cv2.putText(
                        mat, label, (x, ty), _FONT, _FONT_SCALE,
                        _COLOR, _FONT_THICKNESS, cv2.LINE_AA,
                    )
        except Exception as exc:  # noqa: BLE001
            log.debug("green watermark failed: %s", exc)
        return True
