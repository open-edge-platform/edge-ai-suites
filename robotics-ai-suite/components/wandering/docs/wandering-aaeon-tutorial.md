<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Wandering Application on AAEON robot with Intel® RealSense™ Camera and RTAB-Map SLAM

---

This tutorial details the steps to install Wandering Application with
Intel® RealSense™ camera input and create a map using RTAB-Map
Application.

## Getting Started

## Prerequisites

- [Prepare the target system](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html)
- [Setup the Robotics AI Dev Kit APT Repositories](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html#set-up-the-autonomous-mobile-robot-apt-repositories)
- [Install OpenVINO™ Packages](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html#install-openvino-packages)
- [Install Robotics AI Dev Kit Deb packages](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html#install-autonomous-mobile-robot-deb-packages)
- [Install the Intel® NPU Driver on Intel® Core™ Ultra Processors (if applicable)](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html#install-the-intel-npu-driver-on-intel-core-ultra-processors)

## Install Deb package

Install the `ros-<distro>-wandering-aaeon-tutorial` Deb package from the
Intel® Robotics AI Dev Kit APT repository, where `<distro>` is your ROS
distribution (humble or jazzy).

For ROS 2 Humble:

> ```bash
> sudo apt update
> sudo apt install ros-humble-wandering-aaeon-tutorial
> ```

For ROS 2 Jazzy:

> ```bash
> sudo apt update
> sudo apt install ros-jazzy-wandering-aaeon-tutorial
> ```

## Run Demo

Run the following commands to create a map using RTAB-Map and Wandering
Application tutorial on the Aaeon robot.

For ROS 2 Humble:

> ```bash
> source /opt/ros/humble/setup.bash
> ros2 launch wandering_aaeon_tutorial wandering_aaeon.launch.py
> ```

For ROS 2 Jazzy:

> ```bash
> source /opt/ros/jazzy/setup.bash
> ros2 launch wandering_aaeon_tutorial wandering_aaeon.launch.py
> ```

The launch file automatically detects your ROS distribution and loads the
appropriate configuration files, behavior trees, and navigation parameters
optimized for that version.

Once the command is executed, the robot starts moving and creates a map
with RTAB-Map Application.

![image](images/Wandering_aaeon_tutorial.png)

## ROS Distribution Compatibility

This package supports both ROS 2 Humble and ROS 2 Jazzy distributions. The
launch system automatically detects the active ROS distribution and selects
the appropriate configuration files:

- **Behavior Trees**: Distribution-specific behavior tree XML files are used
  to account for API differences between Nav2 versions
- **Navigation Parameters**: Optimized parameters for each ROS distribution's
  Nav2 stack
- **Launch Files**: Automatically configured based on the `ROS_DISTRO`
  environment variable

## Troubleshooting

- You can stop the demo anytime by pressing `ctrl-C`.
