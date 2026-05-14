# Release Notes: Live Video Captioning

## Version 2026.1.0-rc1

**May 14, 2026**

**New**

- Integrated model-download service as a prerequisite step to download and prepare the model.
- Implemented Helm chart support for deployment.
- Updated UI/UX for Alert mode.
- Added [Live Video Captioning RAG](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/live-captioning-rag/index.html) as an additional feature included in Live Video Captioning, enabling Retrieval-Augmented Generation (RAG) chat.

**Known Issues**

- The sample application is not validated on the EMT-S and EMT-D variants of the Edge Microvisor Toolkit.

## Version 1.0.0

**April 01, 2026**

Live Video Captioning is a new sample application, using DLStreamer and VLMs to produce captions
on live camera feed. It enables you to configure the VLM model used, prompt, frame selection,
the rate at which the captions are generated, frame resolution, and more. It also presents
usage metrics of CPU, iGPU, and memory. A rich UI displays all the configuration options, live
camera feed, and the generated text.

In addition, the sample application may generate alerts with custom prompts, with customizable
generation delay. Docker-based deployment is supported currently.

**New**

- Docker Compose stack integrating DLStreamer pipeline server, WebRTC signaling (mediamtx),
  TURN (coturn), and FastAPI dashboard.
- Multi-model discovery from `ov_models/`.
- Live captions via SSE and live metrics via WebSockets.
- Support for the live metrics service.
- A rich graphical user interface.

**Known Issues**

- Helm support is not available in this version.

**Upgrade Notes**

- If you change `.env` values (ports, `HOST_IP`, model paths), restart the stack:
  `docker compose down && docker compose up -d`.
