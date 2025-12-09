<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# FastMapping

## Overview

A ROS project to construct and maintain a volumetric map from a moving RGB-D camera, like [octomap_mapping](https://github.com/OctoMap/octomap_mapping), but runs much faster.

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
$ ls|grep -i .deb
ros-jazzy-fast-mapping_2.3-1_amd64.deb
ros-jazzy-fast-mapping-build-deps_2.3-1_amd64.deb
```

`*build-deps*.deb` package is generated during build process and installation of such packages could be skipped on target platform.

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

Finally, install the Debian package that was built via ``make package``:

```bash
sudo apt update
sudo apt install ./ros-$(ROS_DISTRO)-fast-mapping_*_amd64.deb
```

### Test

To run unit tests (implemented with ``colcon``) execute the below command with target ``ROS_DISTRO`` (example for Jazzy):

```bash
ROS_DISTRO=jazzy make test
```

To run E2E functional tests that validate FastMapping in a practical setup, execute:

```bash
ROS_DISTRO=jazzy make test-e2e
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
build                Build code using colcon
clean                Clean up all build artifacts
clean-colcon         Clean up Colcon build and test artifacts
clean-debian         Clean up Debian packaging artifacts
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
package              Build Debian package
source-package       Create source package tarball
test                 Test code using colcon
test-e2e             Run E2E functional tests
```

## Usage

### Run with Intel RealSense cameras

FastMapping supports mapping from single or multiple Intel RealSense cameras, given that each camera provides a camera_frame <-> map transformation
in the TF tree, e.g. camera1_color_optical_frame <-> map. FastMapping will only support cameras of the same type and will assume all the
cameras to have the same set of intrinsics.

In its default configuration, FastMapping will start mapping from a single camera. In order to run with multiple cameras the parameter 'depth_cameras' must be set
to the number of required cameras. In addition to the number of cameras, FastMapping expects each depth topic of each camera to be specified
as well as a topic providing the CameraInfo (intrinsics) as shown in the examples below.

If Ubuntu 22.04 with Humble is used, then run

```bash
source /opt/ros/humble/setup.bash
```

If Ubuntu 24.04 with Jazzy is used, then run

```bash
source /opt/ros/jazzy/setup.bash
```

Then run

```bash
sudo apt install ros-${ROS_DISTRO}-rtabmap-ros
ros2 launch fast_mapping fast_mapping_rtabmap.launch.py
```

FastMapping running with two Realsense cameras named "camera_front" and "camera_left"

```bash
ros2 run fast_mapping fast_mapping_node --ros-args -p depth_cameras:=2 -p depth_topic_1:=camera_front/aligned_depth_to_color/image_raw -p depth_topic_2:=camera_left/aligned_depth_to_color/image_raw -p depth_info_topic:=camera_front/aligned_depth_to_color/camera_info
```

### Run with ROS2 bag file

> Make sure to have a ros2 bag file for this test

If Ubuntu 22.04 with Humble is used, then run

```bash
source /opt/ros/humble/setup.bash
```

If Ubuntu 24.04 with Jazzy is used, then run

```bash
source /opt/ros/jazzy/setup.bash
```

To run FastMapping, run ROS2 with following command

```bash
ros2 launch fast_mapping fast_mapping.launch.py
```

In parallel start the rosbag file.

```bash
ros2 bag play -s rosbag_v2 <my_ROS2_bagfile.bag>
```

### Run with depth camera and other SLAM module or fixed tf

As long as there is a SLAM module publishing tf properly (they should), we can get camera poses from the tf tree without any ambiguity of coordinates. The param `external_pose_topic` should be set to 'tf':

```bash
ros2 run fast_mapping fast_mapping_node
```

In this way, the fast_mapping_node will request a transform from the tf tree.
This transform is from the map frame, defined by the `map_frame` parameter (the default being "map"),
to the optical frame of the camera. This optical frame is specified in the header of the depth image messages
(for instance, `camera_color_optical_frame` if you are utilizing a RealSense camera with `rs_aligned_depth.launch`).
The transforms that are published to the tf tree do not necessarily need to be in sync with the depth images.
ROS tf will carry out a linear interpolation between the nearest available transforms
when a transform is requested at a particular time.

The FastMapping algorithm will start and poll until a `CameraInfo` message will come.

```bash
ros2 run fast_mapping fast_mapping_node
[INFO] []: waiting for camera depth info from camera/aligned_depth_to_color/camera_info
[INFO] []: waiting for camera depth info from camera/aligned_depth_to_color/camera_info
[INFO] []: waiting for camera depth info from camera/aligned_depth_to_color/camera_info
```

In parallel start the rosbag file.

```bash
ros2 bag play -s rosbag_v2 <my_ROS2_bagfile.bag>
```

Start rviz2 for visualization.

```bash
rviz2
```

## Documentation

Comprehensive documentation on this component is available here: [dev guide](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/navigation/run-fastmapping-algorithm.html).

## License

``fast-mapping`` is licensed under [Apache 2.0 License](./LICENSES/Apache-2.0.txt).
