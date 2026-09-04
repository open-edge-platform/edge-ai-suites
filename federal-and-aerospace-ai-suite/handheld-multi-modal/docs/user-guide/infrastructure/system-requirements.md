# System Requirements

This page provides detailed hardware, software, and platform requirements to
help you set up and run the Handheld Multi-Modal application efficiently.

## Supported Platforms

**Operating Systems**

- Ubuntu 24.04 LTS

## Minimum Requirements

| **Component**       | **Minimum Requirement**   |
|---------------------|---------------------------|
| **Memory**          | 16 GB                     |
| **Disk Space**      | 64 GB                     |

### Validated Platforms

| Product / Family     | CPU |  iGPU |  NPU |
|----------------------|-----------|------------|-----------|
| Intel® Core™ Ultra Processors Series 3 | ✓         | ✓          | ✓         |

> **Note:** Users can also create apps tailored to their use case using models supported by DL Streamer.
> Check [the list of supported models](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dlstreamer/supported_models.html) for the latest information.

## Software Requirements

**Required Software**:

- Docker 27.3.1 or higher
- Python 3.10+
- Git
- `ffmpeg` (for RTSP stream playback and recording)
- `python3.12-venv` (for creating a Python virtual environment)

> `python3.12-venv` is required by `make model` to create a Python virtual environment.
> `ffmpeg` provides `ffplay` for viewing the RTSP output stream and `ffmpeg` for recording.

## Validation

- Ensure all dependencies are installed and configured before proceeding to
  [Infrastructure Setup](../infrastructure-setup.md)
- Continue with [Install OEP SDKs](../install-oep-sdks.md)
- Then deploy the [Handheld Multi-Modal Application](../deploy-applications.md)
