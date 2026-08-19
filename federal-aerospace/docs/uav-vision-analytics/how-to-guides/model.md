<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# AI Model — YOLOv8n-VisDrone

The UAV Vision Analytics application uses **YOLOv8n-VisDrone**, an object detection model
fine-tuned on the [VisDrone dataset](https://github.com/VisDrone/VisDrone-Dataset) for
detecting objects commonly seen in drone-view imagery.


## Model Details

| Property            | Value                                                                |
|---------------------|----------------------------------------------------------------------|
| Model               | YOLOv8n-VisDrone                                                     |
| Source              | [mshamrai/yolov8n-visdrone](https://huggingface.co/mshamrai/yolov8n-visdrone) |
| Precision           | FP16 (OpenVINO IR)                                                   |
| Input resolution    | 640 × 640                                                            |
| Detection classes   | pedestrian, people, bicycle, car, van, truck, tricycle, awning-tricycle, bus, motor |
| Ultralytics version | 8.4.67 (pinned — see `resources/requirements.txt`)                   |

> ⚠️ **`ultralytics` is pinned to `8.4.67`.** Newer releases (8.4.115+ tested) changed the detection head's box-decoding math to use a `CumSum` op instead of `Range`. The resulting OpenVINO IR runs fine on **CPU** but fails to compile on **GPU** and **NPU** plugins. Version `8.4.67` produces a `Range`-based graph verified on all three devices. Do not upgrade `ultralytics` without re-verifying GPU/NPU compatibility.

---

## Prerequisites

- **Python 3.10 or later** with `python3-venv` support
- **Internet access** to reach Hugging Face and PyPI (configure proxy if behind a corporate firewall)

### Install `python3-venv` (if missing)

`make model` creates a virtual environment via `python3 -m venv`. On Ubuntu 24 the venv support package must be installed separately:

```bash
sudo apt install python3.12-venv
```

---

## Quick Setup — `make model` (recommended)

From the app root directory:

```bash
cd edge-ai-suites/federal-aerospace/apps/uav-vision-analytics

make model
```

This creates `resources/venv/`, installs all dependencies, downloads `best.pt` from Hugging Face, and exports to OpenVINO FP16 IR.

**Behind a proxy?** Set proxy variables before running:

```bash
export https_proxy=http://proxy-org.com:port-number
export http_proxy=http://proxy-org.com:port-number

make model
```

---

## Expected Output Path

After export, the model files are at:

```
resources/
└── models/
    └── yolov8n-visdrone/
        ├── best.pt                      ← downloaded PyTorch checkpoint
        └── best_openvino_model/
            ├── best.xml                 ← OpenVINO IR model definition
            └── best.bin                 ← model weights
```

The inference pipelines reference the model at the container-internal path:

```
/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml
```
