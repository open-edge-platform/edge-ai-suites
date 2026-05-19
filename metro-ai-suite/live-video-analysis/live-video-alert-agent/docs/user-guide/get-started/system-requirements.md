# System Requirements

This page summarizes the recommended environment for running Live Video Alert Agent.

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
- Intel® Graphics compute runtime (if using Intel GPU for inference acceleration)
- RTSP source reachable from the `live-video-alert-agent` container (optional, can be added via UI)

## Network / Ports

Default ports (configurable via environment variables):

- `PORT=9000` (Dashboard UI and REST API)
- `METRICS_PORT=9090` (Live metrics WebSocket service)

## Model Requirements

The application automatically downloads VLM models on first run (~2GB). The models are left to user to configure. For example.

- `OpenVINO/Phi-3.5-vision-instruct-int4-ov`
- `OpenVINO/InternVL2-2B-int4-ov`

Configure these via environment variables:

```bash
export OVMS_SOURCE_MODEL=OpenVINO/InternVL2-2B-int4-ov
```

The user is expected to acknowledge the licensing terms and conditions before selecting the model.

## Validation

Proceed to [Get Started](../get-started.md) once Docker is installed and internet connectivity is available for model downloads.
