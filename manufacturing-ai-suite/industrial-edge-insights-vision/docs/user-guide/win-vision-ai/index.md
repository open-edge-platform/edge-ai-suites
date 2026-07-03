# Win Vision AI

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/release-2026.1.0/manufacturing-ai-suite/industrial-edge-insights-vision/win-vision-ai">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.1.0/manufacturing-ai-suite/industrial-edge-insights-vision/win-vision-ai/README.md">
     Readme
  </a>
</div>
hide_directive-->

**Win Vision AI** is a Python application for running multiple AI inference pipelines
concurrently on Intel hardware (CPU / GPU / NPU) on Windows. Built on GStreamer and Intel®
DL Streamer, it handles the end-to-end pipeline — from camera or video input,
through OpenVINO™-accelerated detection and classification, to live RTSP / WebRTC
streaming and structured metadata output.

Configuration is YAML-driven: define your models, input sources, and outputs, then
run. Advanced users can supply raw GStreamer pipeline strings directly for full
control.

> **Platform:** Windows 11

## Layered Architecture

![Win Vision AI Layered Architecture](./_assets/winvisionai-arch-layered.drawio.svg)

For a more detailed description of the architecture and components, including inputs and
outputs, see [How It Works](./how-it-works.md).

## Supporting Resources

- [DL Streamer Documentation](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-libraries/dlstreamer/index.html)
  - [DL Streamer Supported Models](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-libraries/dlstreamer/supported_models.html)
  - [DL Streamer Model Conversion Scripts README](https://github.com/open-edge-platform/dlstreamer/blob/v2026.1.0/scripts/download_models/README.md)

<!--hide_directive
:::{toctree}
:hidden:

Get Started <./get-started.md>
How It Works <./how-it-works.md>
Release Notes <./release-notes.md>

:::
hide_directive-->
