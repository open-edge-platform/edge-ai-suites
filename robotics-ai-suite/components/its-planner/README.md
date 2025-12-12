<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# ITS Planner (Intelligent Sampling and Two-Way Search Path Planner)

## Overview

The ITS Planner is a global path planner module for ROS2 Navigation based on Intelligent Sampling and Two-Way
Search (ITS). This plugin is designed for efficient path planning using either Probabilistic Road Map (PRM) or
Deterministic Road Map (DRM) approaches.

The inputs for the ITS planner are global 2d_costmap (`nav2_costmap_2d::Costmap2D`), start and goal pose
(`geometry_msgs::msg::PoseStamped`). The outputs are 2D waypoints of the path. The ITS planner converts the
2d_costmap to a roadmap which can be saved in a txt file and reused for multiple inquiries. Once a roadmap is
generated, the ITS conducts a two-way search to find a path from the source to destination. Either the smoothing
filter or catmull spline interpolation can be used to create a smooth and continuous path. The generated smooth
path is in the form of ROS navigation message type (`nav_msgs::msg`).

Currently, the ITS plugin does not support continuous replanning. To use this plugin, a simple behavior tree
with compute path to pose and follow path should be used.


## Get Started

### System Requirements

Prepare the target system following the [official documentation](https://docs.openedgeplatform.intel.com/2025.2/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/prepare-system.html).

### Build

To build the ITS Planner packages, export `ROS_DISTRO` env variable to desired platform (`jazzy` or `humble`) and run `make build` command:

```bash
ROS_DISTRO=jazzy make build
```

This will build the following packages:
- `ros-${ROS_DISTRO}-its-planner`
- `ros-${ROS_DISTRO}-its-relocalization`
- `ros-${ROS_DISTRO}-its-send-localization`
- `ros-${ROS_DISTRO}-nav2-bringup-collab`

The built packages will be available in the root directory.

To clean all build artifacts:

```bash
make clean
```

### Install

Depending on selected `ROS_DISTRO` run:

```bash
source /opt/ros/${ROS_DISTRO}/setup.bash
```

Install the ``ros-${ROS_DISTRO}-its-planner`` Debian package from the Intel Robotics AI Suite APT repo:

```bash
sudo apt install ros-${ROS_DISTRO}-its-planner
```

Or install the locally built Debian package:

```bash
sudo apt update
sudo apt install ./ros-${ROS_DISTRO}-its-planner_*_amd64.deb
```

### Development

There is a set of prepared Makefile targets to speed up the development.

In particular, use the following Makefile target to run code linters:

```bash
make lint
```

To run license compliance validation:

```bash
make license-check
```

To see a full list of available Makefile targets:

```bash
$ make help
Target               Description
------               -----------
build                Build ITS Planner and related packages
build-nav2-amcl      Build patched nav2-amcl package
build-nav2-msgs      Build patched nav2-msgs package
help                 Display this help message
license-check        Perform a REUSE license check using docker container https://hub.docker.com/r/fsfe/reuse
lint                 Run all sub-linters using super-linter (using linters defined for this repo only)
lint-all             Run super-linter over entire repository (auto-detects code to lint)
source-package       Create source package tarball
```

## Usage

### Configuration Parameters

The ROS 2 navigation bring-up application is started using the TurtleBot 3 Gazebo simulation which
gets parameters from either `nav2_params_jazzy.yaml` or `nav2_params_humble.yaml` configuration file.

More information about parameter configuration can be found in
[its-customization](https://docs.openedgeplatform.intel.com/2025.2/edge-ai-suites/robotics-ai-suite/robotics/dev_guide/tutorials_amr/navigation/its-customization.html).

### Set environment variables


Run the following script to set environment variables, based on `ROS_DISTRO` used:

```bash
source /opt/ros/${ROS_DISTRO}/setup.bash
export TURTLEBOT3_MODEL=waffle_pi
export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:/opt/ros/${ROS_DISTRO}/share/turtlebot3_gazebo/models
```

### Running ITS Planner


To launch the `default ITS planner` which is based on differential drive robot, run:

```bash
ros2 launch its_planner its_differential_launch.py use_sim_time:=true
```

ITS Planner also supports Ackermann steering; to launch the `Ackermann ITS planner` run:

```bash
ros2 launch its_planner its_ackermann_launch.py use_sim_time:=true
```

### Navigation Usage

After launching the ROS2 navigation and the ITS planner plugin, look at where the robot is in the Gazebo world, and find that spot on the Rviz display.

1. From Rviz set the initial pose by clicking the "2D Pose Estimate" button
2. Click on the map where the robot is
3. Click the "Navigation2 Goal" button and choose goal position

Now a path will be generated and the robot will start following the path to navigate toward the goal position.

For detailed instructions, follow the ROS2 Navigation usage guide: [Navigation usage](https://navigation.ros.org/getting_started/index.html#navigating)

### Ackermann Steering Support

This plugin also supports a global path planner based on ITS for Ackermann steering vehicles, which maneuver with car-like controls and a limited turning radius. This version of the planner is based on the concept of [Dubins Paths](https://en.wikipedia.org/wiki/Dubins_path), and uses an adapted version of [AndrewWalker's Dubins Curves implementation](https://github.com/AndrewWalker/Dubins-Curves).

The Ackermann steering version of this plugin utilizes some additional parameters. More information about them can be found in
[its-customization](https://docs.openedgeplatform.intel.com/2025.2/edge-ai-suites/robotics-ai-suite/robotics/dev_guide/tutorials_amr/navigation/its-customization.html).


## Documentation

Comprehensive documentation on this component is available here: [dev guide](https://docs.openedgeplatform.intel.com/2025.2/edge-ai-suites/robotics-ai-suite/robotics/dev_guide/tutorials_amr/navigation/its-path-planner-plugin.html).

## License

``its-planner`` is licensed under [Apache 2.0 License](./LICENSES/Apache-2.0.txt).
