# How It Works

This section provides a high-level view of how the application processes audio and video input through two parallel pipelines integrated with a modular backend architecture.

![High-Level System Diagram](./_assets/education-ai-suite-smart-class-backend-service-layer.drawio.svg)

## Inputs

You can upload audio recordings and video files, or provide RTSP video streams through the *Web-based UI layer*, which supports:

- Audio and video upload
- Viewing transcription, summaries, mind maps, and classroom statistics
- Monitoring video analytics streams with real-time overlays
- Localisation options (English/Chinese)

The uploaded media is passed to the Backend API, which acts as the gateway to the backend service layer and provides similar capabilities.

## Audio Pipeline

The audio pipeline handles speech-to-text conversion and content summarization:

- **Audio Pre-processing**
  Cleans and formats audio data using FFmpeg, chunking input into segments for optimal processing.

- **ASR Component (Automatic Speech Recognition)**
  Converts audio into text using integrated ASR providers:

  - FunASR (Paraformer)
  - OpenVINO
  - OpenAI (Whisper)

- **Speaker Diarization**
  Identifies and separates individual speakers using Pyannote Audio models. This could be enabled/disabled by modifying `config.yaml`

- **Summariser Component**
  Generates concise summaries of transcribed text using LLM providers:

  - iPexLLM
  - OpenVINO

- **Content Segmentation**
  The LLM segments the transcript into 15–25 topic-based sections, each is encoded and indexed into vector store. Users can then search lecture content by natural-language queries, retrieving the most relevant topic segments.

## Video Analytics Pipeline

The Video Analytics (VA) pipeline performs real-time video analysis using DL Streamer and OpenVINO, processing multiple concurrent video streams to extract classroom engagement data.

### Pipeline Architecture

The VA pipeline runs three independent processing streams simultaneously:

- **Front Video Pipeline** — Student-facing camera stream for detailed person tracking, pose estimation, posture classification, hand-raise recognition, and person re-identification
- **Back Video Pipeline** — Rear-view camera stream for broader classroom monitoring and basic pose analysis
- **Content Pipeline** — Interactive flat panel display (IFPD) or board capture, processed at 1 FPS for content frame analysis

Each pipeline is built as a DL Streamer processing graph with the following stages:

1. **Video Decode and Preprocessing** — Input from RTSP stream or video file is decoded and preprocessed with hardware acceleration (D3D11)
2. **Person Detection and Pose Estimation** — YOLO models (YOLOv8m-pose for front, YOLOv8s-pose for back) detect persons and estimate 17-keypoint skeletons per frame
3. **Posture Detection** — A custom DL Streamer element analyzes keypoint geometry to classify posture (sit/stand) and detect hand-raises
4. **Multi-branch Classification** — Detected persons are routed through parallel classification branches:
     - **ResNet-18** for activity/action classification
     - **MobileNet-V2** for lightweight classification (front pipeline)
     - **Person-ReID-retail-0288** for identity tracking across frames (front pipeline)
5. **Output** — Annotated video is streamed via RTSP through a MediaMTX media server; per-frame metadata is written as JSON for statistics aggregation

### Classroom Statistics

The VA pipeline aggregates per-frame metadata into classroom engagement statistics:

- **Student count** — Average number of students detected (sampled periodically)
- **Stand-up events** — Per-student stand-up detection with noise filtering
- **Hand-raise events** — Per-student hand-raise tracking with configurable confirmation thresholds
- **Per-student tracking** — Re-identified students are tracked across frames with unique IDs

### Streaming and Distribution

A **Media Server (MediaMTX)** receives processed video from all three pipelines and provides:

- RTSP streaming for real-time playback
- HLS/WebRTC streaming for browser-based viewing

## Metrics Collector

Monitors and collects:

- xPU utilisation for hardware performance
- LLM metrics for summarisation efficiency

## Outputs

- **Transcriptions, summaries, mind maps, and topic segments** can be accessed from the Web-based UI and file system. The path for file system is **/\<project-location>/\<your-project-name>/**. For example, `/storage/chapter-10/`
- **Semantic topic search** results are returned via the API, with similarity scores and time-range references into the original recording.
- **Classroom statistics** (student count, stand-up events, hand-raise events) are generated from the video analytics pipeline and displayed in the UI.
- **Video streams** with real-time detection overlays are available via RTSP and HLS/WebRTC.
- **Performance metrics** (e.g., utilisation, model efficiency) are displayed for monitoring.
- Localisation ensures outputs are available in multiple languages (English/Chinese).

## Learn More

- [System Requirements](./get-started/system-requirements.md): Hardware, software, supported models, and weight formats
- [Get Started](./get-started.md): Step-by-step setup instructions
- [Application Flow](./application-flow.md): End-to-end application flow
