<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Simulations Scripts


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
        -v /tmp/simulations_deb_packages:/tmp/simulations_deb_packages \
        --cpus="6.0" \
        --memory="10g" \
        --memory-swap="12g" \
        -e http_proxy='http://proxy-dmz.intel.com:912' \
        -e https_proxy='http://proxy-dmz.intel.com:912' \
        -e no_proxy='localhost,127.0.0.1/8,ch.intel.com,ka.intel.com,devtools.intel.com,backend' \
        -e HTTP_PROXY='http://proxy-dmz.intel.com:912' \
        -e HTTPS_PROXY='http://proxy-dmz.intel.com:912' \
        -e NO_PROXY='localhost,127.0.0.1/8,ch.intel.com,ka.intel.com,devtools.intel.com,backend' \
        amd64/ros:humble-ros-base \
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
       -v /tmp/simulations_deb_packages:/tmp/simulations_deb_packages \
       --cpus="6.0" \
       --memory="10g" \
       --memory-swap="12g" \
       -e http_proxy='http://proxy-dmz.intel.com:912' \
       -e https_proxy='http://proxy-dmz.intel.com:912' \
       -e no_proxy='localhost,127.0.0.1/8,ch.intel.com,ka.intel.com,devtools.intel.com,backend' \
       -e HTTP_PROXY='http://proxy-dmz.intel.com:912' \
       -e HTTPS_PROXY='http://proxy-dmz.intel.com:912' \
       -e NO_PROXY='localhost,127.0.0.1/8,ch.intel.com,ka.intel.com,devtools.intel.com,backend' \
       amd64/ros:jazzy-ros-base \
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
- `/tmp/humble_simulations_deb_packages/` for ROS Humble
- `/tmp/jazzy_simulations_deb_packages/` for ROS Jazzy
