<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# DL Streamer Coding Agent — User Guide

## Overview

The DL Streamer Coding Agent is a Claude Code skill that turns plain-English descriptions into working video-analytics applications. You describe what you want — it generates, builds, and validates a complete DL Streamer app.

**Skill location:** `<dlstreamer-repo>/.github/skills/dlstreamer-coding-agent/`
(where `<dlstreamer-repo>` is your local clone of the [DL Streamer repository](https://github.com/open-edge-platform/dlstreamer))

## Quick Start

1. Open Claude Code inside your local `dlstreamer` repository
2. Describe the video AI pipeline you want to build
3. The agent asks clarifying questions if needed, then generates and runs the app

That's it. No boilerplate, no manual GStreamer wiring.

## What to Include in Your Prompt

A good prompt answers these questions:

| What            | Why                          | Example                                   |
| --------------- | ---------------------------- | ----------------------------------------- |
| Video source    | Where to read frames from    | A Pexels URL, local file, or `rtsp://...` |
| AI model(s)     | What intelligence to apply   | "YOLOv11 for detection"                   |
| What to output  | What the app should produce  | "Annotated video + JSON with detections"  |
| Target hardware | Which accelerator to use     | "Intel Core Ultra 3, prefer GPU"          |
| App language    | Python, C++, or shell script | "Python application"                      |
| Where to save   | Output directory name        | "Save in `my_app/`"                       |

If you skip any of these, the agent will ask before proceeding.

## Example Prompts

**Simple — detection + tracking (shell script):**

```text
Create a bash script that detects and tracks people using YOLO26m and Mars-Small-128.
Input: https://videos.pexels.com/video-files/18552655/18552655-hd_1280_720_30fps.mp4
Output: annotated video file.
Optimized for Intel Core Ultra 3. Save in people_tracking/.
```

**Medium — license plate OCR (Python):**

```text
Build a Python app for license plate recognition:
- YOLOv11 for plate detection, PaddleOCR for text
- Input: video file or RTSP camera
- Output: annotated video + JSON with plate text
Save in license_plate_recognition/. Include README.
```

**Advanced — event-based recording:**

```text
Python app that records video clips only when people are detected:
- Input: RTSP camera (or file for testing)
- Detect people, start recording on detection, stop when gone
- Output: sequence of clips (save-1.mp4, save-2.mp4, ...)
Save in smart_nvr/.
```

**Conversion — DeepStream to DL Streamer:**

```text
Convert this DeepStream app to DL Streamer: [paste code or path]
Keep the same detection + classification + JSON output.
```

## What You Get

The agent generates a ready-to-run project:

```text
my_app/
├── my_app.py            # Main application (or .sh / .cpp)
├── export_models.py     # Downloads and converts AI models
├── requirements.txt     # Python dependencies
├── README.md            # How to set up and run
└── results/             # Output goes here at runtime
```

It also:

- Pulls the `intel/dlstreamer:latest` Docker image
- Downloads and converts models to OpenVINO format
- Downloads your test video
- Runs the app and checks that output is valid

## Supported Use Cases

| Category        | Examples                               |
| --------------- | -------------------------------------- |
| Detection       | YOLO (v8/v11/v26), SSD, RTDETR         |
| Tracking        | DeepSORT, SORT with re-ID models       |
| Text/OCR        | PaddleOCR for license plates, signs    |
| GenAI/VLM       | InternVL, MiniCPM, Qwen2.5-VL, SmolVLM |
| Multi-camera    | Shared models, cross-stream batching   |
| Mosaic          | Composite 2x2 / 3x3 grid views         |
| Smart recording | Event-triggered start/stop clips       |
| Streaming       | WebRTC output, RTSP input              |
| Conversion      | DeepStream Python/C++ → DL Streamer    |

## Tips

- **Name exact models** — "YOLOv11n" works better than "an object detector"
- **Provide a test video** — the agent validates the pipeline end-to-end
- **Say "run and check output"** — triggers automatic validation
- **Ask for README** — ensures you get setup docs with the code

## Troubleshooting

| Problem                         | Solution                                                |
| ------------------------------- | ------------------------------------------------------- |
| Docker pull fails               | Check network and `docker login`                        |
| Model export runs out of memory | Use a smaller model variant                             |
| Output video won't play         | Usually fixed by agent (EOS handling); re-run if needed |
| Very slow first run (5-10 min)  | Normal — GPU compiles shaders on first inference        |
| NPU inference fails             | Not all models support NPU; agent falls back to GPU     |

## More Examples

The skill includes additional example prompts at:
`<dlstreamer-repo>/.github/skills/dlstreamer-coding-agent/examples/`

- People detection + tracking
- License plate recognition
- Event-based smart NVR
- Multi-stream mosaic
- Pose estimation
- Safety compliance checks
- DeepStream conversion (Python and C++)

## Prerequisites

- Docker installed and running
- Python 3.10+
- Network access (Docker images, model downloads, test videos)
- Intel hardware with GPU recommended
