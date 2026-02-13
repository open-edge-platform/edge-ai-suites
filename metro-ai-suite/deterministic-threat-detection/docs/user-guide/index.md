# Deterministic Threat Detection with Time-Sensitive Networking (TSN)

This project demonstrates a Time-Sensitive Networking (TSN) 
sample application that delivers AI-processed video and 
sensor data with deterministic, low latency in a shared 
network.

This sample shows how TSN protects latency-sensitive AI 
and sensor workloads in industrial and edge AI deployments. 
The demonstration includes:

- Multi-camera video acquisition over Ethernet
- Time synchronization using **IEEE 802.1AS (gPTP)**
- End-to-end latency measurement using PTP timestamps
- AI inference on synchronized video frames
- MQTT-based data aggregation and visualization
- Network congestion impact from best-effort background traffic
- Traffic protection using **IEEE 802.1Qbv (Time-Aware Shaper)**

## Use Case

The use case involves multiple RTSP cameras streaming video to edge compute nodes for AI inference. Simultaneously, a sensor data producer generates telemetry data. Both inference results and sensor data are published over MQTT.

An aggregation node measures the end-to-end latency. By injecting background traffic and then enabling TSN features, the demonstration shows how TSN provides consistent and deterministic latency for critical data streams.



<!--hide_directive
:::{toctree}
:hidden:

get-started
how-tos

Source Code < https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite/deterministic-threat-detection/docs/user-guide >
:::
hide_directive-->