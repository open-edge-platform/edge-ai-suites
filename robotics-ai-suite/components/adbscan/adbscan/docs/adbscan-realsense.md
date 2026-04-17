<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# ADBSCAN Algorithm with Intel® RealSense™ Camera Input Demo

---

This tutorial describes how to run the ADBSCAN algorithm from Intel®
RealSense™ camera input.

It outputs to the `obstacle_array` topic of type
`nav2_dynamic_msgs/ObstacleArray`.

## Prerequisites

- [Prepare the target system](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html)
- [Setup the Robotics AI Dev Kit APT Repositories](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html#set-up-the-autonomous-mobile-robot-apt-repositories)
- [Install OpenVINO™ Packages](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html#install-openvino-packages)
- [Install Robotics AI Dev Kit Deb packages](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html#install-autonomous-mobile-robot-deb-packages)
- [Install the Intel® NPU Driver on Intel® Core™ Ultra Processors (if applicable)](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html#install-the-intel-npu-driver-on-intel-core-ultra-processors)

## Install

Install `ros-humble-adbscan-ros2` Deb package from Intel® Robotics AI
Dev Kit APT repository

> ```sh
> sudo apt update
> sudo apt install ros-humble-adbscan-ros2
> ```

Install the following package with ROS 2 bag files in order to publish
point cloud data from 2D LIDAR or Intel® RealSense™ camera

> ```sh
> sudo apt install ros-humble-bagfile-laser-pointcloud
> ```

## Run the demo with Intel® RealSense™

> ```sh
> ros2 launch adbscan_ros2 play_demo_realsense_launch.py
> ```
>
> Expected result: ROS 2 rviz2 starts, and you will see how ADBSCAN
> interprets Intel® RealSense™ data coming from the ROS 2 bag:
>
> > ::: video
> > ../../../../videos/adbscan_demo_RS.mp4
> > :::
