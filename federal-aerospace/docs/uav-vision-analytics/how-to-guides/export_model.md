<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Export YOLOv8n-VisDrone to OpenVINO

The `make model` target automates all steps below. Run the steps manually only if `make model` fails or you need a custom export configuration (e.g., INT8 quantization).

---

## Prerequisites

- **Python 3.10 or later** with `python3-venv` support
- **Internet access** to reach Hugging Face and PyPI (configure proxy if behind a corporate firewall)

### Install `python3-venv` (if missing)

`make model` creates a virtual environment via `python3 -m venv`. On Ubuntu 24 the venv support package must be installed separately:

```bash
# Ubuntu 22.04 / 24.04
sudo apt install python3.12-venv

# If on Ubuntu 22.04 with Python 3.10:
sudo apt install python3.10-venv python3-venv
```

> **Error you'll see without this:**
> ```
> The virtual environment was not created successfully because ensurepip is not available.
> Failing command: .../resources/venv/bin/python3
> make: *** [Makefile:28: model] Error 1
> ```

---

## AI Model

| Property | Value |
|---|---|
| Model | YOLOv8n-VisDrone |
| Source | [mshamrai/yolov8n-visdrone](https://huggingface.co/mshamrai/yolov8n-visdrone) |
| Precision | FP16 (OpenVINO IR) |
| Input resolution | 640 × 640 |
| Detection classes | pedestrian, people, bicycle, car, van, truck, tricycle, awning-tricycle, bus, motor |
| Ultralytics version | 8.4.67 (pinned — see `resources/requirements.txt`) |

---

## Quick start — automated (`make model`)

From the app root directory:

```bash
cd edge-ai-suites/federal-aerospace/apps/uav-vision-analytics

make model
```

This creates `resources/venv/`, installs all dependencies, downloads `best.pt` from Hugging Face, and exports to OpenVINO FP16 IR.

**Behind a proxy?** Ensure `https_proxy` is set in your environment before running `make model`:

```bash
export https_proxy=http://proxy-org.com:port-number
export http_proxy=http://proxy-org.com:port-number

make model
```

---

## Manual steps

Use these steps if `make model` fails or you want a different precision (FP32, INT8).

### Step 1: Create and activate a virtual environment

```bash
cd edge-ai-suites/federal-aerospace/apps/uav-vision-analytics/resources

# Install venv support if needed
sudo apt install python3.12-venv

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

> **`nncf` is only required** if you plan to use `int8=True` INT8 export.

> ⚠️ **Pin `ultralytics==8.4.67`.** Newer releases (8.4.115+ tested) changed the detection head's box-decoding math to use a `CumSum` op instead of `Range`. The resulting OpenVINO IR runs fine on **CPU** but fails to compile on **GPU** and **NPU** plugins. `8.4.67` produces a `Range`-based graph verified on all three devices. `requirements.txt` already pins this version — do not upgrade `ultralytics` without re-verifying GPU/NPU compatibility.

### Step 2: Download the checkpoint from Hugging Face

```bash
hf download mshamrai/yolov8n-visdrone best.pt --local-dir ./models/yolov8n-visdrone
```

### Step 3: Export to OpenVINO IR

Run from inside the `resources/` folder (where `venv` and `models/` are located):

**FP16 (recommended — required for GPU/NPU-compatible graph):**
```bash
yolo export \
  model=./models/yolov8n-visdrone/best.pt \
  format=openvino dynamic=True opset=18 imgsz=640 half=True
```

**FP32:**
```bash
yolo export \
  model=./models/yolov8n-visdrone/best.pt \
  format=openvino dynamic=True opset=18 imgsz=640
```

**INT8 (requires `nncf`, calibrated quantization):**
```bash
# Fast calibration using the built-in coco8.yaml sample set (~seconds):
yolo export \
  model=./models/yolov8n-visdrone/best.pt \
  format=openvino dynamic=True opset=18 imgsz=640 int8=True

# Better accuracy: calibrate on VisDrone (~1.7 GB download on first run):
yolo export \
  model=./models/yolov8n-visdrone/best.pt \
  format=openvino dynamic=True opset=18 imgsz=640 int8=True data=VisDrone.yaml
```

Each export creates a `best_openvino_model/` folder next to `best.pt` containing `best.xml` and `best.bin`.

---

## Step 4: Verify the exported model (optional)

```bash
python3 -c "
import openvino as ov
core = ov.Core()
m = core.read_model('./models/yolov8n-visdrone/best_openvino_model/best.xml')
print('OK — inputs:', [i.any_name for i in m.inputs])
print('Available devices:', core.available_devices)
"
```

Use `best_int8_openvino_model` in the path if you exported with `int8=True`.

---

## Step 5: Run a quick inference test (optional)

```bash
yolo predict \
  model=./models/yolov8n-visdrone/best_openvino_model \
  imgsz=640 \
  source=<image_or_video_path>
```

---

## Expected output path

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

---

## VisDrone detection classes

The model detects 10 classes of objects commonly found in drone-view imagery:

```
pedestrian  people  bicycle  car  van  truck  tricycle  awning-tricycle  bus  motor
```
