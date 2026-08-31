# Release Notes: Smart Classroom

## Version 2026.2

**Release Date**: September 9, 2026

Smart Classroom 2026.2 refactors the backend around a **modular feature-module
architecture** and adds two new classroom AI capabilities — **VLM-based exam grading with
graded reports** and **Board (content-screen) OCR**. It also introduces a cross-platform
**Flutter application** for Content Search. All new capabilities run locally on Intel
hardware using OpenVINO.

**New**:

- **Flutter Content Search application** — a cross-platform (Windows Desktop and Web)
  Flutter + Riverpod client for the Content Search backend, delivering file ingestion,
  RAG-powered Q&A with cited sources, multi-turn conversations, and file management.
  - Runs from its own dedicated `config.yaml` so it can be
    deployed independently of the main Smart Classroom application.
  - Talks to a lightweight **standalone VLM service** (Qwen3-VL-8B) instead of requiring
    the full application stack, for faster startup and lower resource use.
  - Adds an agentic **Coding Companion** mode with skills that drive setup, ingestion, Q&A, file
    management, and health diagnostics from natural-language commands.

- **VLM-based exam grading and graded reports** — a new grading service that scores
  student papers against a teacher-provided rubric and produces per-student graded reports.
  - Runs as its own feature/service, gated by the `grading` feature flag.
  - Supports single-column and two-column exam page layouts.
  - Accepts student papers organized by directory (one folder per student).
  - Adds **Qwen3.5 9B** VLM support with configurable INT8/INT4 quantization.
  - Ships sample rubrics and sample exams for a guided quick test.

- **Board OCR** — extracts text written on the classroom content/whiteboard screen from an
  RTSP stream or recorded video.
  - Extracts frames using FFmpeg + Intel QSV and feeds them to an OCR reader with text
    normalization and deduplication.
  - Integrated into the audio-summary pipeline so recognized board text enriches the
    generated class summary.

**Improved**:

- **Modular feature-module architecture** — the backend is now composed of self-contained
  feature modules (`asr`, `summary`, `mindmap`, `topic_segmentation`, `video_analytics`,
  `board_ocr`, `content_search`, `qa`, `grading`, `report`), each exposing a common
  interface (router, `build`/`teardown`, and a UI descriptor).
  - Features are toggled independently via the `features` block in `config.yaml`.
  - A dependency-ordered registry bootstraps only the enabled features and detects
    dependency cycles at startup.
- **Unified Content Search Python environment** so that Content Search shares a single managed
  virtual environment with the rest of the application.
- **Externalized LLM prompts** to make prompt tuning easier without code changes.
- **Health checks** hardened against proxy interference.

## Version 2026.1

**Release Date**: June 17, 2026

Smart Classroom 2026.1, a modular, extensible framework for the Windows OS, adds a Content Search subsystem, document upload, text/image retrieval,
OCR, QnA, and multilingual processing including Mandarin/Chinese. This release also adds
WebRTC WHEP streaming, Intel® Wildcat Lake (WCL) platform support, and updates to audio transcription.

**New**:

- **Content Search module** for uploading documents and media, indexing them with
  OpenVINO™-accelerated embedding models, and retrieving results by text or image query.
- **Q&A support** in Content Search for querying uploaded content with locally running LLMs.
- **OCR** in Content Search with OpenVINO™ and PaddleOCR for printed and handwritten documents.
- **Mandarin/Chinese language support** for QnA and transcription pipelines.
- **File listing and file removal endpoints** in the Content Search API.
- **Config API endpoint** in Content Search for runtime search and embedding settings.
- **WebRTC WHEP streaming** for low-latency live video delivery.
- **Intel(R) Core(TM) Series 3** (Wildcat Lake) processor support.
- **Video start and end timestamps** in Content Search results for precise navigation.
- **Resource utilization monitoring** to cap pipeline resource usage.

**Improved**:

- Long audio transcription is now supported with and without speaker diarization.
- RTSP playback mode and file duration validation in the video ingestion pipeline.
- Content Search embedding models upgraded to multilingual and cross-lingual models.
- Batch embedding insertion for improved indexing throughput on large document sets.
- Local PyAnnote audio model caching for offline diarization loading.
- Pipeline startup reliability under concurrent load.
- YOLO model configuration and quantization setting updates.
- CMake configuration and build scripts for the gvasmartclassroom GStreamer plugin.
- Error tracking for pipeline status reporting.
- Video summarization output consistency.
- UI behavior to stop active streaming sessions automatically after 10 minutes.
- Support for DL Streamer 2026.1.
- Summary scoring formula updates and reranker configuration refactoring.
- Content Search download streaming optimization to reduce memory overhead for large file
  transfers.

**Fixed**:

- Crash in the video analytics pipeline.
- Noise in per-class attendance statistics in the video pipeline.
- Content Search cleanup when no task ID was present.
- Duplicate file entries caused by missing task IDs during upload.
- Inference request conflicts when embedding multiple documents concurrently.
- Incorrect video scaling in the HLS player at some resolutions.
- Encoding errors in video analytics output.
- Incorrect YOLO model quantization results.
- Content Search upload and delete operations under some conditions.
- Corrupted file handling in Content Search that could cause indexing failures.
- Hardcoded model name in the startup script; model name is now read from configuration.

## Version 2026.0

**Release Date**: April 1, 2026

The Smart Classroom application now offers a series after-class summary enhancements in the form of next‑generation real-time audio and visual analytics, giving teachers and schools a better understanding of classroom dynamics through AI‑driven summaries and engagement metrics.

The Education AI Suite now also includes built-in telemetry hooks and benchmarking.

**New**:

- **Speaker Diarization** (via the Audio Pipeline):
  - identifies teacher and student speakers using NPU-accelerated diarization
  - generates an interactive audio timeline for replay and analysis
  - enables time-coded navigation within class video recordings

- **Class Engagement Metrics – Audio**:
  - measure teacher and student speech duration
  - track questions asked and answered
  - track student-teacher interaction frequency

- **Class Engagement Metrics – Video**:
  - track student hand raises
  - track posture changes (stand up/sit down)
  - track teacher movement

- **Built‑in telemetry** to measure classroom workloads across Intel platforms (CPU core utilization, iGPU load, NPU load, memory usage, workload-specific performance counters)

- **Benchmarking scripts** to reproduce Intel internal performance measurements, and validate XPU performance

**Improved**:

- **Knowledge Graph UI** readability and formatting, and increased clarity when visualizing topic relationships

## Documentation and Source Code

- [GitHub](https://github.com/open-edge-platform/edge-ai-suites/tree/main/education-ai-suite)

## Previous releases

- [Release notes 2025](./release-notes/release-notes-2025.md)

<!--hide_directive
:::{toctree}
:hidden:

Release Notes 2025 <./release-notes/release-notes-2025.md>

:::
hide_directive-->