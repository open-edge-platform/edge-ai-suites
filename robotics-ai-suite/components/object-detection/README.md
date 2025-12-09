<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# OpenVINO Vision Applications

## Overview

This repository contains multiple vision applications that leverage OpenVINO for computer vision tasks in robotics, including object detection, semantic segmentation, and YOLOv8-based detection. These applications provide ROS 2 integration for real-time perception capabilities using Intel RealSense cameras and OpenVINO inference engine.

## Get Started

### System Requirements

Prepare the target system following the [official documentation](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/prepare-system.html).

### Build

To build debian packages, export `ROS_DISTRO` env variable to desired platform and run `make package` command. After build process successfully finishes, built packages will be available in the root directory. The following command is an example for `Jazzy` distribution.

```bash
ROS_DISTRO=jazzy make package
```

You can list all built packages:

```bash
$ ls | grep -i .deb
ros-jazzy-object-detection-tutorial_2.3-1_amd64.deb
ros-jazzy-segmentation-realsense-tutorial_2.3-1_amd64.deb
ros-jazzy-yolo-msgs_2.3-1_amd64.deb
ros-jazzy-yolo_2.3-1_amd64.deb
```

To clean all build artifacts:

```bash
make clean
```

### Install

If Ubuntu 22.04 with Humble is used, then run

```bash
source /opt/ros/humble/setup.bash
```

If Ubuntu 24.04 with Jazzy is used, then run

```bash
source /opt/ros/jazzy/setup.bash
```

Finally, install the Debian packages that were built via `make package`:

```bash
sudo apt update
sudo apt install ./ros-$(ROS_DISTRO)-object-detection-tutorial_*_amd64.deb
sudo apt install ./ros-$(ROS_DISTRO)-segmentation-realsense-tutorial_*_amd64.deb
sudo apt install ./ros-$(ROS_DISTRO)-yolo-msgs_*_amd64.deb
sudo apt install ./ros-$(ROS_DISTRO)-yolo_*_amd64.deb
```

### Test

To run unit tests (implemented with `colcon`) execute the below command with target `ROS_DISTRO` (example for Jazzy):

```bash
ROS_DISTRO=jazzy make test
```

### Development

There is a set of prepared Makefile targets to speed up the development.

In particular, use the following Makefile target to run code linters.

```bash
make lint
```

To run license compliance validation:

```bash
make license-check
```

To see a full list of available Makefile targets:

```bash
$ make
Target               Description
------               -----------
clean                Clean up all build artifacts
license-check        Perform a REUSE license check using docker container https://hub.docker.com/r/fsfe/reuse
lint                 Run all sub-linters using super-linter (using linters defined for this repo only)
lint-all             Run super-linter over entire repository (auto-detects code to lint)
package              Build Debian packages
source-package       Create source package tarball
test                 Test code using colcon
```

## Usage

This repository contains three main applications:

### Object Detection Application

The Object Detection application provides real-time object detection capabilities using OpenVINO and Intel RealSense cameras. It supports various pre-trained models and can be customized for specific detection tasks.

For detailed usage instructions, see the [Object Detection Tutorial documentation](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/perception/openvino/object_detection_tutorial.html).

### Segmentation Realsense Tutorial

The Segmentation application demonstrates semantic segmentation using OpenVINO with Intel RealSense depth cameras. It provides pixel-level classification for scene understanding.

For detailed usage instructions, see the [Segmentation Realsense Tutorial documentation](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/perception/openvino/segmentation_realsense_tutorial.html).

### YOLOv8

The YOLOv8 application provides state-of-the-art object detection using the YOLOv8 model optimized with OpenVINO. It offers high-performance real-time detection for robotics applications.

For detailed usage instructions, see the [YOLOv8 OpenVINO Tutorial documentation](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/perception/openvino/yolov8_openvino_tutorial.html).

## License

OpenVINO Vision Applications is licensed under [Apache 2.0 License](./LICENSES/Apache-2.0.txt).
