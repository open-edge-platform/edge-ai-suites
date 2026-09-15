#!/usr/bin/env python3

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Export YOLOv8n to OpenVINO IR format for DL Streamer inference."""
from pathlib import Path
from ultralytics import YOLO

MODELS_DIR = Path(__file__).resolve().parent / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

model = YOLO("yolov8n.pt")
model.export(format="openvino", dynamic=False, imgsz=416, int8=False, half=True)
print(f"Model exported to {MODELS_DIR}")
