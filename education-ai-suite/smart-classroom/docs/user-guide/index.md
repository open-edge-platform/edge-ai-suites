# Smart Classroom

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/education-ai-suite/smart-classroom">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/education-ai-suite/smart-classroom/README.md">
     Readme
  </a>
</div>
hide_directive-->

The Smart Classroom project is a modular, extensible framework designed to process and analyze
educational content using advanced AI models. It combines real-time video analytics with audio
transcription and summarization to provide comprehensive classroom intelligence.

This application provides an end-to-end workflow, starting from file uploads or live recording,
through parallel audio and video analysis, to generate insightful outputs like transcriptions,
summaries, mind maps, and classroom engagement statistics. You can monitor system performance,
switch between audio-video modes, and validate results seamlessly, ensuring an interactive and
efficient classroom experience.

The main features are as follows:

## Audio Pipeline

- **Audio transcription** with ASR models (e.g., Whisper, Paraformer)
- **Speaker diarization** using Pyannote Audio models
- **Summarization** using LLMs (e.g., Qwen, LLaMA) optimized with OpenVINO
- **MindMap generation** using Mermaid.js for visual diagram rendering
- **Content segmentation** for automatic topic extraction from transcripts
- **Semantic topic search** using FAISS vector indexing

## Video Analytics Pipeline

- **Real-time video analysis** across three concurrent camera streams (front, back, content)
- **Person detection and pose estimation** using YOLO models with 17-keypoint skeleton tracking
- **Person re-identification** for tracking individual students across frames
- **Classroom statistics** including student count, stand-up events, and hand-raise events

## Architecture

- **Plug-and-play architecture** for integrating new ASR, LLM, and video analytics models
- **API-first design** ready for frontend integration

<!--hide_directive
:::{toctree}
:hidden:

./get-started
./how-it-works
./application-flow
Release Notes <./release-notes>

:::
hide_directive-->
