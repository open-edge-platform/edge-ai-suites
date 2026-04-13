<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Groundfloor Segmentation (Efficient Groundfloor Segmentation for 3D Pointclouds)

## Overview

This repository contains a realization of an efficient groundfloor segmentation approach for 3D pointclouds. The application comes with three default use cases: standalone use with RealSense camera (or other depth cameras), integration with the Wandering demo on Aaeon robot, and direct use with 3D pointcloud input.

The application is designed as a ROS2 node and provides two output topics:

- `/segmentation/labeled_points`: A labeled pointcloud, where every point is assigned a classification label, e.g. groundfloor, obstacle, etc.
- `/segmentation/obstacle_points`: A filtered pointcloud that contains only obstacle points.

## Get Started

### Supported Platforms

This application supports the following ROS2 distributions:

| ROS2 Distribution | Ubuntu Version | Status |
|-------------------|----------------|--------|
| Humble | 22.04 LTS | ✅ Fully Supported |
| Jazzy | 24.04 LTS | ✅ Fully Supported |

> [!NOTE]
> The application has been tested and validated on both distributions. A unified launch system (`twist_bridge`) automatically handles distribution-specific differences to ensure consistent behavior.

### System Requirements

Prepare the target system following the [official documentation](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html).

### Build

To build a Debian package, set the `ROS_DISTRO` environment variable to your target ROS2 distribution and run the build command:

```bash
export ROS_DISTRO=humble  # or jazzy
make build
```

After the build completes successfully, the Debian package will be available in the root directory.

To clean all build artifacts:

```bash
make clean
```

### Install

Source your ROS2 environment and install the Debian package:

```bash
export ROS_DISTRO=humble  # or jazzy
source /opt/ros/${ROS_DISTRO}/setup.bash
sudo apt update
sudo apt install ./ros-${ROS_DISTRO}-pointcloud-groundfloor-segmentation*.deb
```

To load the application's environment for execution:

```bash
source install/setup.bash
```

### Test

To run unit tests with your target ROS distribution:

```bash
export ROS_DISTRO=humble  # or jazzy
make test
```

### Development

There is a set of prepared Makefile targets to speed up the development.

In particular, use the following Makefile target to run code linters.

```bash
make lint
```

Alternatively, you can run linters individually.

```bash
make lint-bash
make lint-clang
make lint-githubactions
make lint-json
make lint-markdown
make lint-python
make lint-yaml
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
build                Build debian package
clean                Clean build artifacts
help                 
license-check        Perform a REUSE license check using docker container https://hub.docker.com/r/fsfe/reuse
lint                 Run all sub-linters using super-linter (using linters defined for this repo only)
lint-all             Run super-linter over entire repository (auto-detects code to lint)
lint-bash            Run Bash linter using super-linter
lint-clang           Run clang linter using super-linter
lint-githubactions   Run Github Actions linter using super-linter
lint-json            Run JSON linter using super-linter
lint-markdown        Run Markdown linter using super-linter
lint-python          Run Python linter using super-linter
lint-yaml            Run YAML linter using super-linter
source-package       Create source package tarball
test                 Run tests
```

## Usage

The node operates on a parameter file, that can be provided as launch argument (`node_params_file`).

The algorithm addresses situations like non-flat floors, ramps, inclines, declines, overhanging loads and other challenging conditions. Its capabilities extend beyond standard segmentation approaches, making it suited for diverse scenarios.

The application generates two output topics:
- `segmentation/labeled_points` - assigns labels (ground, elevated, obstacle or above the roof) to points within the sensor's 3D pointcloud
- `segmentation/obstacle_points` - provides a reduced pointcloud containing only points labeled as obstacles

### Standalone use with RealSense camera (or other depth cameras)

This use case is intended if the depth output of a RealSense camera should be segmented and converted into a 3D point cloud.

The ROS2 node expects input from a RealSense camera via two topics:

- `/<camera_name>/depth/image_rect_raw`
- `/<camera_name>/depth/camera_info`

where `<camera_name>` is a command-line parameter for the launch command (default: `camera`).

**Launch the segmentation node:**

```bash
export ROS_DISTRO=humble  # or jazzy
source /opt/ros/${ROS_DISTRO}/setup.bash
source install/setup.bash
ros2 launch pointcloud_groundfloor_segmentation realsense_groundfloor_segmentation_launch.py
```

**Launch with additional options:**

The ROS 2 launch file supports additional arguments for RViz visualization and standalone operation.

Terminal 1 - Start the RealSense camera:

```bash
ros2 launch realsense2_camera rs_launch.py enable_infra1:=true align_depth.enable:=true enable_sync:=true init_reset:=true pointcloud.enable:=true camera_namespace:=/
```

Terminal 2 - Start the segmentation node with visualization:

```bash
ros2 launch pointcloud_groundfloor_segmentation realsense_groundfloor_segmentation_launch.py with_rviz:=True standalone:=True
```

Use the `-s` flag to see all available launch arguments:

```bash
ros2 launch pointcloud_groundfloor_segmentation realsense_groundfloor_segmentation_launch.py -s
```

**Output Topics:**

Monitor the active topics:

```bash
ros2 topic list
```

Expected output includes:

```console
/camera/depth/camera_info
/camera/depth/image_rect_raw
/parameter_events
/rosout
/segmentation/labeled_points
/segmentation/obstacle_points
/tf
/tf_static
```

> [!NOTE]
> Your topic list may differ if you use additional ROS 2 nodes or different camera settings.

**Visualization Examples:**

Labeled pointcloud with classification:

![Labeled Pointcloud](docs/images/pointcloud_groundfloor_segmentation_demo_camera_labeled_points.png)
*Labeled pointcloud with classification labels*

Filtered obstacle points:

![Obstacle Pointcloud](docs/images/pointcloud_groundfloor_segmentation_demo_camera_obstacle_points.png)
*Filtered obstacle points*

### Aaeon Robot Integration with Teleop/Wandering

This use case integrates the groundfloor segmentation with the Aaeon robot's navigation system, using RealSense depth data instead of a 2D laser scan for costmap generation.

**Background - Distribution Differences:**

Different ROS2 distributions handle teleop keyboard differently:
- **Humble** uses `Twist` messages
- **Jazzy** uses `TwistStamped` messages

This necessitated maintaining separate procedures. A unified solution with a `twist_bridge` node now handles these differences automatically.

**Unified Quick Start (Works on All Distributions):**

```bash
export ROS_DISTRO=humble  # or jazzy
source /opt/ros/${ROS_DISTRO}/setup.bash
ros2 launch pointcloud_groundfloor_segmentation aaeon_complete_system_launch.py
TURTLEBOT3_MODEL=aaeon ros2 run turtlebot3_teleop teleop_keyboard
```

**What the Launch File Provides:**

| Component | Purpose |
|-----------|---------|
| **AMR Interface** | Initializes the Aaeon robot interface |
| **Twist Bridge** | Converts between Twist/TwistStamped for keyboard teleoperation |
| **Teleop Keyboard** | Enables manual robot control via keyboard |
| **TF Transforms** | Establishes required frames: `base_link` ↔ `camera_link`, `map` ↔ `odom` |
| **Segmentation Node** | Runs groundfloor segmentation with RealSense input |

**Launch Arguments:**

```bash
ros2 launch pointcloud_groundfloor_segmentation aaeon_complete_system_launch.py \
  with_aaeon:=true \
  with_twist_bridge:=true
```

- `with_aaeon` (default: `true`) - Enable Aaeon robot interface
- `with_twist_bridge` (default: `true`) - Enable message type conversion

**Manual Setup (Alternative):**

If you prefer to configure the system manually, open three terminal sessions:

Terminal 1 - Establish camera transform:

```bash
export ROS_DISTRO=humble  # or jazzy
source /opt/ros/${ROS_DISTRO}/setup.bash
ros2 run tf2_ros static_transform_publisher 0 0 0.1 0 0 0 1 /base_link /camera_link
```

Terminal 2 - Establish map-to-odometry transform:

```bash
ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 1 /map /odom
```

Terminal 3 - Launch segmentation with visualization:

```bash
ros2 launch pointcloud_groundfloor_segmentation realsense_groundfloor_segmentation_launch.py with_rviz:=True
```

### Use with 3D Pointcloud (e.g., from 3D LiDAR sensor)

This application can also process 3D pointcloud data directly from sensors such as 3D LiDAR.

**Launch the segmentation node:**

```bash
export ROS_DISTRO=humble  # or jazzy
source /opt/ros/${ROS_DISTRO}/setup.bash
source install/setup.bash
ros2 launch pointcloud_groundfloor_segmentation pointcloud_groundfloor_segmentation_launch.py
```

**Configure Input Topic:**

The input pointcloud topic is configurable via the `pointcloud_topic` launch argument:

```bash
ros2 launch pointcloud_groundfloor_segmentation pointcloud_groundfloor_segmentation_launch.py pointcloud_topic:=/my_lidar/points
```

**Monitor Active Topics:**

```bash
ros2 topic list
```

Expected topics include:

```console
/input/points
/parameter_events
/pseudo_camera/depth/camera_info
/pseudo_camera/depth/image_rect_raw
/rosout
/segmentation/labeled_points
/segmentation/obstacle_points
/tf
/tf_static
```

> [!NOTE]
> Your topic list may differ if you use additional ROS 2 nodes or different sensor configuration.

**Requirements:**

- The LiDAR node must publish to `/input/points`, or you must remap the topic appropriately
- Complete TF transform chain from `base_link` to the sensor frame

### Adjusting Application Parameters

The ROS2 node is configured via parameter files. Parameter files are located in the package's params directory.

**Find the parameter files:**

```bash
find /opt/ros -name pointcloud_groundfloor_segmentation -type d
# Look for: /opt/ros/${ROS_DISTRO}/share/pointcloud_groundfloor_segmentation/params/
```

**Available Parameters:**

- **`base_frame`** (default: `base_link`): The ROS2 TF frame for algorithm operation. A complete transform between the sensor frame and this frame is required.

- **`use_best_effort_qos`** (default: `false`): Whether to use `best_effort` QoS. By default, `reliable` QoS is used.

- **`sensor.name`** (default: `camera`): Sensor name (e.g., `camera`, `realsense_camera`). This is the prefix for input topics (e.g., `/camera/depth/image_rect_raw`).

- **`sensor.max_surface_height`** (default: `0.05 m`): Maximum height of a flat groundfloor. Points higher than this are flagged as `obstacle`.

- **`sensor.min_distance_to_ego`** (default: `0.4 m`): Sensor measurements closer than this value are ignored.

- **`sensor.max_incline`** (default: `15°`): Maximum allowed incline/decline angle. Points exceeding this are not labeled as `groundfloor`.

- **`sensor.robot_height`** (default: `2.0 m`): Measurements above this height are flagged as `above` (no collision risk).

**Parameter Visualization:**

![Parameters Illustration](docs/images/pointcloud_groundfloor_segmentation_demo_parameters.png)
*Visual representation of segmentation parameters*

### Requirements

To achieve optimal output quality, it is essential to fulfill following requirements:

- The input sensor should be forward facing, ideally in parallel to the groundfloor.
- The ROS 2 TF tree between `base_frame` and the sensor frame must be complete.
- Satisfactory input data quality is crucial. Incomplete depth images or pointclouds may result in incorrect labels.

### Troubleshooting

- **Failed to install Deb package**: Please make sure to run `sudo apt update` before installing the necessary Deb packages.
- **Stopping the demo**: You can stop the demo anytime by pressing `ctrl-C`.
- **Segmentation quality issues**: The quality of the segmentation and labeling depends on the quality of the input data. Noisy data, especially major outliers could result in wrong labels. If this is the case, the input data should be pre-processed to reduce noise.

## Documentation

Comprehensive documentation on this component is available here: [dev guide](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/dev_guide/tutorials_amr/perception/pointcloud-groundfloor-segmentation.html).

## License

`groundfloor` is licensed under [Apache 2.0 License](./LICENSES/Apache-2.0.txt).
