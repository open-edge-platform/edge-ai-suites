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

### System Requirements

Prepare the target system following the [official documentation](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/prepare-system.html).

### Build

To build debian package, export `ROS_DISTRO` env variable to desired platform and run `make build` command. After build process successfully finishes, built package will be available in the root directory. The following command is an example for `Humble` distribution.

```bash
ROS_DISTRO=humble make build
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

Finally, install the Debian package that was built via `make build`:

```bash
sudo apt update
sudo apt install ./ros-$(ROS_DISTRO)-pointcloud-groundfloor-segmentation*.deb
```

To run the application afterwards, you need to load the application's environment:

```bash
source install/setup.bash
```

### Test

To run unit tests execute the below command with target `ROS_DISTRO` (example for Humble):

```bash
ROS_DISTRO=humble make test
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

where `<camera_name>` is a commandline parameter for the launch command. By default `<camera_name>` is 'camera'.

If Ubuntu 22.04 with Humble is used, then run

```bash
source /opt/ros/humble/setup.bash
ros2 launch pointcloud_groundfloor_segmentation realsense_groundfloor_segmentation_launch.py
```

If Ubuntu 24.04 with Jazzy is used, then run

```bash
source /opt/ros/jazzy/setup.bash
ros2 launch pointcloud_groundfloor_segmentation realsense_groundfloor_segmentation_launch.py
```

**Running with additional options:**

The ROS 2 launch file provides additional arguments, for example to run the ROS 2 node only together with a camera, or with rviz. These can be activated as follows:

Terminal 1:

```bash
source /opt/ros/humble/setup.bash
ros2 launch realsense2_camera rs_launch.py enable_infra1:=true align_depth.enable:=true enable_sync:=true init_reset:=true pointcloud.enable:=true camera_namespace:=/
```

Terminal 2:

```bash
source /opt/ros/humble/setup.bash
ros2 launch pointcloud_groundfloor_segmentation realsense_groundfloor_segmentation_launch.py with_rviz:=True standalone:=True
```

The commandline option `-s` will show all available flags.

**Output visualization:**

One can view the list of running ROS 2 topics by typing `ros2 topic list` in a terminal.

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
> Your topic list may differ, if you use additional ROS 2 nodes or other camera settings.

In case of the standalone execution, the rviz view for the labeled pointcloud should look as follows:

![Labeled Pointcloud](docs/images/pointcloud_groundfloor_segmentation_demo_camera_labeled_points.png)
*Labeled pointcloud with classification labels*

In case of the standalone execution, the rviz view for the filtered pointcloud should look as follows:

![Obstacle Pointcloud](docs/images/pointcloud_groundfloor_segmentation_demo_camera_obstacle_points.png)
*Filtered obstacle points*

### Use together with Teleop/Wandering demo on Aaeon robot

This use case is intended for the teleop/wandering application running on the Aaeon robot. It basically uses the same functionality as the default wandering application, but uses the RealSense depth stream instead of a 2D laser scan to create the global and local costmap for navigation.

**Quick start (using pre-configured script):**

If Ubuntu 22.04 with Humble is used, then run

```bash
/opt/ros/humble/share/pointcloud_groundfloor_segmentation/scripts/wandering_aaeon.sh
```

If Ubuntu 24.04 with Jazzy is used, then run

```bash
/opt/ros/jazzy/share/pointcloud_groundfloor_segmentation/scripts/wandering_aaeon.sh
```

**Manual setup:**

Alternatively, you can manually set up the required TF links and launch the segmentation. Open three terminal sessions:

Terminal 1: Establish a TF link between robot and camera:

```bash
source /opt/ros/humble/setup.bash
ros2 run tf2_ros static_transform_publisher 0 0 0.1 0 0 0 1 /base_link /camera_link
```

Terminal 2: Establish a TF link between robot and map:

```bash
source /opt/ros/humble/setup.bash
ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 1 /map /odom
```

Terminal 3: Run the segmentation application with Intel® RealSense™ camera input:

```bash
source /opt/ros/humble/setup.bash
ros2 launch pointcloud_groundfloor_segmentation realsense_groundfloor_segmentation_launch.py with_rviz:=True
```

An example of a local costmap based on the RealSense depth input is provided in the image above.

### Use with 3D pointcloud (e.g., from 3D LiDAR sensor)

This application can also be used directly with a 3D pointcloud as input, for example from a 3D LiDAR sensor.

If Ubuntu 22.04 with Humble is used, then run

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch pointcloud_groundfloor_segmentation pointcloud_groundfloor_segmentation_launch.py
```

If Ubuntu 24.04 with Jazzy is used, then run

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch pointcloud_groundfloor_segmentation pointcloud_groundfloor_segmentation_launch.py
```

The input topic name can be provided using the commandline parameter `pointcloud_topic`.

One can view the list of running ROS 2 topics by typing `ros2 topic list` in a terminal.

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
> Your topic list may differ, if you use additional ROS 2 nodes or other camera settings.

The LiDAR node, that needs to be started in parallel, has to provide the topic `/input/points` otherwise the topic has to be remapped.

### Adjusting Application Parameters

The ROS 2 node supports a set of parameters, that can be found under:

```bash
/opt/ros/humble/share/pointcloud_groundfloor_segmentation/params/
```

There is one example configuration how the application's output can be used for the ROS 2 nav2 application, and a second file providing parameter values for the segmentation task. These include:

- **`base_frame`**: This is the ROS 2 TF frame that the underlying algorithm operates on. The default value is `base_link`. There must be a complete transform between the sensor frame and this `base_frame`.

- **`use_best_effort_qos`**: Defines if `best_effort` QoS should be used. By default `reliable` is used.

- **`sensor.name`**: Name of the connected sensor e.g. camera or realsense_camera. The default is `camera`. This is the prefix of the input topic, e.g. /camera/depth/image_rect_raw.

- **`sensor.max_surface_height`**: The maximum height of a perfectly flat groundfloor. Default value is 0.05 meter. If no incline is detected, measurements higher than this value will be flagged as `obstacle`.

- **`sensor.min_distance_to_ego`**: Sensor measurements closer than this value are ignored during processing. Default value is 0.4 meter.

- **`sensor.max_incline`**: The maximum allowed incline (or decline) of a ramp on the groundfloor. If an incline above this value is detected, the corresponding points will no longer receive the label `groundfloor`. The default value is 15 degrees.

- **`sensor.robot_height`**: Measurements above this value do not impose a collision risk for the robot and will be flagged as `above`. The default value is 2.0 meter.

An example illustrating these parameters is provided in the image below:

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

Comprehensive documentation on this component is available here: [dev guide](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/perception/pointcloud-groundfloor-segmentation.html).

## License

`groundfloor` is licensed under [Apache 2.0 License](./LICENSES/Apache-2.0.txt).
