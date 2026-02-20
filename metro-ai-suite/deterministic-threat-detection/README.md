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

## How It Works

![DTD High-Level Architecture](./docs/user-guide/_assets/deterministic-threat-detection-architecture.svg)

The use case involves multiple RTSP cameras streaming video to edge compute nodes for AI
inference. Simultaneously, a sensor data producer generates telemetry data. Both inference
results and sensor data are published over MQTT.

An aggregation node measures the end-to-end latency. By injecting background traffic and then
enabling TSN features, the demonstration shows how TSN provides consistent and deterministic
latency for critical data streams.

To ensure synchronized operations across all devices, every machine in the system uses Precision Time Protocol (PTP) to align their clocks accurately.

An aggregation node collects the MQTT messages and calculates the end-to-end latency. To demonstrate the impact of Time-Sensitive Networking (TSN), background traffic is introduced into the network. By enabling TSN features, the system showcases how TSN guarantees consistent and deterministic latency for critical data streams, even under network congestion.

### Components

- **DL Streamer Pipeline Server (VA Pipeline):** Processes video frames, extracts metadata, and integrates AI inference results.
- **Live Camera Streaming:** A network camera streams video to the edge compute node.
- **Camera Frame Capture + AI Inference:** Captures video frames, performs AI inference, and publishes results with PTP timestamps.
- **TSN Switch:** A TSN switch that supports IEEE 802.1AS (PTP) and IEEE 802.1Qbv (Time-Aware Shaper).
- **Sensor Data:** A sensor data producer that generates telemetry data and publishes it over MQTT with PTP timestamps.
- **MQTT Aggregator:** Subscribes to MQTT topics, collects data, and visualizes end-to-end latency.
- **Traffic Injector:** A machine that generates best-effort background traffic using iperf to demonstrate the impact of congestion on latency-sensitive workloads.

## Learn More

- [Get Started](./docs/user-guide/get-started.md): For detailed instructions on how to set up the environment and run the demonstration.
- [How to Configure PTP](./docs/user-guide/how-to-guides/configure-ptp.md): For step-by-step guidance on setting up Precision Time Protocol (PTP) for time synchronization across devices.
- [MOXA TSN Switch Configuration](./docs/user-guide/how-to-guides/configure-moxa-switch.md): For instructions on configuring the MOXA TSN switch for the first time.
- [Enable TSN Traffic Shaping on MOXA Switch](./docs/user-guide/how-to-guides/enable-tsn-traffic-shaping.md): For details on how to enable IEEE 802.1Qbv (Time-Aware Shaper) on the MOXA switch to prioritize critical traffic.
- [Run RTSP Camera Capture and AI Inference](./docs/user-guide/how-to-guides/run-rtsp-camera-and-ai-inference.md): For details on how to set up and run the RTSP camera capture and AI inference pipelines.
- [Run Sensor Data Producer](./docs/user-guide/how-to-guides/run-sensor-data-producer.md): For instructions on how to set up and run the sensor data producer that generates telemetry data.
- [Run MQTT Aggregator and Visualization](./docs/user-guide/how-to-guides/run-mqtt-aggregator-and-visualization.md): For details on how to set up and run the MQTT aggregator that collects data and visualizes latency measurements.
- [Inject Background Traffic with iperf](./docs/user-guide/how-to-guides/run-traffic-injector.md): For instructions on how to use iperf to generate best-effort background traffic to demonstrate the impact of congestion on latency-sensitive workloads.
- [Release Notes](./docs/user-guide/release-notes.md): For information on new features, improvements, and bug fixes in each release of the project.
