<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-ai-suites/tree/release-2026.0.0/metro-ai-suite/deterministic-threat-detection">
     GitHub project
  </a>
  <a class="icon_document" href="https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.0.0/metro-ai-suite/deterministic-threat-detection/README.md">
     Readme
  </a>
</div>
hide_directive-->

# Deterministic Threat Detection

Welcome to the documentation for the Deterministic Threat Detection project. This guide provides all the information you need to understand, set up, and run this Time-Sensitive Networking (TSN) sample application.

This project demonstrates how to achieve deterministic, low-latency delivery of AI-processed video and sensor data in a shared network, protecting critical workloads from network congestion.

## How It Works

![DTD High-Level Architecture](./_assets/deterministic-threat-detection-architecture.svg)

The use case involves multiple RTSP cameras streaming video to edge compute nodes for AI
inference. Simultaneously, a sensor data producer generates telemetry data. Both inference
results and sensor data are published over MQTT.

An aggregation node measures the end-to-end latency. By injecting background traffic and then
enabling TSN features, the demonstration shows how TSN provides consistent and deterministic
latency for critical data streams.

To ensure synchronized operations across all devices, every machine in the system uses Precision Time Protocol (PTP) to align their clocks accurately.

An aggregation node collects the MQTT messages and calculates the end-to-end latency. To demonstrate the impact of Time-Sensitive Networking (TSN), background traffic is introduced into the network. By enabling TSN features, the system showcases how TSN guarantees consistent and deterministic latency for critical data streams, even under network congestion.

### Components

- **Live Camera Streams:** A network camera streams video to the edge compute node.
- **Sensor Data:** A sensor data producer that generates telemetry data and publishes it over MQTT with PTP timestamps.
- **DL Streamer Pipeline Server (VA Pipeline):** Captures and processes video frames, performs AI inference, and publishes the results with PTP timestamps over MQTT.
- **Time-Sensitive Networking Switch:** A TSN switch that supports IEEE 802.1AS (PTP) and IEEE 802.1Qbv (Time-Aware Shaper).
- **Electrical / Ethernet Noise:** A machine that generates best-effort background traffic using iperf to demonstrate the impact of congestion on latency-sensitive workloads.
- **Post-processing and Data Visualization:** Subscribes to MQTT topics, collects data, and visualizes end-to-end latency.

## Learn More

- [Get Started](./get-started.md)
- [How-to Guides](./how-to-guides.md)
- [Release Notes](./release-notes.md)

<!--hide_directive
:::{toctree}
:hidden:

get-started
how-to-guides
release-notes

:::
hide_directive-->
