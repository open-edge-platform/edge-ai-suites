<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Demo/PoC mode reference (`{{MODE}}=demo`)

Load **only** when Question 0 selected `demo`. Build one lightweight app proving Intel inference output. Do **not**:

- generate a Docker Compose stack, `.env`, `install.sh`, or the `{{STACK_DIR}}/` layout from the main skill;
- stand up MediaMTX/WebRTC, Coturn, Mosquitto, Node-RED, Grafana, or Nginx;
- run parameter validation or production completion criteria (1–11).

Ask **one** sub-path question:

> Demo/PoC framework? `dlstreamer` (video-analytics pipeline) or
> `openvino` (minimal inference script). [default `dlstreamer`]

Scope: one model, one input, one device. Confirm it runs and prints/overlays results, then stop.

## Sub-path A — DL Streamer demo app (`dlstreamer`)

Use for **video analytics** (decode → infer → overlay/print detections) on file, RTSP, or `/dev/video*`.

**Delegate to `dlstreamer-coding-agent`** (open-edge-platform/skills) when available; it creates DL Streamer apps (Python, C/C++, or `gst-launch-1.0`). Pass:

| Input | Example | Notes |
|---|---|---|
| Task | object detection / classification | one task only for a PoC |
| Model | `yolov11s` (OpenVINO IR) | reuse an OMZ / DL Streamer model; `model-download` skill can fetch IR |
| Input source | `file:///path/sample.mp4`, `rtsp://…`, `/dev/video0` | one source |
| Device | `CPU` (default), `GPU`, `NPU`, `AUTO` | Intel target |
| Output | `gvawatermark` overlay + `gvametaconvert`/`gvametapublish` to stdout | no MQTT/WebRTC needed for a PoC |

If unavailable, hand-write a minimal pipeline:

```bash
gst-launch-1.0 filesrc location=sample.mp4 ! decodebin ! \
  gvadetect model=yolov11s.xml device=CPU ! gvawatermark ! \
  gvametaconvert ! gvametapublish method=file file-path=/dev/stdout ! \
  fakesink sync=false
```

Set `gvadetect` to chosen `GPU`/`NPU`; add one `gvaclassify` only if requested.

**Done when:** pipeline reaches EOS/steady state and prints metadata and/or annotated output without errors.

## Sub-path B — OpenVINO demo app (`openvino`)

Use for **standalone inference** over image/video or non-video model, with no GStreamer.

No dedicated OpenVINO skill — follow OpenVINO 2026 docs:

- Get Started / install: <https://docs.openvino.ai/2026/index.html>
- Python API (`ov.Core`, `read_model`, `compile_model`, `infer`)
- Model conversion (`ov.convert_model`) and OpenVINO IR (`.xml`/`.bin`)

Minimal pattern (adapt model/pre/post-processing):

```python
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import cv2
import numpy as np
import openvino as ov

DEVICE = "CPU"  # or "GPU", "NPU", "AUTO"

core = ov.Core()
model = core.read_model("model.xml")          # OpenVINO IR (or an .onnx model)
compiled = core.compile_model(model, DEVICE)
out_port = compiled.output(0)

img = cv2.imread("sample.jpg")
_, _, h, w = compiled.input(0).shape          # NCHW
blob = cv2.resize(img, (w, h)).transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)

result = compiled([blob])[out_port]           # run inference
print("output shape:", result.shape)          # post-process per model spec
```

Guidance:

- Install `pip install openvino` (add `openvino-dev`/`nncf` only for conversion or INT8 quantization).
- Get IR via `model-download` (OMZ) or `ov.convert_model` from PyTorch/ONNX/TensorFlow.
- Device string is the chosen `CPU`/`GPU`/`NPU`/`AUTO`.

**Done when:** script loads model, runs real inference, and prints/writes sensible class, boxes, or tensor without errors.

## Demo/PoC completion criteria (all must pass)

1. Exactly one application is produced for the chosen sub-path — no full-stack containers, no MediaMTX/Node-RED/Grafana/Nginx.
2. The app targets the user's Intel device (`CPU`/`GPU`/`NPU`/`AUTO`).
3. The app runs end-to-end and produces inference output (printed metadata, annotated frames, or an output tensor).
4. Any generated source file carries the SPDX header (`SPDX-FileCopyrightText` + `SPDX-License-Identifier: Apache-2.0`).
5. A short README/usage note states how to run it and what output to expect.

## Optional external skills (demo mode)

Invoke if available; else use templates above.

- `dlstreamer-coding-agent` (open-edge-platform/skills) — Sub-path A pipeline authoring.
- `dlsps-user` (open-edge-platform/skills) — **not needed for a demo**; use only if PoC becomes a REST-driven Pipeline Server microservice; then switch to full-stack (`{{MODE}}=production`).
- `model-download` (open-edge-platform/edge-ai-libraries) — fetch/convert model IR for either sub-path.
