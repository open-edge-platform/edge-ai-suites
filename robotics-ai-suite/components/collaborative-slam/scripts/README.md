<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Collaborative SLAM Scripts

## Build C-SLAM incrementally Script (incr-build.sh)

These scripts may be used to build the collaborative SLAM Debian packages from source code and install them into your system.

It is recommended these scripts be used with the development container supplied here: `applications.robotics.mobile.amr-common/dev/dev-container/`

Remember to either adjust the hard-coded folder path contained in each script, or set the appropriate environment variable[s] used within, to match your development environment.

- Use `incr-build.sh` to compile the C-SLAM incrementally. Specify an input parameter: 1 (default) - SSE CPU, 2 - LZE GPU, 3 - AVX2 CPU


## Local Build Script Usage (uni-build.sh)

This README describes how to use the build script locally using Docker containers for both ROS Humble and ROS Jazzy distributions.

## Prerequisites

- Docker installed and running
- Access to the Intel AMR registry: `amr-registry.caas.intel.com`
- Build script `uni-build.sh` located in the `scripts/` directory

## Usage

### For ROS Humble

1. **Start the Docker container:**
   ```bash
   docker run -it --rm \
     -v $(pwd):/workspace \
     -w /workspace \
     -v /tmp/cslam_deb_packages:/tmp/cslam_deb_packages \
     --cpus="6.0" \
     --memory="10g" \
     --memory-swap="12g" \
     amr-registry.caas.intel.com/edge-controls/amr-build:humble \
     bash

2. **Run the build script for humble:**
    ```bash
    ./uni-build.sh humble 2 > build_humble.log 2>&1

    Build Parameters
    - First parameter: ROS distribution (jazzy, humble)
    - Second parameter (optional): Number of parallel compilation jobs
    Default: Auto-detect (uses all available CPU cores)
    Recommended for local development: 2 or 1
    CI/Production: Omit for maximum performance

### For ROS Jazzy

1. **Start the Docker container:**
   ```bash
   docker run -it --rm \
     -v $(pwd):/workspace \
     -w /workspace \
     -v /tmp/cslam_deb_packages:/tmp/cslam_deb_packages \
     --cpus="6.0" \
     --memory="10g" \
     --memory-swap="12g" \
     amr-registry.caas.intel.com/edge-controls/amr-build:jazzy \
     bash

2. **Run the build script for jazzy:**
    ```bash
    ./uni-build.sh jazzy 2 > build_jazzy.log 2>&1

    Build Parameters
    - First parameter: ROS distribution (jazzy, humble)
    - Second parameter (optional): Number of parallel compilation jobs
    Default: Auto-detect (uses all available CPU cores)
    Recommended for local development: 2 or 1
    CI/Production: Omit for maximum performance

## Output

Build packages will be available in:
- `/tmp/humble_cslam_deb_packages/` for ROS Humble
- `/tmp/jazzy_cslam_deb_packages/` for ROS Jazzy
