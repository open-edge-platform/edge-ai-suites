# System Requirements

This page summarizes the recommended environment for running Live Video Captioning.

## Hardware Platforms used for validation

- This application is specifically targeting the Core&trade; platforms. Intel® Core&trade; Ultra 2 and 3 with integrated GPU are supported currently.
- While there is no hard restriction in using this application on Intel® Xeon® platforms with/without Intel® Arc&trade; GPUs, the user is requested to raise a feature ticket in case of any requirement.

## Operating Systems used for validation

- Ubuntu: Refer to the official [documentation](https://dgpu-docs.intel.com/devices/hardware-table.html) for details on required kernel version. For the listed hardware platforms, the kernel requirement translates to Ubuntu 24.04 or Ubuntu 24.10 depending on the GPU used.

## Minimum Requirements

| **Component**       | **Minimum**                     | **Recommended**                                  |
|---------------------|---------------------------------|--------------------------------------------------|
| **Memory**          | 16 GB                           | 32 GB                                            |
| **Disk Space**      | 64 GB SSD                       | 128 GB SSD                                       |

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

Proceed to [Get Started](../get-started.md) once Docker is installed and at least one model is available in `ov_models/`.
