# System Requirements

This page provides detailed hardware, software, and platform requirements to help you set up and run the microservice efficiently.

## Supported Platforms

**Operating Systems**

- Ubuntu 24.04 LTS or later

**Hardware**

- Intel® Core™ Ultra processor with integrated GPU (validated on Panther Lake, PTL 358H), sharing system RAM
- At least **64 GB RAM** — default deployment target for `Qwen3.5-35B-A3B` (FP8, 60k context)
- At least **32 GB swap** — so the model load and KV cache can spill under peak memory pressure
- At least 128 GB disk space (model weights + Hugging Face cache)

## Software Requirements

**Required Software**:

- Docker 24.0
- Python 3.10

## Validation

- Ensure all required software are installed and configured before proceeding to [Get Started](../get-started.md).

## Supporting Resources

- [Overview](../index.md)
- [API Reference](../api-reference.md)
