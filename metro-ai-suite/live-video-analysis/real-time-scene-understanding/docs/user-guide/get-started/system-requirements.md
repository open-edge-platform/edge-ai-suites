# System Requirements

This page summarizes the recommended environment for running Real Time Scene Understanding.

## Hardware Platforms used for validation

- This application is specifically targeting Intel&reg; Core&trade; platforms. Intel&reg; Core&trade; Ultra 2 and 3 with integrated GPU are currently supported.
- Intel&reg; Core&trade; Ultra platforms with integrated NPU can run compatible VLMs; model and resolution support vary by device.
- While there is no hard restriction in using this application on Intel&reg; Xeon&reg; platforms with or without Intel&reg; Arc&trade; GPUs, users are requested to raise a feature ticket in case of any requirement.

## Operating Systems used for validation

- Ubuntu: Refer to the official [documentation](https://dgpu-docs.intel.com/devices/hardware-table.html) for details on required kernel version. For the listed hardware platforms, the kernel requirement translates to Ubuntu 24.04 or Ubuntu 24.10 depending on the GPU used.

## Minimum Requirements

| **Component**  | **Minimum** | **Recommended** |
|----------------|-------------|-----------------|
| **Memory**     | 16 GB       | 32 GB           |
| **Disk Space** | 64 GB SSD   | 128 GB SSD      |

## Software Requirements

- Docker Engine and Docker Compose
- Intel&reg; Graphics compute runtime (if using Intel GPU for inference acceleration)
- RTSP source reachable from the `real-time-scene-understanding` container (optional, can be added via UI)

## Network / Ports

Default host ports (configurable in `.env`):

- `PORT=9100` (Dashboard UI and REST API; Compose maps this host port to container port `9100`)
- `METRICS_SERVICE_PORT=9090` (Live metrics SSE service)
- `WEBRTC_SIGNALING_PORT=8889` (MediaMTX WebRTC/WHEP signaling)
- `8189/udp` (MediaMTX WebRTC media)
- `3478/udp` (Coturn TURN service)

Compose publishes the dashboard host port through `PORT` (default `9100`); add `PORT` to `.env` to change it. The container listens on port `9100`. The `DASHBOARD_PORT` value in `.env.example` does not change the host port mapping.

## Model Requirements

The application uses two VLM models. The alert model performs frame-level alert gating, and the deep-analyzer model processes segmented clips. The deep-analyzer model must support video input. The configured models are `Qwen3-VL-2B-Instruct` for the alert pipeline and `Qwen3-VL-8B-Instruct` for deep analysis.

Configure model selection via `.env` file as below:

- ALERT_VLM_MODEL=Qwen3-VL-2B-Instruct
- ALERT_VLM_DEVICE=CPU
- DEEP_ANALYZER_MODEL=Qwen3-VL-8B-Instruct
- DEEP_ANALYZER_DEVICE=GPU

These are the values in `.env.example` and match the model-preparation commands. Download or prepare them for the configured device and make sure their directory names match the model settings under `ov_models/<device-lowercase>/<model-name>/`. The application can use pre-converted OpenVINO models. The model directory names are:

- `Qwen3-VL-2B-Instruct`
- `Qwen3-VL-8B-Instruct`

Model files can also be prepared using the provided scripts and model directories in this repository (for example, `model_download_scripts/download_models.sh` and `ov_models/`). Please refer to the [Model Preparation Guide](./model-preparation.md) for the steps.

> **Note:** Pre-converted OpenVINO IR VLMs can avoid local model conversion. When choosing one, verify compatibility with the OpenVINO GenAI runtime and target device used by this application. Browse models from the [OpenVINO organization on Hugging Face](https://huggingface.co/OpenVINO) and its [VLM collection](https://huggingface.co/collections/OpenVINO/visual-language-models).

## Validation

Proceed to [Get Started](../get-started.md) once Docker is installed and internet connectivity is available for model downloads.
