<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Demo/PoC mode reference (`{{MODE}}=demo`)

Load this file **only** when Question 0 selected `demo`. The goal is a
**single, lightweight application** that proves an AI model runs on Intel
hardware and produces inference output — nothing else. Explicitly do **not**:

- generate a Docker Compose stack, `.env`, `install.sh`, or the `{{STACK_DIR}}/`
  layout from the main skill;
- stand up MediaMTX/WebRTC, Coturn, Mosquitto, Node-RED, Grafana, or Nginx;
- run parameter validation or the production completion criteria (1–11).

Ask the user **one** question to pick a sub-path, then follow it:

> Demo/PoC framework? `dlstreamer` (video-analytics pipeline) or
> `openvino` (minimal inference script). [default `dlstreamer`]

Keep the scope tiny: one model, one input, one device. Confirm the app runs
and prints/overlays results, then stop.

## Sub-path A — DL Streamer demo app (`dlstreamer`)

Best when the demo is a **video-analytics pipeline** (decode → infer →
overlay/print detections) on a file, RTSP stream, or `/dev/video*` camera.

**Delegate to the `dlstreamer-coding-agent` skill** (open-edge-platform/skills)
when it is available in the session — it translates a natural-language pipeline
description into a working DL Streamer app (Python, C/C++, or a `gst-launch-1.0`
command line). Pass it the minimal inputs:

| Input | Example | Notes |
|---|---|---|
| Task | object detection / classification | one task only for a PoC |
| Model | `yolov11s` (OpenVINO IR) | reuse an OMZ / DL Streamer model; `model-download` skill can fetch IR |
| Input source | `file:///path/sample.mp4`, `rtsp://…`, `/dev/video0` | one source |
| Device | `CPU` (default), `GPU`, `NPU`, `AUTO` | Intel target |
| Output | `gvawatermark` overlay + `gvametaconvert`/`gvametapublish` to stdout | no MQTT/WebRTC needed for a PoC |

If the skill is **not** available, hand-write a minimal pipeline, e.g.:

```bash
gst-launch-1.0 filesrc location=sample.mp4 ! decodebin ! \
  gvadetect model=yolov11s.xml device=CPU ! gvawatermark ! \
  gvametaconvert ! gvametapublish method=file file-path=/dev/stdout ! \
  fakesink sync=false
```

Swap `gvadetect` device to `GPU`/`NPU` per the user's choice; add a single
`gvaclassify` stage only if a classifier was requested.

**Done when:** the pipeline runs to EOS (or steady state for live sources) and
prints detection metadata (and/or writes an annotated output) without errors.

## Sub-path B — OpenVINO demo app (`openvino`)

Best when the demo is a **standalone inference script** over an image/video or
a non-video model, with no GStreamer dependency.

There is **no dedicated OpenVINO skill** — follow the OpenVINO 2026
documentation as the authoritative reference:

- Get Started / install: <https://docs.openvino.ai/2026/index.html>
- Python API (`ov.Core`, `read_model`, `compile_model`, `infer`)
- Model conversion (`ov.convert_model`) and OpenVINO IR (`.xml`/`.bin`)

Minimal pattern (adapt model/pre/post-processing to the chosen model):

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

- Install with `pip install openvino` (add `openvino-dev`/`nncf` only if the
  demo needs model conversion or INT8 quantization).
- Get an IR via the `model-download` skill (OMZ) or `ov.convert_model` from a
  PyTorch/ONNX/TensorFlow source.
- Device selection uses the same `CPU`/`GPU`/`NPU`/`AUTO` string the user chose.

**Done when:** the script loads the model, runs at least one inference on real
input, and prints/writes a sensible result (class, boxes, or output tensor)
without errors.

## Demo/PoC completion criteria (all must pass)

1. Exactly one application is produced for the chosen sub-path — no full-stack
   containers, no MediaMTX/Node-RED/Grafana/Nginx.
2. The app targets the user's Intel device (`CPU`/`GPU`/`NPU`/`AUTO`).
3. The app runs end-to-end and produces inference output (printed metadata,
   annotated frames, or an output tensor).
4. Any generated source file carries the SPDX header
   (`SPDX-FileCopyrightText` + `SPDX-License-Identifier: Apache-2.0`).
5. A short README/usage note states how to run it and what output to expect.

## Optional external skills (demo mode)

If available in the session, invoke; otherwise write the app from the templates
above.

- `dlstreamer-coding-agent` (open-edge-platform/skills) — Sub-path A pipeline
  authoring.
- `dlsps-user` (open-edge-platform/skills) — **not needed for a demo**; use it
  only if the PoC grows into a REST-driven Pipeline Server microservice, in
  which case switch back to the full-stack (`{{MODE}}=production`) path.
- `model-download` (open-edge-platform/edge-ai-libraries) — fetch/convert model
  IR for either sub-path.
