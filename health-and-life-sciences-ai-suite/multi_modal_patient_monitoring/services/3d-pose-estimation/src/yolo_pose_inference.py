"""
YOLO-Pose Inference Engine - OpenVINO runtime for pose estimation.

Runs yolo11m-pose (COCO-17 keypoints) using OpenVINO IR FP16.
Device selection is controlled via the POSE_3D_DEVICE environment variable.
Supports CPU, GPU, and NPU.

Public API:
    process_frame(frame) -> (annotated_frame, poses_3d, poses_2d)
"""

import os
import cv2
import numpy as np
import logging
from pathlib import Path
import openvino as ov

logger = logging.getLogger(__name__)

# Standard COCO 17-keypoint skeleton
COCO_KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]

COCO_SKELETON = [
    (0, 1), (0, 2), (1, 3), (2, 4),          # head
    (5, 6),                                     # shoulders
    (5, 7), (7, 9), (6, 8), (8, 10),           # arms
    (5, 11), (6, 12),                           # torso
    (11, 12),                                   # hips
    (11, 13), (13, 15), (12, 14), (14, 16),     # legs
]

# Limb colours (BGR): blue for right side, green for left, yellow for centre
_LIMB_COLORS = [
    (255, 128, 0), (255, 128, 0), (255, 128, 0), (255, 128, 0),  # head
    (0, 255, 255),                                                 # shoulders
    (0, 255, 0), (0, 255, 0), (255, 0, 0), (255, 0, 0),          # arms
    (0, 255, 0), (255, 0, 0),                                     # torso
    (0, 255, 255),                                                 # hips
    (0, 255, 0), (0, 255, 0), (255, 0, 0), (255, 0, 0),          # legs
]


class YoloPoseInference:
    """YOLO-Pose inference engine using OpenVINO IR."""

    NUM_KEYPOINTS = 17

    def __init__(self, model_path: str, device: str = None, device_properties: dict = None):
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"OpenVINO IR model not found: {self.model_path}")

        self.core = ov.Core()

        if device is None:
            raw = os.getenv("POSE_3D_DEVICE", "GPU")
            device = raw.strip().strip('"').strip("'")

        logger.info("Compiling YOLO-Pose model on device: %s", device)
        print(f"[INFO] YOLO-Pose target device: {device}")

        if device_properties:
            self._configure_device_properties(device, device_properties)

        try:
            self.compiled_model = self.core.compile_model(str(self.model_path), device)
            self.device = device
            print(f"[INFO] ✓ YOLO-Pose model loaded on {device}")
        except Exception as e:
            raise RuntimeError(f"Failed to load YOLO-Pose on {device}: {e}")

        self.input_layer = self.compiled_model.input(0)
        self.input_shape = self.input_layer.shape  # [1, 3, 640, 640]
        self.imgsz = self.input_shape[2]  # 640

        # Confidence thresholds
        self.conf_threshold = 0.25
        self.iou_threshold = 0.45
        self.kpt_threshold = 0.5

        print(f"[INFO] YOLO-Pose input: {self.input_shape}, imgsz={self.imgsz}")

    # ------------------------------------------------------------------
    # Device helpers (same interface as PoseInference)
    # ------------------------------------------------------------------
    def _configure_device_properties(self, device, props):
        try:
            if device.upper() == "GPU" and "gpu" in props:
                gpu = props["gpu"]
                if "memory_type" in gpu:
                    self.core.set_property("GPU", {"GPU_MEMORY_TYPE": gpu["memory_type"]})
                if "queue_throttle" in gpu:
                    self.core.set_property("GPU", {"GPU_QUEUE_THROTTLE": gpu["queue_throttle"]})
        except Exception as e:
            logger.warning("Failed to set device properties: %s", e)

    def get_device_info(self) -> dict:
        return {
            "device": self.device,
            "model_path": str(self.model_path),
            "input_shape": list(self.input_shape),
            "target_size": (self.imgsz, self.imgsz),
        }

    def get_model_info(self) -> dict:
        return {
            "device": self.device,
            "model_path": str(self.model_path),
            "input_shape": list(self.input_shape),
            "target_size": (self.imgsz, self.imgsz),
            "stride": 0,
        }

    # ------------------------------------------------------------------
    # Preprocessing — letterbox resize
    # ------------------------------------------------------------------
    def preprocess(self, frame):
        """Letterbox-resize *frame* (BGR) to model input size.

        Returns (input_tensor, letterbox_params) where letterbox_params
        is (ratio, dw, dh) needed to map detections back to the
        original frame coordinates.
        """
        h0, w0 = frame.shape[:2]
        r = self.imgsz / max(h0, w0)
        new_w, new_h = int(w0 * r), int(h0 * r)

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        dw = (self.imgsz - new_w) / 2
        dh = (self.imgsz - new_h) / 2
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        padded = cv2.copyMakeBorder(resized, top, bottom, left, right,
                                    cv2.BORDER_CONSTANT, value=(114, 114, 114))
        # Ensure exact size after rounding
        padded = cv2.resize(padded, (self.imgsz, self.imgsz))

        blob = padded.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)[None, ...]  # [1, 3, H, W]
        return blob, (r, dw, dh)

    # ------------------------------------------------------------------
    # Post-processing — decode YOLO-Pose output
    # ------------------------------------------------------------------
    def _decode_output(self, output, ratio, dw, dh, orig_shape):
        """Decode raw YOLO-Pose output tensor.

        The model output shape is [1, 56, N] where each column is:
            [cx, cy, w, h, conf, kx0, ky0, kc0, kx1, ky1, kc1, ...]

        Returns list of dicts with keys: bbox, score, keypoints.
        """
        # output shape: (1, 56, N) — transpose to (N, 56)
        preds = output[0].T  # (N, 56)

        # Filter by object confidence (column 4)
        scores = preds[:, 4]
        mask = scores > self.conf_threshold
        preds = preds[mask]
        scores = scores[mask]

        if len(preds) == 0:
            return []

        # NMS on bounding boxes
        boxes_xywh = preds[:, :4]
        boxes_xyxy = self._xywh2xyxy(boxes_xywh)
        keep = self._nms(boxes_xyxy, scores, self.iou_threshold)
        preds = preds[keep]
        scores = scores[keep]
        boxes_xyxy = boxes_xyxy[keep]

        detections = []
        h0, w0 = orig_shape[:2]
        for i in range(len(preds)):
            # Map bbox back to original image
            x1 = (boxes_xyxy[i, 0] - dw) / ratio
            y1 = (boxes_xyxy[i, 1] - dh) / ratio
            x2 = (boxes_xyxy[i, 2] - dw) / ratio
            y2 = (boxes_xyxy[i, 3] - dh) / ratio

            # Keypoints: 17 * 3 values starting at index 5
            kpts_raw = preds[i, 5:].reshape(self.NUM_KEYPOINTS, 3)
            kpts = np.zeros_like(kpts_raw)
            kpts[:, 0] = (kpts_raw[:, 0] - dw) / ratio  # x
            kpts[:, 1] = (kpts_raw[:, 1] - dh) / ratio  # y
            kpts[:, 2] = kpts_raw[:, 2]                   # conf

            # Clamp to image bounds
            kpts[:, 0] = np.clip(kpts[:, 0], 0, w0)
            kpts[:, 1] = np.clip(kpts[:, 1], 0, h0)

            detections.append({
                "bbox": [float(x1), float(y1), float(x2), float(y2)],
                "score": float(scores[i]),
                "keypoints": kpts,
            })

        return detections

    @staticmethod
    def _xywh2xyxy(boxes):
        out = np.empty_like(boxes)
        out[:, 0] = boxes[:, 0] - boxes[:, 2] / 2
        out[:, 1] = boxes[:, 1] - boxes[:, 3] / 2
        out[:, 2] = boxes[:, 0] + boxes[:, 2] / 2
        out[:, 3] = boxes[:, 1] + boxes[:, 3] / 2
        return out

    @staticmethod
    def _nms(boxes, scores, iou_thresh):
        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
            iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
            order = order[np.where(iou <= iou_thresh)[0] + 1]
        return keep

    # ------------------------------------------------------------------
    # Main entry point — same signature as PoseInference.process_frame()
    # ------------------------------------------------------------------
    def process_frame(self, frame):
        """Process a single frame.

        Returns:
            annotated_frame: frame with skeleton overlay
            poses_3d: list of 3D pose arrays (placeholder zeros for YOLO 2D model)
            poses_2d: list of 2D poses in legacy format [x0,y0,c0,...,overall_score]
        """
        blob, (ratio, dw, dh) = self.preprocess(frame)
        result = self.compiled_model(blob)
        output = result[self.compiled_model.output(0)]

        detections = self._decode_output(output, ratio, dw, dh, frame.shape)

        poses_3d = []
        poses_2d = []

        for det in detections:
            kpts = det["keypoints"]  # (17, 3)
            score = det["score"]

            # Build legacy 2D format: [x0,y0,c0, x1,y1,c1, ..., overall_score]
            flat = []
            for k in range(self.NUM_KEYPOINTS):
                flat.extend([float(kpts[k, 0]), float(kpts[k, 1]), float(kpts[k, 2])])
            flat.append(float(score))
            poses_2d.append(np.array(flat))

            # Placeholder 3D: (17, 4) zeros — YOLO-Pose is 2D-only
            pose_3d = np.zeros((self.NUM_KEYPOINTS, 4), dtype=np.float32)
            for k in range(self.NUM_KEYPOINTS):
                pose_3d[k] = [float(kpts[k, 0]), float(kpts[k, 1]), 0.0, float(kpts[k, 2])]
            poses_3d.append(pose_3d)

        annotated_frame = self.draw_poses(frame, detections)
        return annotated_frame, poses_3d, poses_2d

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw_poses(self, frame, detections):
        """Draw bounding boxes, labels, and COCO-17 skeletons on *frame*."""
        annotated = frame.copy()

        for person_idx, det in enumerate(detections):
            kpts = det["keypoints"]
            bbox = det["bbox"]  # [x1, y1, x2, y2]
            score = det["score"]

            # Draw bounding box
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            box_color = (0, 255, 0)  # green
            cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, 2, cv2.LINE_AA)

            # Draw label (larger font for visibility)
            label = f"Person {person_idx + 1}: {score:.0%}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
            cv2.rectangle(annotated, (x1, y1 - th - 12), (x1 + tw + 6, y1), box_color, -1)
            cv2.putText(annotated, label, (x1 + 3, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2, cv2.LINE_AA)

            # Draw limb connections
            for idx, (i, j) in enumerate(COCO_SKELETON):
                if kpts[i, 2] > self.kpt_threshold and kpts[j, 2] > self.kpt_threshold:
                    pt1 = (int(kpts[i, 0]), int(kpts[i, 1]))
                    pt2 = (int(kpts[j, 0]), int(kpts[j, 1]))
                    color = _LIMB_COLORS[idx % len(_LIMB_COLORS)]
                    cv2.line(annotated, pt1, pt2, color, 3, cv2.LINE_AA)

            # Draw keypoints
            for k in range(self.NUM_KEYPOINTS):
                if kpts[k, 2] > self.kpt_threshold:
                    cx, cy = int(kpts[k, 0]), int(kpts[k, 1])
                    cv2.circle(annotated, (cx, cy), 5, (255, 0, 255), -1, cv2.LINE_AA)

        return annotated
