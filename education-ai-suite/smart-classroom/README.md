# 🎓 Smart Classroom

The **Smart Classroom** project is a modular, extensible framework designed to process and summarize educational content using advanced AI models. It supports transcription, summarization, mindmap generation and future capabilities like video understanding and real-time analysis.

The main features are as follows:

#### Audio Pipeline

- Audio transcription with ASR models (e.g., Whisper, Paraformer)
- Speaker diarization using Pyannote Audio models (optional)
- Summarization using powerful LLMs (e.g., Qwen, LLaMA)
- MindMap generation using Mermaid.js for visual diagram rendering of the summary
- Content segmentation for automatic topic extraction from transcripts

#### Video Analytics Pipeline

- Real-time video analysis across three concurrent camera streams (front, back, content)
- Person detection and pose estimation using YOLO models with keypoint skeleton tracking
- Person re-identification for tracking individual students across frames
- Classroom statistics including student count, stand-up events, and hand-raise events

#### Architecture

- Plug-and-play architecture for integrating new ASR, LLM, and video analytics models
- API-first design ready for frontend integration

## Get Started

To see the system requirements and other installations, see the following guides:

- [System Requirements](./docs/user-guide/get-started/system-requirements.md): Check the hardware and software requirements for deploying the application.
- [Get Started](./docs/user-guide/get-started.md): Follow step-by-step instructions to set up the application.
- [Application Flow](./docs/user-guide/application-flow.md): Check the flow of application.

## How It Works

The architecture follows a modular, dual-pipeline design for comprehensive classroom analysis.

The **audio pipeline** begins with audio preprocessing, where FFmpeg chunks input audio into smaller segments for optimal handling. These segments are processed by an **ASR transcriber** (e.g., Whisper or Paraformer) to convert speech into text. An **LLM summariser** (such as Qwen or Llama), optimised through frameworks like OpenVINO, or IPEX, generates concise summaries delivered via the output handler.

The **video analytics pipeline** processes up to three concurrent camera streams (front, back, content) through DL Streamer-based processing graphs. Each stream passes through **YOLO-based person detection and pose estimation**, followed by **posture classification** (sit/stand, hand-raise) and **multi-model classification** (ResNet-18, MobileNet-V2, Person-ReID). All models run on OpenVINO with NPU by default. Processed video is streamed via a **MediaMTX RTSP server**, and per-frame metadata is aggregated into classroom engagement statistics.

<p align="center">
  <img src="./docs/user-guide/_assets/architecture.svg" alt="High-Level Audio Pipeline Diagram" width="80%">
</p>
<p align="center">
  <img src="./docs/user-guide/_assets/video-pipeline.svg" alt="High-Level Video Pipeline Diagram" width="80%">
</p>

For more information see [How it works](./docs/user-guide/how-it-works.md)

## Learn More

- [Release Notes](./docs/user-guide/release-notes.md)
