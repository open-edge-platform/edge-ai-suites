<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# AI Model — YOLO11s

The UAV Vision Analytics application uses **YOLO11s**, Ultralytics' stock
COCO-pretrained object detection model.


## Model Details

| Property | Value |
| --- | --- |
| Model | YOLO11s |
| Source | Ultralytics (downloaded by the `yolo` CLI) |
| Precision | FP16 (OpenVINO IR) |
| Input resolution | 640 × 640 |
| Detection classes | 80 classes (person, car, truck, bus, bicycle, motorcycle, ...) |
| Ultralytics version | 8.4.67 (pinned — see `resources/requirements.txt`) |

> **Important:** `ultralytics` **is pinned to** `8.4.67`. Newer releases
> (8.4.115+ tested) changed the detection head's box-decoding math to use a
> `CumSum` op instead of `Range`. The resulting OpenVINO IR runs fine on
> **CPU** but fails to compile on **GPU** and **NPU** plugins. Version `8.4.67`
> produces a `Range`-based graph verified on all three devices. Do not upgrade
> `ultralytics` without re-verifying GPU/NPU compatibility.

## Prerequisites

- **Python 3.10 or later** with `python3-venv` support
- **Internet access** to reach Ultralytics' release assets and PyPI (configure proxy if behind a corporate firewall)

### Install `python3-venv` (if missing)

`make model` creates a virtual environment via `python3 -m venv`. On Ubuntu 24 the venv support package must be installed separately:

```bash
sudo apt install python3.12-venv
```

## Quick Setup — `make model` (recommended)

From the app root directory:

```bash
cd edge-ai-suites/federal-and-aerospace-ai-suite/uav-vision-analytics

make model
```

This creates `resources/venv/`, installs all dependencies, downloads `yolo11s.pt` from Ultralytics, and exports to OpenVINO FP16 IR.

**Behind a proxy?** Set proxy variables before running:

```bash
export https_proxy=http://proxy-org.com:port-number
export http_proxy=http://proxy-org.com:port-number

make model
```

## Expected Output Path

After export, the model files are at:

```text
resources/
└── models/
    └── yolo11s/
        ├── yolo11s.pt                     ← downloaded PyTorch checkpoint
        └── yolo11s_openvino_model/
            ├── yolo11s.xml                ← OpenVINO IR model definition
            └── yolo11s.bin                ← model weights
```

The inference pipelines reference the model at the container-internal path:

```text
/home/pipeline-server/resources/models/yolo11s/yolo11s_openvino_model/yolo11s.xml
```

## Using a Different Ultralytics Model

To try a different size/variant (e.g. `yolo11n`, `yolo11m`, or `yolov8n`),
edit the `model=` value in the `model` target of the `Makefile` (it accepts
any Ultralytics model name and auto-downloads the matching checkpoint), then
update the model path in every file that references it:

- `Makefile` (`MODEL_DIR`, `MODEL_XML`)
- `scripts/mavlink_pipeline_manager.py` (`MODEL_PATH`)
- `scripts/uavsdk_pipeline_manager.py` (`MODEL_PATH`)
- `benchmark/benchmark_app_payload.json` (all `model` fields)

## Using a Custom / Fine-Tuned Model

To substitute a custom-trained OpenVINO IR model (e.g. a model fine-tuned on
aerial imagery):

1. Place `model.xml` + `model.bin` under `resources/models/{{MODEL_NAME}}/`
2. Update the model path in the files listed above
3. Re-verify `threshold` (default `0.4`) is appropriate for the new model's
   confidence distribution

**Note:** Only OpenVINO IR format (`.xml` + `.bin`) is supported by
`gvadetect`. ONNX models must be converted first with `mo` (OpenVINO Model
Optimizer) or `openvino.convert_model()`.
