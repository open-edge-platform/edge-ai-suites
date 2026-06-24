# NICU Warmer — Intelligent Patient Monitoring

::::{container} component_header_row
<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/release-2026.1.0/health-and-life-sciences-ai-suite/NICU-Warmer">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.1.0/health-and-life-sciences-ai-suite/NICU-Warmer/README.md">
     Readme
  </a>
  </a>
  <a class="icon_download" href="https://huggingface.co/Intel/latch-detect">
     latch-detect model
  </a>
  <a class="icon_download" href="https://huggingface.co/Intel/patient-present">
     patient-present model
  </a>
  <a class="icon_download" href="https://huggingface.co/Intel/people-present">
     people-present model
  </a>
</div>
hide_directive-->

> Note!
> This application is for **reference and evaluation purposes**. It is
  **not intended for direct use in clinical or diagnostic environments** and is not
  validated as such.
::::

The NICU Warmer application is a reference solution that demonstrates how multiple AI models
can run simultaneously in a single GStreamer pipeline on Intel® hardware, providing workloads
that mimic real-time neonatal patient monitoring in a simulated hospital warmer bed scenario.

It combines several representative AI workloads:

- **Object Detection (×3):** Custom OpenVINO FP32 models for detecting patient presence,
  caretaker presence, and warmer latch clip status — all running on Intel Arc GPU.
- **rPPG (Remote Photoplethysmography):** Contactless heart and respiratory rate
  estimation from facial video using MTTS-CAN, running on CPU.
- **Action Recognition:** Kinetics-400 encoder/decoder model mapped to 11 NICU-specific
  activity categories, running on Intel NPU (AI Boost).
- **Metrics Collector:** Gathers hardware and system telemetry (CPU, GPU, NPU, memory, power)
  from the host.
- **UI:** Web-based React dashboard for visualizing detections, vital signs, activity, and
  system performance in real time.

Together, these components illustrate how vision-based AI workloads can be orchestrated across
Intel GPU, NPU, and CPU, monitored, and visualized in a clinical-style scenario.

## Supporting Resources

- [Get Started](./get-started.md) – Step-by-step instructions to build and run the application
  using `make` and Docker.
- [System Requirements](./get-started/system-requirements.md) – Hardware, software, and network
  requirements, plus an overview of the AI models used by each workload.
- [How It Works](./how-it-works.md) – High-level architecture, service responsibilities, and
  data/control flows.
- [Release Notes](./release-notes.md) – Version history and known issues.


<!--hide_directive
:::{toctree}
:hidden:

Get Started <get-started.md>
How It Works <how-it-works.md>
Release Notes <release-notes.md>

:::
hide_directive-->
