# Deterministic Threat Detection with Time-Sensitive Networking (TSN)

This project demonstrates a Time-Sensitive Networking (TSN) sample application for
deterministic, low-latency delivery of AI-processed video and sensor data in a shared network
with other traffic.

## Overview

This sample application showcases how TSN can be used to protect latency-sensitive AI and
sensor workloads in industrial and edge AI deployments. It demonstrates:

- Multi-camera video acquisition over Ethernet
- Precise time synchronization using **IEEE 802.1AS (gPTP)**
- End-to-end latency measurement using PTP timestamps
- AI inference on synchronized video frames
- MQTT-based data aggregation and visualization
- The impact of network congestion from best-effort background traffic
- Traffic protection using **IEEE 802.1Qbv (Time-Aware Shaper)**

## Use Case

The use case involves multiple RTSP cameras streaming video to edge compute nodes for AI
inference. Simultaneously, a sensor data producer generates telemetry data. Both inference
results and sensor data are published over MQTT.

An aggregation node measures the end-to-end latency. By injecting background traffic and then
enabling TSN features, the demonstration shows how TSN provides consistent and deterministic
latency for critical data streams.

## Getting Started

For detailed instructions on how to set up the environment and run the demonstration, please
refer to the user guide in the `docs/user-guide` directory. Start with the [Overview](./docs/user-guide/index.md).
