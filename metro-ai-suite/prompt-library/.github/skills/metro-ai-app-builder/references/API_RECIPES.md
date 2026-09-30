<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# API recipes — media/analytics stacks and their delegate routing

The **API recipe** answer (Step 1, Q8) is a **routing** signal: each recipe is a
different media + analytics API stack that requires a **different delegate skill
or code path**. Load this in Step 2 when the API-recipe axis is set (or when you
resolve `auto` to a concrete recipe). This takes precedence over the general
catalog for media/analytics use cases.

## Recipes → delegate routing

| API recipe | What it is | Route to (primary) | Supporting |
|---|---|---|---|
| **DL Streamer (DLS)** | GStreamer + Intel DL Streamer inference elements (`gvadetect`/`gvaclassify`/`gvawatermark`) — pipelines and sample apps. | **`dlstreamer-coding-agent`** (the DLS skill). **Not** `metro-ai-apps-recipe`. | `model-download-user` (IR) |
| **OpenVINO + OpenCV** | A custom app using the OpenVINO runtime for inference and OpenCV for capture/decode/pre-post. | OpenVINO custom-code path — a minimal Python app (load → `compile_model` → infer → post-process) per the OpenVINO docs; no dedicated skill. | `model-download-user` (IR) |
| **OVMS + FFmpeg** | Model served by OpenVINO Model Server (OVMS) over its API, with FFmpeg handling media I/O. | OVMS model-serving path — stand up OVMS with an OVMS-ready model, FFmpeg glue code for decode/encode; no dedicated skill. | `model-download-user` (OVMS-ready IR) |

## Key distinction — DLS vs the recipe stack

- **API recipe = DL Streamer** → the user wants a **DL Streamer pipeline / app**.
  Route to **`dlstreamer-coding-agent`**.
- **Packaging = microservice / full end-to-end stack** → the user wants the
  operable analytics **stack** (DLSPS + WebRTC + Node-RED + Grafana + alerts).
  Route to **`metro-ai-apps-recipe`**. The recipe uses DL Streamer under the hood,
  but it is selected by the **packaging** axis, not by the DLS API-recipe answer.

So: choosing "DL Streamer" as the API recipe does **not** route to
`metro-ai-apps-recipe`; choosing the microservice/end-to-end packaging does.

## Resolving `auto`

When API recipe is `auto`, pick from packaging + outcome:

- Vision **microservice / full stack** → `metro-ai-apps-recipe` (DLSPS under the
  hood).
- Vision **demo / function / port**, or "a pipeline/app in code" → **DL Streamer**
  → `dlstreamer-coding-agent`.
- A **model-serving API** the user will call from their own code → **OVMS +
  FFmpeg**.
- A **minimal self-contained inference app** → **OpenVINO + OpenCV**.

Always pair a custom-code recipe (OV+OpenCV, OVMS+FFmpeg) with
`model-download-user` when a specific IR / OVMS-ready model is required.
