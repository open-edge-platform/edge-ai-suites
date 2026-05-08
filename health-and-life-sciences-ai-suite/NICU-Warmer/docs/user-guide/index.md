# NICU Warmer — Intelligent Patient Monitoring

The NICU Warmer application is a reference workload that demonstrates how multiple AI models
can run simultaneously in a single GStreamer pipeline on Intel® hardware, providing real-time
neonatal patient monitoring in a hospital warmer bed scenario.

It combines several AI workloads:

- **Object Detection (×3):** Custom OpenVINO FP32 models for detecting patient presence,
  caretaker presence, and warmer latch clip status — all running on Intel Arc GPU.
- **rPPG (Remote Photoplethysmography):** Contactless heart rate and respiratory rate
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

> **Disclaimer:** This application is provided for development and evaluation purposes only and
> is _not_ intended for clinical or diagnostic use.
