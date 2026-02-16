# System Requirements

This page summarizes the recommended environment for running Live Video Alert.

### Operating Systems

- Ubuntu 24.04.1 LTS

## Minimum Requirements

| **Component**       | **Minimum**                     | **Recommended**                                  |
|---------------------|---------------------------------|--------------------------------------------------|
| **Processor**       | 11th Gen Intel® Core™ Processor | Intel® Xeon® Platinum 8351N CPU @ 2.40GHz        |
| **Memory**          | 16 GB                           | 32 GB                                            |
| **Disk Space**      | 256 GB SSD                      | 256 GB SSD                                       |
| **GPU/Accelerator** | Intel® UHD Graphics             | Intel® Arc™ Graphics                             |

## Software Requirements

- Docker Engine and Docker Compose
- Intel® Graphics compute runtime (if using Intel GPU for inference acceleration)
- RTSP source reachable from the `live-video-alert` container (optional, can be added via UI)

## Network / Ports

Default ports (configurable via environment variables):

- `PORT=9000` (Dashboard UI and REST API)
- `METRICS_PORT=9090` (Live metrics WebSocket service)

## Model Requirements

The application automatically downloads VLM models on first run (~2GB). Supported models:

- `OpenVINO/Phi-3.5-vision-instruct-int4-ov` (default)
- `OpenVINO/InternVL2-2B-int4-ov` (alternative)

Configure via environment variables:
```bash
export OVMS_SOURCE_MODEL=OpenVINO/InternVL2-2B-int4-ov
export MODEL_NAME=InternVL2-2B
```

## Validation

Proceed to [Get Started](./get-started.md) once Docker is installed and internet connectivity is available for model downloads.
