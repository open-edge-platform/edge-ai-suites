<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Robot Re-localization package for ROS2 Navigation

The robot re-localization package is a package which enables re-localization in ROS2 navigation.
Under sensor measurements glitches or disturbance in the environments or similarity in the scene, robot may lose its localization, hence a fast and reliable re-localization algorithm is required to re-localize the robot.
To address this problem, we innovated a compute and memory efficient re-localization algorithm for mobile robots.

## Getting Started

Robotics AI Suite provides a ROS2 Debian package for the application, supported by the following platform:

- OS: Ubuntu 22.04

- ROS version: humble

## Install Debian Package

Install the ``ros-humble-its-relocalization-bringup`` Debian package from the Intel Robotics AI Suite APT repo

```sh
sudo apt install ros-humble-its-relocalization-bringup
```

Run the following script to set environment variables and bringup ROS2 navigation, and Turtlebot3 in Gazebo:

```sh
source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=waffle_pi
export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:/opt/ros/humble/share/turtlebot3_gazebo/models
ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False
```

Once the ROS2 navigation is running in Gazebo, open a new terminal to bring up the re-localization:

```sh
source /opt/ros/humble/setup.bash
ros2 launch relocalization_bringup relocalization.launch.xml 
```

We simulate the re-localization package, we created a demo application which simulates a situation where sensor fails.
In this application, the sensor gets disabled for a few seconds while the robot is traveling toward the goal.
Once, the sensor measurements are re-enabled, the robot will automatically re-localized itself and continue the navigation toward the goal.
To run this demo application run:

```sh
ros2 launch relocalization_bringup relocalization_demo.launch.xml mode:=demo
```
