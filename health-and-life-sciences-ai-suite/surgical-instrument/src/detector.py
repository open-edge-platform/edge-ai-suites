"""OpenVINO polyp detector — pure OpenVINO (no ultralytics), version-stable.

Takes a BGR numpy frame and returns detection boxes in the ORIGINAL frame's
pixel coordinates. Preprocessing is standard YOLO letterbox (aspect-preserving
resize + gray-114 pad) so accuracy matches the exported model. Post-processing
decodes the YOLO ``[1, 4+nc, 8400]`` head and runs numpy NMS.

Kept deliberately free of GStreamer / VA-API so it runs identically whether the
frames come from a Basler camera, a webcam, or a video file.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np
import openvino as ov

log = logging.getLogger("detector")


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float
    score: float


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thr: float) -> list[int]:
    if boxes.size == 0:
        return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(x1[i], x1[rest])
        yy1 = np.maximum(y1[i], y1[rest])
        xx2 = np.minimum(x2[i], x2[rest])
        yy2 = np.minimum(y2[i], y2[rest])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        union = areas[i] + areas[rest] - inter
        iou = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
        order = rest[iou <= iou_thr]
    return keep


class Detector:
    def __init__(
        self,
        model_xml: str,
        device: str = "GPU",
        threshold: float = 0.5,
        iou_threshold: float = 0.45,
    ) -> None:
        self.threshold = threshold
        self.iou_threshold = iou_threshold
        self.device = device.upper()

        core = ov.Core()
        model = core.read_model(model_xml)
        cfg: dict[str, str] = {
            "PERFORMANCE_HINT": "LATENCY",
            "NUM_STREAMS": "1",
            "ALLOW_AUTO_BATCHING": "NO",
        }
        if self.device == "GPU":
            # Empirically the throughput-critical knob on Intel iGPUs for this
            # model/driver combo (matches the BU reference configuration).
            cfg["GPU_DISABLE_WINOGRAD_CONVOLUTION"] = "YES"
        self._compiled = core.compile_model(model, self.device, cfg)
        self._request = self._compiled.create_infer_request()
        self._input = self._compiled.inputs[0]
        _, _, self.in_h, self.in_w = (int(v) for v in self._input.shape)
        log.info(
            "detector ready: device=%s input=%dx%d thr=%.2f iou=%.2f",
            self.device, self.in_w, self.in_h, threshold, iou_threshold,
        )
        self._warmup()

    def _warmup(self) -> None:
        blob = np.zeros((1, 3, self.in_h, self.in_w), dtype=np.float32)
        try:
            self._request.infer({self._input: blob})
            log.info("warmup inference done")
        except Exception as exc:  # noqa: BLE001
            log.warning("warmup failed: %s", exc)

    def _letterbox(self, frame_bgr: np.ndarray) -> tuple[np.ndarray, float, int, int]:
        h0, w0 = frame_bgr.shape[:2]
        scale = min(self.in_w / w0, self.in_h / h0)
        nw, nh = int(round(w0 * scale)), int(round(h0 * scale))
        resized = cv2.resize(frame_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((self.in_h, self.in_w, 3), 114, dtype=np.uint8)
        pad_x, pad_y = (self.in_w - nw) // 2, (self.in_h - nh) // 2
        canvas[pad_y:pad_y + nh, pad_x:pad_x + nw] = resized
        return canvas, scale, pad_x, pad_y

    def infer(self, frame_bgr: np.ndarray) -> list[Box]:
        h0, w0 = frame_bgr.shape[:2]
        lb, scale, pad_x, pad_y = self._letterbox(frame_bgr)
        # BGR -> RGB, normalize, HWC -> NCHW
        blob = lb[:, :, ::-1].astype(np.float32) / 255.0
        blob = np.ascontiguousarray(blob.transpose(2, 0, 1)[None])

        self._request.infer({self._input: blob})
        out = np.asarray(self._request.get_output_tensor(0).data)[0]  # (4+nc, 8400) or (8400, 4+nc)
        if out.shape[0] < out.shape[1]:
            out = out.transpose(1, 0)
        if out.shape[1] < 5:
            return []

        cxcywh = out[:, :4]
        scores = out[:, 4] if out.shape[1] == 5 else out[:, 4:].max(axis=1)
        keep = scores >= self.threshold
        if not np.any(keep):
            return []
        cxcywh, scores = cxcywh[keep], scores[keep]

        xyxy = np.empty_like(cxcywh)
        xyxy[:, 0] = cxcywh[:, 0] - cxcywh[:, 2] / 2
        xyxy[:, 1] = cxcywh[:, 1] - cxcywh[:, 3] / 2
        xyxy[:, 2] = cxcywh[:, 0] + cxcywh[:, 2] / 2
        xyxy[:, 3] = cxcywh[:, 1] + cxcywh[:, 3] / 2
        # letterbox space -> original frame space
        xyxy[:, [0, 2]] = (xyxy[:, [0, 2]] - pad_x) / scale
        xyxy[:, [1, 3]] = (xyxy[:, [1, 3]] - pad_y) / scale
        xyxy[:, [0, 2]] = np.clip(xyxy[:, [0, 2]], 0, w0 - 1)
        xyxy[:, [1, 3]] = np.clip(xyxy[:, [1, 3]], 0, h0 - 1)

        idxs = _nms(xyxy, scores, self.iou_threshold)
        return [
            Box(float(xyxy[i, 0]), float(xyxy[i, 1]), float(xyxy[i, 2]), float(xyxy[i, 3]), float(scores[i]))
            for i in idxs
        ]
