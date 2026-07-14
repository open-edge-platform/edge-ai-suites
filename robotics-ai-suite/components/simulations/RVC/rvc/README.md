<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# RVC &mdash; Single-Arm Two-Conveyor Pick-and-Place Demo

A ROS 2 + Gazebo simulation in which a UR5 robotic arm continuously
picks cubes off one conveyor belt and places them onto a second belt.
The demo is built on top of the shared `robot_config` and
`robot_config_plugins` packages that also power the `picknplace` demo.

## Supported Platforms

| ROS 2 | Ubuntu | Gazebo |
| --- | --- | --- |
| Humble | 22.04 (Jammy) | Fortress (7.x) |
| Jazzy | 24.04 (Noble) | Harmonic (8.x) |

## Installation

Install the Debian package from the Intel(R) Robotics AI Dev Kit APT repository:

```bash
# Humble
sudo apt update && sudo apt install ros-humble-rvc-simulation

# Jazzy
sudo apt update && sudo apt install ros-jazzy-rvc-simulation
```

## Launch

```bash
RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ros2 launch rvc rvc.launch.py
```

See [../../docs/rvc.md](../../docs/rvc.md) for details.
