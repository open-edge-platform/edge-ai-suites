# System Requirements: Scenescape Use Case

## Software Requirements

- **Operating System:** Ubuntu 24.04 or later
- **Docker Engine** with Docker Compose V2
- [**Scenescape**](https://github.com/open-edge-platform/scenescape/tree/main)

## Hardware Requirements

| Component | Details |
|-----------|---------|
| **Basler ace U Camera (acA1920-40GC)** | GigE Vision camera with IEEE 1588v2 PTP hardware timestamping support |
| **AXIS RTSP Camera P3265-LVE** | General RTSP camera with optional support of NTP |
| **MOXA TSN Switch** | Managed switch supporting IEEE 802.1AS (gPTP), IEEE 802.1Qbv (Time-Aware Shaper), and IEEE 1588v2 |
| **Arrow Lake Host Machine** | Linux-based system with an Intel i226 TSN-capable network card |

> **Note:** You can use either Basler cameras or RTSP cameras for this workflow. Basler cameras provide hardware PTP timestamps, while RTSP cameras rely on software timestamps or NTP synchronization.
