# Real Time Scene Understanding

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/live-video-analysis/real-time-scene-understanding">
	  GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/live-video-analysis/real-time-scene-understanding/README.md">
	  Readme
  </a>
</div>
hide_directive-->

**Real Time Scene Understanding** deploys AI-powered live video analysis for RTSP streams with FFMpeg pythonic bindings, PyAV and OpenVINO Vision Language Models (VLMs). You can process streaming video, run prompt-driven scene understanding, and monitor both system and inference performance from a web dashboard.

The key features are:

**VLM Model Support**: Configure separate alert and deep-analysis OpenVINO VLMs through environment settings, with model files mounted from `ov_models/`.

**Real-Time Streaming**: WebRTC-based low-latency video preview for live monitoring workflows.

**Prompt-Driven Scene Intelligence**: Run natural-language prompts against live frames for flexible scene interpretation.

**Performance Metrics**: Live charts for CPU/GPU/RAM plus inference metrics such as TTFT, TPOT, and throughput.

**Modular Architecture**: Containerized application, streaming, metrics, and object-storage services.

**Alert Mode**: Alert-oriented output styling for binary prompt responses (for example, "Yes"/"No").

## Use Cases

**Real-Time Monitoring**: Analyze security cameras, industrial lines, and public infrastructure with prompt-driven scene understanding.

**Operational Safety**: Detect safety-relevant conditions through targeted prompts in manufacturing, warehousing, and logistics environments.

**Accessibility and Summarization**: Generate concise, contextual scene descriptions to improve accessibility and operator awareness.

**Performance Benchmarking**: Compare VLM behavior across Intel hardware by tracking latency, throughput, and resource utilization.

<!--hide_directive
:::{toctree}
:hidden:

get-started.md
quick-start-guide.md
how-it-works.md
api-reference.md
known-issues.md
get-started/system-requirements.md
get-started/model-preparation.md
get-started/build-from-source.md
get-started/run-unit-tests.md
Release Notes <release-notes.md>

:::
hide_directive-->
