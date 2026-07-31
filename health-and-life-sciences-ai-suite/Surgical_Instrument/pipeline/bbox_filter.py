"""gvapython callback to drop bogus over-sized ROIs before tracking/drawing.

yolo11n occasionally emits a low-confidence detection whose bounding-box
covers most of the frame (a class-collapse artefact seen at frame boundaries
and when the endoscope de-focuses). Those boxes get a track_id from
`gvatrack`, get drawn by `gvawatermark`, and pollute the JSON going out on
MQTT. We drop any ROI whose area exceeds MAX_AREA_FRAC of the frame here,
between gvadetect and gvatrack.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("bbox_filter")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class BBoxFilter:
    def __init__(self,
                 max_area_frac: float | None = None,
                 max_dim_frac: float | None = None) -> None:
        self._max_area = float(os.environ.get("BBOX_MAX_AREA_FRAC",
                                              max_area_frac if max_area_frac is not None else 0.6))
        self._max_dim = float(os.environ.get("BBOX_MAX_DIM_FRAC",
                                             max_dim_frac if max_dim_frac is not None else 0.85))
        self._dropped = 0
        log.info("BBoxFilter: max_area=%.2f max_dim=%.2f", self._max_area, self._max_dim)

    def process_frame(self, frame) -> bool:
        try:
            for region in list(frame.regions()):
                rect = region.normalized_rect()
                w = float(rect.w)
                h = float(rect.h)
                area = w * h
                if area > self._max_area or w > self._max_dim or h > self._max_dim:
                    frame.remove_region(region)
                    self._dropped += 1
                    if self._dropped % 50 == 1:
                        log.info("BBoxFilter: dropped %d oversize ROIs (last w=%.2f h=%.2f area=%.2f)",
                                 self._dropped, w, h, area)
        except Exception as exc:  # noqa: BLE001
            log.debug("bbox filter failed: %s", exc)
        return True
