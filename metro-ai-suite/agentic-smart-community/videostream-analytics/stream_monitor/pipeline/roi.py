"""ROI crop helpers for stream_monitor.

Used after prefilter passes: the trajectory_region_xyxy returned by
YoloPrefilter.filter() defines an axis-aligned bounding box covering all
detections across the segment. This module rewrites the segment mp4 to a
cropped/highlighted variant that the VLM can focus on.

Three modes:
    crop            - crop to the ROI region only (zoomed-in view)
    highlight       - full frame with ROI highlighted (box + dimmed surroundings)
    crop_and_concat - left=original, right=per-frame top-1 person crop
                      (requires a YoloPrefilter instance for per-frame detection)

Output is saved as <stem>_input.mp4 alongside the original segment.
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_CONCAT_CROP_W = 224
_DIVIDER_W = 4


def expand_roi(roi_xyxy, expand: float) -> tuple:
    """Expand normalized [x1,y1,x2,y2] by `expand` fraction; clamp to [0,1]."""
    x1, y1, x2, y2 = roi_xyxy
    w, h = x2 - x1, y2 - y1
    cx1 = max(0.0, x1 - w * expand)
    cy1 = max(0.0, y1 - h * expand)
    cx2 = min(1.0, x2 + w * expand)
    cy2 = min(1.0, y2 + h * expand)
    return cx1, cy1, cx2, cy2


def prepare_roi_segment(
    seg_path: str,
    roi_xyxy,
    mode: str = "crop",
    expand: float = 0.25,
    yolo=None,
    reencode_h264: bool = True,
) -> Optional[str]:
    """Prepare a ROI-enhanced segment mp4 for VLM consumption.

    Returns the output path (<stem>_input.mp4) or None on failure.
    """
    cap = cv2.VideoCapture(seg_path)
    if not cap.isOpened():
        logger.warning("ROI %s: cannot open %s", mode, seg_path)
        return None
    fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0

    cx1, cy1, cx2, cy2 = expand_roi(roi_xyxy, expand)
    px1, py1 = int(cx1 * fw), int(cy1 * fh)
    px2, py2 = int(cx2 * fw), int(cy2 * fh)
    crop_w, crop_h = px2 - px1, py2 - py1
    if crop_w < 32 or crop_h < 32:
        cap.release()
        logger.warning("ROI %s: region too small (%dx%d)", mode, crop_w, crop_h)
        return None

    stem = os.path.splitext(seg_path)[0]
    out_path = f"{stem}_input.mp4"

    if mode == "crop":
        out_size = (crop_w, crop_h)
    elif mode == "crop_and_concat":
        out_size = (fw + _DIVIDER_W + _CONCAT_CROP_W, fh)
    else:  # highlight
        out_size = (fw, fh)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, out_size)

    gray_right = np.full((fh, _CONCAT_CROP_W, 3), 128, dtype=np.uint8)
    divider = np.full((fh, _DIVIDER_W, 3), 255, dtype=np.uint8)
    last_crop = gray_right.copy()
    sample_fps = yolo.sample_fps if (yolo and hasattr(yolo, "sample_fps")) else 2.0
    infer_step = max(1, round(fps / sample_fps))
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if mode == "crop":
            writer.write(frame[py1:py2, px1:px2])
        elif mode == "highlight":
            overlay = frame.copy()
            mask = np.zeros((fh, fw), dtype=np.uint8)
            mask[py1:py2, px1:px2] = 255
            overlay[mask == 0] = (frame[mask == 0] * 0.4).astype(np.uint8)
            cv2.rectangle(overlay, (px1, py1), (px2, py2), (0, 255, 0), 2)
            writer.write(overlay)
        elif mode == "crop_and_concat":
            if yolo is not None and frame_idx % infer_step == 0:
                dets = yolo.predict(frame)
                infer_w, infer_h = yolo.last_infer_size
                persons = [d for d in dets if d["name"] == "person"]
                if persons:
                    top1 = max(persons, key=lambda d: d["conf"])
                    bx1, by1, bx2, by2 = top1["xyxy"]
                    sx, sy = fw / (infer_w or 1), fh / (infer_h or 1)
                    bx1, by1 = int(bx1 * sx), int(by1 * sy)
                    bx2, by2 = int(bx2 * sx), int(by2 * sy)
                    bw, bh = bx2 - bx1, by2 - by1
                    bx1 = max(0, bx1 - int(bw * expand))
                    by1 = max(0, by1 - int(bh * expand))
                    bx2 = min(fw, bx2 + int(bw * expand))
                    by2 = min(fh, by2 + int(bh * expand))
                    person_crop = frame[by1:by2, bx1:bx2]
                    if person_crop.size > 0:
                        ph, pw = person_crop.shape[:2]
                        scale = min(_CONCAT_CROP_W / pw, fh / ph)
                        new_w, new_h = int(pw * scale), int(ph * scale)
                        resized = cv2.resize(person_crop, (new_w, new_h),
                                             interpolation=cv2.INTER_LINEAR)
                        panel = np.full((fh, _CONCAT_CROP_W, 3), 128, dtype=np.uint8)
                        y_off = (fh - new_h) // 2
                        x_off = (_CONCAT_CROP_W - new_w) // 2
                        panel[y_off:y_off + new_h, x_off:x_off + new_w] = resized
                        last_crop = panel
            concat = np.hstack([frame, divider, last_crop])
            writer.write(concat)
        frame_idx += 1
    cap.release()
    writer.release()

    if reencode_h264:
        h264_path = out_path.replace(".mp4", "_h264.mp4")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", out_path, "-c:v", "libx264", "-preset", "fast", h264_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=60,
            )
            os.remove(out_path)
            os.rename(h264_path, out_path)
        except Exception as e:
            logger.warning("ROI %s: ffmpeg re-encode failed: %s", mode, e)

    logger.debug("ROI %s: %s -> %s (%dx%d)", mode, os.path.basename(seg_path),
                 os.path.basename(out_path), out_size[0], out_size[1])
    return out_path
