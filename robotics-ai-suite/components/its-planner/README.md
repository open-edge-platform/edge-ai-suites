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

Currently, the ITS plugin does not support continuous replanning. To use this plugin, a simple behavior tree with compute path to pose and follow path should be used.


## Get Started

### System Requirements

Prepare the target system following the [official documentation](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/prepare-system.html).

### Build

To build the ITS Planner packages, export `ROS_DISTRO` env variable to desired platform and run `make build` command:

```bash
ROS_DISTRO=humble make build
```

This will build the following packages:
- `ros-humble-its-planner`
- `ros-humble-its-relocalization`
- `ros-humble-its-send-localization`
- `ros-humble-nav2-bringup-collab`

The built packages will be available in the root directory.

To clean all build artifacts:

```bash
make clean
```

### Install

If Ubuntu 22.04 with Humble is used, then run:

```bash
source /opt/ros/humble/setup.bash
```

Install the ``ros-humble-its-planner`` Debian package from the Intel Robotics AI Suite APT repo:

```bash
sudo apt install ros-humble-its-planner
```

Or install the locally built Debian package:

```bash
sudo apt update
sudo apt install ./ros-humble-its-planner_*_amd64.deb
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

To use this plugin, the following parameters need to be added to the `nav2_params.yaml`:

```yaml
planner_server:
  ros__parameters:
    expected_planner_frequency: 0.01
    use_sim_time: True
    planner_plugins: ["GridBased"]
    GridBased:
      plugin: "its_planner/ITSPlanner"
      interpolation_resolution: 0.05
      catmull_spline: False
      smoothing_window: 15
      buffer_size: 10
      build_road_map_once: True
      min_samples: 250
      roadmap: "PROBABLISTIC"
      w: 32
      h: 32
      n: 2
```

**Parameter Descriptions:**

- `catmull_spline`: if true, the generated path from the ITS will be interpolated with catmull spline method; otherwise smoothing filter will be used to smooth the path
- `smoothing_window`: window size for the smoothing filter; unit is grid size
- `buffer_size`: during the roadmap generation, the samples are generated away from obstacles. The buffer size dictates how far the roadmap samples should be away from obstacles
- `build_road_map_once`: If true, the roadmap will be loaded from the saved file, otherwise a new roadmap will be generated
- `min_samples`: minimum number of samples required to generate the roadmap
- `roadmap`: can be either `PROBABLISTIC` or `DETERMINISTIC`
- `w`: the width of the window for intelligent sampling
- `h`: the height of the window for intelligent sampling
- `n`: the minimum number of samples that is required in an area defined by `w` and `h`

### Running ITS Planner

Run the following script to set environment variables:

```bash
source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=waffle_pi
export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:/opt/ros/humble/share/turtlebot3_gazebo/models
```

To launch the default ITS planner which is based on differential drive robot, run:

```bash
ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False params_file:=/opt/ros/humble/share/its_planner/nav2_params.yaml default_bt_xml_filename:=/opt/ros/humble/share/its_planner/navigate_w_recovery.xml
```

ITS Planner also supports Ackermann steering; to launch the Ackermann ITS planner run:

```bash
ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False params_file:=/opt/ros/humble/share/its_planner/nav2_params_dubins.yaml default_bt_xml_filename:=/opt/ros/humble/share/its_planner/navigate_w_recovery.xml
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

The Ackermann steering version of this plugin utilizes some additional parameters which can be found in `nav2_params_dubins.yaml`:

<!-- markdownlint-disable MD033 -->
<pre><code>planner_server:
  ros__parameters:
    expected_planner_frequency: 0.01
    use_sim_time: True
    planner_plugins: ["GridBased"]
    GridBased:
      plugin: "its_planner/ITSPlanner"
      interpolation_resolution: 0.05
      catmull_spline: False
      smoothing_window: 15
      buffer_size: 10
      build_road_map_once: True
      min_samples: 250
      roadmap: "PROBABLISTIC"
      w: 32
      h: 32
      n: 2
    <b>-- Dubins Specific --
      dubins_path: True
      turn_radius: .22
      robot_radius: .25
      yaw_tolerance: .125
      use_final_heading: True</b>
</code></pre>

**Dubins-Specific Parameters:**

- `dubins_path`: If true, the ITS algorithm will utilize Dubins Paths to form a global path that can be followed by an Ackermann steering vehicle.
- `turn_radius`: The minimum turning radius of the robot, in world scale.
- `robot_radius`: The radius of the robot, in world scale.
- `yaw_tolerance`: The amount (+/-) by which the heading angles of the end positions of the intermediate Dubins curves may vary, in radians. Does not apply to the final Goal heading.
- `use_final_heading`: Whether to use the goal heading specified by the `geometry_msgs::msg::PoseStamped` message or not.

## Documentation

Comprehensive documentation on this component is available here: [dev guide](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/navigation/its-path-planner-plugin.html).

## License

``its-planner`` is licensed under [Apache 2.0 License](./LICENSES/Apache-2.0.txt).
