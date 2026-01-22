# System Requirements

This page summarizes the recommended environment for running Live Video Captioning.

### Operating Systems

- Ubuntu 24.04.1 LTS

<!--
**Hardware Platforms**
- Intel® Core™ processors (Intel® Core™ i5 processor or higher)
- Intel® Xeon® processors (recommended for large deployments)
-->

## Minimum Requirements

| **Component**       | **Minimum**                     | **Recommended**                      |
|---------------------|---------------------------------|--------------------------------------|
| **Processor**       | 11th Gen Intel® Core™ Processor | Intel® Core™ Ultra 7 Processor 155H  |
| **Memory**          | 8 GB                            | 8 GB                                 |
| **Disk Space**      | 256 GB SSD                      | 256 GB SSD                           |
| **GPU/Accelerator** | Intel® UHD Graphics             | Intel® Arc™ Graphics                 |

## Software Requirements

- Docker Engine and Docker Compose
- RTSP source reachable from the `dlstreamer-pipeline-server` container

## Network / Ports

Default ports (configurable via `.env`):

- `EVAM_HOST_PORT=8040` (Pipeline management REST API)
- `WHIP_SERVER_PORT=8889` (WebRTC/WHIP signaling)
- `DASHBOARD_PORT=4173` (Dashboard UI)

## Model Requirements

Models directory must be present under `ov_models/` and include OpenVINO IR artifacts (for example):

- `openvino_language_model.xml`
- `openvino_vision_embeddings_model.xml`

## Validation

Proceed to [Get Started](./get-started.md) once Docker is installed and at least one model is available in `ov_models/`.
