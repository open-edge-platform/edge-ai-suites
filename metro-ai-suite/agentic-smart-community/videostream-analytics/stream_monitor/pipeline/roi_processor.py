"""ROI-cropped clip generation for VLM input (child_safety).
The pipeline calls `prepare_roi_segment()` after a motion segment is written
and prefilter has accumulated a `trajectory_region_xyxy` union bbox. The
result is `<seg_stem>_input.mp4`, which `_emit_segment` then sends to MCP as
`summary_clip_input` so the VLM sees a zoomed-in / highlighted view.

All failures are downgraded to a logger.warning + `None` return. Callers must
fall back to the original clip path on `None`.
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Width of the right-side panel in crop_and_concat mode.
_CONCAT_CROP_W = 224
# Thickness of the white divider line in crop_and_concat mode.
_DIVIDER_W = 4


def _expand_roi(roi_xyxy: list[float], expand: float) -> tuple[float, float, float, float]:
    """Expand normalized [x1,y1,x2,y2] box by `expand` fraction, clamp to [0,1]."""
    x1, y1, x2, y2 = roi_xyxy
    w, h = x2 - x1, y2 - y1
    cx1 = max(0.0, x1 - w * expand)
    cy1 = max(0.0, y1 - h * expand)
    cx2 = min(1.0, x2 + w * expand)
    cy2 = min(1.0, y2 + h * expand)
    return cx1, cy1, cx2, cy2


def prepare_roi_segment(
    seg_path: str,
    roi_xyxy: list[float],
    mode: str = "crop",
    expand: float = 0.25,
    yolo: Any | None = None,
) -> str | None:
    """Prepare a ROI-enhanced segment for VLM consumption.

    Output is saved as `<seg_stem>_input.mp4` alongside the original segment.
    Returns the output path, or None on any failure (caller falls back to
    the original clip).

    Modes:
        crop            – crop to ROI region only (zoomed-in view)
        highlight       – full frame with ROI highlighted (box + dim overlay)
        crop_and_concat – left=original, right=per-frame top1 person crop
                          (requires `yolo` for per-frame detection)
    """
    if not os.path.exists(seg_path):
        logger.warning("ROI %s: source segment not found: %s", mode, seg_path)
        return None
    if not roi_xyxy or len(roi_xyxy) != 4:
        logger.warning("ROI %s: invalid roi_xyxy=%r", mode, roi_xyxy)
        return None

    cap = cv2.VideoCapture(seg_path)
    if not cap.isOpened():
        logger.warning("ROI %s: cannot open %s", mode, seg_path)
        return None
    fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0

    cx1, cy1, cx2, cy2 = _expand_roi(roi_xyxy, expand)
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
    else:  # highlight (also default fallback for unknown modes)
        out_size = (fw, fh)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, out_size)
    if not writer.isOpened():
        cap.release()
        logger.warning("ROI %s: cannot open writer for %s (size=%s)",
                       mode, out_path, out_size)
        return None

    # crop_and_concat scratch buffers
    cw = _CONCAT_CROP_W
    gray_right = np.full((fh, cw, 3), 128, dtype=np.uint8)
    divider = np.full((fh, _DIVIDER_W, 3), 255, dtype=np.uint8)
    last_crop = gray_right.copy()
    sample_fps = (
        yolo.sample_fps if (yolo is not None and hasattr(yolo, "sample_fps")) else 2.0
    )
    infer_step = max(1, round(fps / sample_fps))
    frame_idx = 0

    try:
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
                    try:
                        dets = yolo.predict(frame)
                    except Exception as e:
                        logger.debug("ROI concat: yolo.predict failed: %s", e)
                        dets = []
                    persons = [d for d in dets if d.get("name") == "person"]
                    if persons:
                        top1 = max(persons, key=lambda d: d.get("conf", 0.0))
                        box = top1.get("xyxy")
                        # `_postprocess` returns normalized coords; scale to fw/fh
                        if box and len(box) == 4:
                            bx1, by1 = int(box[0] * fw), int(box[1] * fh)
                            bx2, by2 = int(box[2] * fw), int(box[3] * fh)
                            bw, bh = bx2 - bx1, by2 - by1
                            bx1 = max(0, bx1 - int(bw * expand))
                            by1 = max(0, by1 - int(bh * expand))
                            bx2 = min(fw, bx2 + int(bw * expand))
                            by2 = min(fh, by2 + int(bh * expand))
                            person_crop = frame[by1:by2, bx1:bx2]
                            if person_crop.size > 0:
                                ph, pw = person_crop.shape[:2]
                                scale = min(cw / pw, fh / ph)
                                new_w, new_h = int(pw * scale), int(ph * scale)
                                resized = cv2.resize(
                                    person_crop, (new_w, new_h),
                                    interpolation=cv2.INTER_LINEAR,
                                )
                                panel = np.full((fh, cw, 3), 128, dtype=np.uint8)
                                y_off = (fh - new_h) // 2
                                x_off = (cw - new_w) // 2
                                panel[y_off:y_off + new_h, x_off:x_off + new_w] = resized
                                last_crop = panel
                writer.write(np.hstack([frame, divider, last_crop]))
            else:
                # Unknown mode — write the original frame (no transform)
                writer.write(frame)
            frame_idx += 1
    finally:
        cap.release()
        writer.release()

    # Re-encode to h264 for VLM compatibility. Failure is tolerated — keep
    # the mp4v output rather than dropping the clip.
    h264_path = out_path.replace(".mp4", "_h264.mp4")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", out_path,
             "-c:v", "libx264", "-preset", "fast", h264_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
        )
        os.remove(out_path)
        os.rename(h264_path, out_path)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        logger.warning("ROI %s: ffmpeg re-encode failed (%s), keeping mp4v", mode, e)
        # Clean up partial h264 file if it exists.
        try:
            if os.path.exists(h264_path):
                os.remove(h264_path)
        except OSError:
            pass

    logger.debug(
        "ROI %s: %s -> %s (%dx%d)",
        mode, os.path.basename(seg_path),
        os.path.basename(out_path), out_size[0], out_size[1],
    )
    return out_path
