# Deterministic Threat Detection with Time-Sensitive Networking (TSN) - Preview

The Deterministic Threat Detection with Time-Sensitive Networking (TSN) project demonstrates how to deliver deterministic, low-latency AI and sensor workloads in shared networks. This application is currently in preview.

---

## Overview

![Deterministic Threat Detection Architecture](../../docs/deterministic-threat-detection/user-guide/_assets/common-deterministic-threat-detection-architecture.svg)

| Component | Role |
|-----------|------|
| **Moxa Managed Switch TSN-G5000 Series** | Precision Time Protocol (PTP) Grandmaster clock, VLAN segmentation, and IEEE 802.1Qbv time-aware traffic shaping |
| **Arrow Lake Host (Intel® Ethernet Network Adapter I226)** | TSN-capable inference host; clock synchronized to the switch via PTP |
| **Camera(s)** | Video source; supports cameras that use the Real-Time Streaming Protocol (RTSP) with either the Network Time Protocol (NTP) or the generalized Precision Time Protocol (gPTP), or the Basler GigE cameras that use IEEE 1588 version 2 hardware Precision Time Protocol (PTP). |
| **Traffic Injector** | Runs `iperf3` to generate background congestion and demonstrate TSN protection |

This project demonstrates two complementary use cases for industrial edge AI, both using the TSN infrastructure to protect latency-sensitive streams from background congestion:

### Use Case 1 — Multi-Camera AI Inference with Deterministic Delivery

Deep Learning Streamer (DL Streamer) processes the RTSP camera streams from AXIS cameras for person detection. The DL Streamer then publishes the inference results and simulated sensor telemetry over MQTT with PTP timestamps. An MQTT aggregation node measures end-to-end latency in real time, demonstrating how TSN protects critical streams from iperf3 background congestion.

[Get Started — Use Case 1](../../docs/deterministic-threat-detection/user-guide/get-started.md)

Basler GigE cameras hardware-timestamp each frame with IEEE 1588v2 Precision Time Protocol (PTP). A patched GStreamer pipeline propagates these timestamps through DL Streamer into Scenescape for 3D multi-camera tracking. This use case measures how TSN congestion affects Higher Order Tracking Accuracy (HOTA) and demonstrates that traffic shaping restores accuracy to the baseline.

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

- [Get Started — Use Case 1](../../docs/deterministic-threat-detection/user-guide/get-started.md)
- [Get Started — Use Case 2](../../docs/deterministic-threat-detection/user-guide/get-started-scenescape.md)
- [How-to Guides](../../docs/deterministic-threat-detection/user-guide/how-to-guides.md)
- [Release Notes](../../docs/deterministic-threat-detection/user-guide/release-notes.md)

## Key References

- **Moxa Managed Switch TSN-G5000 Series:** [PTP Grandmaster, VLAN segmentation, and IEEE 802.1Qbv shaping](https://www.moxa.com/en/products/industrial-network-infrastructure/ethernet-switches/layer-2-managed-switches/tsn-g5008-series)
- **Intel Ethernet Network Adapter I226:** TSN-capable Ethernet controller for Arrow Lake hosts
- **IEEE 802.1Qbv standard:** Time-Aware Scheduler for traffic isolation
- **Scenescape:** [3D multi-camera object tracking](https://github.com/open-edge-platform/scenescape)
- **DL Streamer:** [Intel's video processing and AI inference pipeline](https://github.com/openvinotoolkit/dlstreamer)
