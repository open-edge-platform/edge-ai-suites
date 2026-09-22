# System Requirements

## Hardware Prerequisites

To ensure 30+ FPS performance and real-time inference, the following hardware is recommended:

| Component | Specification |
| :--- | :--- |
| **Processor** | Intel® Xeon® Scalable Processor or Intel® Core™ i9 (12th Gen+) |
| **Accelerator** | **Intel® Data Center GPU Flex Series** (Highly Recommended for high-density streams/transcoding) |
| **Memory** | 32 GB DDR4/DDR5 ECC |
| **Storage** | 512 GB NVMe SSD (High Endurance) |
| **Network** | Dual 10GbE Uplink (for Camera Streams + Cloud Backhaul) |

## Software Prerequisites

- **Operating System**: Ubuntu 22.04 LTS (Jammy Jellyfish)
- **Container Runtime**: Docker Engine 24.0+
- **Orchestration**: Docker Compose v2.20+
- **Drivers**: Intel® GPU Drivers (verified for Flex Series)

## Network Requirements

- **Ports**:
  - `1883`: MQTT Broker (Internal/External)
  - `3000`: Grafana Dashboard
  - `8080`: Web UI
  - `8086`: InfluxDB
- **Time Sync**: Local NTP Server connectivity is critical for multi-camera correlation.
