# Getting Started Guide - Drone Mission Compute SDK

## Overview

The Drone Mission Compute SDK provides a comprehensive development environment for drone and robotics applications using Intel's optimized compute tools and frameworks.
This guide demonstrates the installation process and provides a practical example of deploying robotics vision and control pipelines on Intel edge hardware.

## Learning Objectives

Upon completion of this guide, you will be able to:

- Install and configure the Drone Mission Compute SDK
- Deploy robotics inference pipelines using OpenVINO and DLStreamer
- Understand the architecture of vision-guided robotics applications on Intel platforms

## System Requirements

Verify that your development environment meets the following specifications:

- Operating System: Ubuntu 24.04 LTS or Ubuntu 22.04 LTS
- Memory: Minimum 16GB RAM (32GB recommended)
- Storage: 50GB available disk space
- Network: Active internet connection for package downloads
- Hardware: Intel processor with integrated or discrete GPU recommended

## Installation Process

Execute the automated installation script to configure the complete development environment:

```bash
curl -fsS https://raw.githubusercontent.com/open-edge-platform/edge-ai-suites/refs/heads/main/metro-ai-suite/metro-sdk-manager/scripts/drone-mission-compute-sdk.sh | bash
```

## Next Steps

After installation completes:

1. Navigate to `$HOME/oep/` to explore the cloned repositories
2. Review the robotics AI suite examples in `edge-ai-suites/robotics-ai-suite/`
3. Explore the robot vision control pipelines in `edge-ai-suites/robotics-ai-suite/robot-vision-control/`
