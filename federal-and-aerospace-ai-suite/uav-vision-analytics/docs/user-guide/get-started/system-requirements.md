<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# System Requirements

## Developer System

The developer system is used to build installation artifacts and prepare the bootable USB. The build flow has been verified on:

| Component | Minimum                                                          |
| --------- | ---------------------------------------------------------------- |
| OS        | Linux distribution or WSL environment                            |
| CPU       | Any modern x86-64 processor with virtualisation support          |
| Memory    | 16 GiB RAM                                                       |
| Storage   | 100 GiB free disk space (for image build workspace)              |
| USB       | 32 GiB USB drive (for bootable installation media)               |
| Network   | Internet access (or configured proxy) to fetch packages and ISOs |

### Prerequisites

#### Docker Setup

For Windows Subsystem for Linux (WSL), follow the steps in the [Windows WSL Guide](../how-to/set-up-windows-wsl.md).

Docker Engine is required because the build workflow uses Docker images and containers.

Install Docker Engine for your Linux distribution using the official Docker documentation:

- [Linux install overview](https://docs.docker.com/engine/install/)
- [Debian](https://docs.docker.com/engine/install/debian/)
- [Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [RHEL](https://docs.docker.com/engine/install/rhel/)
- [Fedora](https://docs.docker.com/engine/install/fedora/)

Configure Docker for [non-root usage and service startup after installation](https://docs.docker.com/engine/install/linux-postinstall/).

If you are behind a proxy, configure [Docker daemon proxy settings](https://docs.docker.com/config/daemon/systemd/).

#### Install Make on the Development System

```bash
sudo apt-get install -y make
```

#### Password Hash Tools

The build requires a SHA-512 password hash for the image credentials. Install at least one of the following:

```bash
# Option 1: openssl
sudo apt-get install -y openssl

# Option 2: mkpasswd (whois package)
sudo apt-get install -y whois
```

## Target (Host) System

The target system is the Intel edge node on which the provisioned OS and workloads will run. The following section provides detailed hardware, software, and platform requirements to help you set up and run the application efficiently.

### Operating Systems

- Ubuntu 24.04 LTS

### Minimum Requirements

| **Component**       | **Minimum Requirement**   |
|---------------------|---------------------------|
| **Memory**          | 16 GB                     |
| **Disk Space**      | 64 GB                     |

### Validated Platforms

| Product / Family     | CPU |  iGPU |  NPU |
|----------------------|-----------|------------|-----------|
| Intel® Core™ Ultra Processors Series 3 | ✓         | ✓          | ✓         |


> **Note:** Users can also create apps tailored to their use case using models supported by DL Streamer.
Check [the list of supported models](https://docs.openedgeplatform.intel.com/2026.2/edge-ai-libraries/dlstreamer/supported_models.html) for the latest information.

### Software Requirements

**Required Software**:

- Docker 27.3.1 or higher
- Python 3.10+
- Git
- `ffmpeg` (for RTSP stream playback and recording)
- `python3.12-venv` (for creating a Python virtual environment)

> `python3.12-venv` is required by `make model` to create a Python virtual environment.
> `ffmpeg` provides `ffplay` for viewing the RTSP output stream and `ffmpeg` for recording.

<!--
## Compatibility Notes
**Known Limitations**:
- GPU optimizations require Intel® integrated graphics or compatible accelerators.
-->

### Validation

- Ensure all dependencies are installed and configured before proceeding to
  [Get Started Standalone](./get-started-standalone.md)
  [Get Started SDK](./get-started-uavsdk.md)
