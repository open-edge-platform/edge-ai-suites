# Release Notes: Live Video Captioning

## Version 2026.1.0

**June 17, 2026**

**New**

- [Live Video Captioning RAG](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/live-captioning-rag/index.html)
  as an additional feature in Live Video Captioning, enabling Retrieval-Augmented Generation (RAG) chat.
- Integration of model-download service to simplify downloading before preparing the model.
- Added support for using the host machine's camera as an input source.
- Dynamically selects the default pipeline based on detected hardware such as GPU.
- Simplify the setup process of the application.
- Deployment with Helm chart.
- Enhancements in UI/UX for the Alert mode.
- Documentation updates.

**Known Issues**

- The sample application is not validated either on the Standalone or Developer Node
  versions of Edge Microvisor Toolkit.

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
