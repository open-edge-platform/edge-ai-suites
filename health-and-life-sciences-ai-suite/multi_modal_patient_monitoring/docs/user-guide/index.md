## Multi-Modal Patient Monitoring

The Multi-Modal Patient Monitoring application is a reference workload that demonstrates how multiple AI pipelines can run simultaneously on a single Intel® platform, providing consolidated monitoring for a virtual patient.

It combines several AI services:

- **rPPG (Remote Photoplethysmography):** Contactless heart and respiratory rate estimation from facial video.
- **3D-Pose Estimation:** 3D human pose detection from video.
- **AI-ECG:** ECG rhythm classification from simulated ECG waveforms.
- **MDPNP:** Getting metrics of three simulated devices such as ECG, BP and CO2
- **Patient Monitoring Aggregator:** Central service that collects and aggregates vitals from all AI workloads.
- **Metrics Collector:** Gathers hardware and system telemetry (CPU, GPU, NPU, power) from the host.
- **UI:** Web-based dashboard for visualizing waveforms, numeric vitals, and system status.

Together, these components illustrate how vision- and signal-based AI workloads can be orchestrated, monitored, and visualized in a clinical-style scenario.

### Documentation Overview

Use the following pages to get started and understand the system:

- **[System Requirements](system-requirements.md)** – Hardware, software, and network requirements, plus an overview of the AI models used by each workload.
- **[System Design](system-design.md)** – High-level architecture, service responsibilities, and data/control flows.
- **[Get Started](get-started.md)** – Step-by-step instructions to build and run the application using `make` and Docker.

> This application is provided for development and evaluation purposes only and is *not* intended for clinical or diagnostic use.

