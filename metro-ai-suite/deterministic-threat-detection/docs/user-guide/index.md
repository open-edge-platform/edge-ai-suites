# Deterministic Threat Detection

Deterministic Threat Detection is a Time-Sensitive Networking (TSN) sample application for
deterministic, low-latency delivery of AI-processed video and sensor data in a shared network
with other traffic.

## Use Case

This sample application showcases how TSN can be used to protect latency-sensitive AI and
sensor workloads in industrial and edge AI deployments. It demonstrates:

- Multi-camera video acquisition over Ethernet
- Precise time synchronization using **IEEE 802.1AS (gPTP)**
- End-to-end latency measurement using PTP timestamps
- AI inference on synchronized video frames
- MQTT-based data aggregation and visualization
- The impact of network congestion from best-effort background traffic
- Traffic protection using **IEEE 802.1Qbv (Time-Aware Shaper)**

This use case demonstrates how Time-Sensitive Networking (TSN) enables deterministic and
reliable delivery of AI-processed video and sensor data in a shared Ethernet network carrying
mixed traffic.

Multiple Ethernet-connected RTSP cameras stream video to edge compute nodes where each frame
is timestamped using a PTP-synchronized system clock and processed through an AI inference
pipeline. In parallel, a simulated sensor data producer generates time-stamped telemetry data.
Both video inference results and sensor data are published over MQTT to a centralized
aggregation node.

The aggregation node subscribes to all MQTT topics and measures end-to-end latency by comparing
the frame or sensor generation timestamp with the message reception time. Since all devices
share a common time reference through IEEE 802.1AS (gPTP), the measured latency accurately
reflects network and processing delays.

To evaluate the impact of network congestion, best-effort background traffic is intentionally
injected using iPerf. Without TSN traffic shaping, this background traffic interferes with
critical video and sensor data, resulting in increased latency and jitter.

The experiment then enables VLAN-based traffic separation and IEEE 802.1Qbv (Time-Aware Shaper)
on a TSN-capable switch to prioritize critical traffic. With TSN enabled, the system
demonstrates consistent and deterministic latency for video and sensor data, even in the
presence of heavy background traffic.

This use case validates how TSN can be used to protect latency-sensitive AI and sensor
workloads in industrial and edge AI deployments.

## Learn More

- [Get Started Guide](./get-started.md): Configuration and run steps.
- [How-to Guides](./how-to-guides.md): A collection of dedicated how-to guides.

<!--hide_directive
:::{toctree}
:hidden:

get-started
how-to-guides

:::
hide_directive-->