# System Requirements

This section shows the hardware, software, and platform requirements to help you set up and run Smart Traffic Intersection Agent efficiently.

The agent currently supports CPU- and GPU-based runs, and runs in the context of video summary pipeline. Hence, the system requirements is as per the documentation in the sample application.

## Supported Operating Systems

- Ubuntu 22.04 LTS or later
- Other Linux distributions with Docker support

## Hardware Requirements

| Component | Minimum | Recommended |
|---|---|---|
| CPU | Intel® Core™ i5 or equivalent | Intel® Core™ Ultra or Intel® Xeon® processor |
| RAM | 16 GB | 32 GB or more |
| Disk Space | 50 GB free | 100 GB free |
| GPU (optional) | — | Intel® integrated GPU (iGPU) for accelerated VLM inference |
| Network | Internet access for weather API and model downloads | — |

## Software Requirements

- Docker Engine version 24.0 or later
- Docker Compose v2: [Installation Guide](https://docs.docker.com/compose/install/)
- Python version 3.10 or later
- Git (for cloning the repository)
- A Hugging Face account and access token (for downloading VLM models)

## Other Requirements

- **MQTT Broker**: An MQTT broker for traffic data streaming (included in the deployment stack)
- **Hugging Face Token**: Required to pull VLM model weights. See [Hugging Face Tokens](https://huggingface.co/docs/hub/security-tokens) for details.
- **Network Ports**: The agent requires available ports for the backend API (default: 8081) and UI (default: 7860). Ensure these are not in use, or leave them empty in the configuration to use ephemeral ports.

## Validation

- Ensure all required software is installed and configured before proceeding to [Get Started](../get-started.md).

## Learn More

- [Overview](../index.md)
- [API Reference](../api-reference.md)
