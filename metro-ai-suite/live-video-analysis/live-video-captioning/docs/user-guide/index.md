<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/release-2026.0.0/metro-ai-suite/live-video-analysis/live-video-captioning">
     GitHub project
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.0.0/metro-ai-suite/live-video-analysis/live-video-captioning/README.md">
     Readme
  </a>
</div>
hide_directive-->

# Live Video Captioning

**Live Video Captioning** deploys AI-powered captioning for live video streams with Deep Learning Streamer (DL Streamer) and OpenVINO™ Vision Language Models. You can process RTSP streams, generate real-time captions, and monitor performance metrics on a dashboard.

The key features are:

**Multi-Model Support**: Switch between VLMs (InternVL2, Gemma-3, etc.) with automatic model discovery from `ov_models/`.

**Real-time Streaming**: WebRTC-based low-latency preview video delivery.

**Performance Metrics**: Live charts for CPU/GPU/RAM and inference metrics such as TTFT, TPOT, and throughput.

**Modular Architecture**: Containerized services with clearly separated backend, frontend, and pipeline configuration.

**Alert Mode**: Optional alert styling for binary classification prompts (“Yes”/“No”).

**Object-Detection-Model Support**: Optionally integrate YOLO-based detection models into the pipeline to enable object detection and frame filtering.

## Use Cases

**Real-time Video Analytics**: Monitor security cameras, industrial equipment, or public spaces with AI-powered scene understanding and automatic captioning.

**Accessibility Enhancement**: Generate live captions for video content, making streams accessible to users with hearing impairments.

**Performance Benchmarking**: Evaluate VLM performance on Intel® hardware by comparing throughput, latency, and resource utilization across different models and pipeline configurations.

**Intelligent Surveillance**: Deploy custom prompts (for example, “Is there a person in the frame?”) for security and safety monitoring workflows.

<!--hide_directive
:::{toctree}
:hidden:

get-started
how-it-works
alert-mode
object-detection-pipeline
api-reference
known-issues
Release Notes <release-notes.md>

:::
hide_directive-->
