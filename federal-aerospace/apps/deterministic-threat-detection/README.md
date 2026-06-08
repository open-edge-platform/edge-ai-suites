# Deterministic Threat Detection with Time-Sensitive Networking (TSN) - Preview

Welcome to the documentation for the Deterministic Threat Detection project—a Time-Sensitive Networking (TSN) demonstration showing how to deliver deterministic, low-latency AI and sensor workloads in shared networks. This application is currently in preview.

---

## Overview

![Deterministic Threat Detection Architecture](../../docs/deterministic-threat-detection/user-guide/_assets/common-deterministic-threat-detection-architecture.svg)

| Component | Role |
|-----------|------|
| **MOXA TSN Switch (TSN-G5000)** | PTP Grandmaster clock, VLAN segmentation, IEEE 802.1Qbv time-aware traffic shaping |
| **Arrow Lake Host (Intel i226 NIC)** | TSN-capable inference host; clock synchronized to the switch via PTP |
| **Camera(s)** | Video source; supports either RTSP cameras (NTP/gPTP) or Basler GigE cameras (IEEE 1588v2 hardware PTP) |
| **Traffic Injector** | Runs `iperf3` to generate background congestion and demonstrate TSN protection |

This project demonstrates two complementary use cases for industrial edge AI, both using TSN infrastructure to protect latency-sensitive streams from background congestion:

### Use Case 1 — Multi-Camera AI Inference with Deterministic Delivery

RTSP camera streams from AXIS cameras are processed by DL Streamer for person detection. Inference results and simulated sensor telemetry are published over MQTT with PTP timestamps. An MQTT aggregation node measures end-to-end latency in real time, demonstrating how TSN protects critical streams from iperf3 background congestion.

[Get Started — Use Case 1](../../docs/deterministic-threat-detection/user-guide/get-started.md)

Basler GigE cameras hardware-timestamp each frame with IEEE 1588v2 PTP. A patched GStreamer pipeline propagates these timestamps through DL Streamer into Intel® SceneScape for 3D multi-camera tracking. This use case measures how TSN congestion affects HOTA tracking accuracy and demonstrates that traffic shaping restores accuracy to baseline.

[Get Started — Use Case 2](../../docs/deterministic-threat-detection/user-guide/get-started-scenescape.md)

---

## Application Deployment

### Option 1 — Git Clone

Clone the full repository and navigate to the application directory:

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites/federal-aerospace/apps/deterministic-threat-detection
```

### Option 2 — Download ZIP Archive

Download and extract the standalone application package:

```bash
curl -OjL https://github.com/open-edge-platform/edge-ai-suites/releases/download/fedaero-latest/deterministic-threat-detection.zip
unzip deterministic-threat-detection.zip
cd deterministic-threat-detection
```

> **Note:** The documentation assumes paths relative to the `edge-ai-suites/federal-aerospace/apps/deterministic-threat-detection` directory. If you used the ZIP archive, replace `edge-ai-suites/federal-aerospace/apps/deterministic-threat-detection` with the path to your extracted `deterministic-threat-detection` folder wherever it appears in the guides.

---

## Documentation

- [Get Started — Use Case 1](./docs/user-guide/get-started.md)
- [Get Started — Use Case 2](./docs/user-guide/get-started-scenescape.md)
- [How-to Guides](./docs/user-guide/how-to-guides.md)
- [Release Notes](./docs/user-guide/release-notes.md)

## Key References

- **MOXA TSN-G5000:** [PTP Grandmaster, VLAN segmentation, IEEE 802.1Qbv shaping](https://www.moxa.com/en/products/industrial-network-infrastructure/ethernet-switches/en-50155-switches/tsn-g5004-series)
- **Intel i226 NIC:** TSN-capable Ethernet controller for Arrow Lake hosts
- **IEEE 802.1Qbv:** Time-Aware Scheduler for traffic isolation
- **Intel® SceneScape:** [3D multi-camera object tracking](https://github.com/open-edge-platform/scenescape)
- **DL Streamer:** [Intel's video processing and AI inference pipeline](https://github.com/openvinotoolkit/dlstreamer)
