<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# ADBSCAN (Adaptive Density-Based Spatial Clustering of Applications with Noise)

## Overview

ADBSCAN is an advanced unsupervised clustering algorithm that groups high-dimensional points based on their distribution density. It is an improvement over the classic DBSCAN algorithm where the clustering parameters are adaptive based on the range, making it especially suitable for processing LiDAR data. ADBSCAN is an Intel-patented algorithm which improves the object detection range by 20-30%
on average.

This repository contains several AMR (Autonomous Mobile Robot) algorithm implementations based on ADBSCAN, including:
- **ROS2_node** - ROS2 package with a node that subscribes to pointcloud sensors (LIDAR/RealSense) and publishes a list of objects in ObstacleArray message format
- **Standalone** - Standalone C++ source code for the ADBSCAN algorithm with sample input files
- **Visualization** - Python scripts to visualize the bounding boxes of detected object clusters in pointcloud data
- **Follow_me_RS_2D** - ROS2 package implementing a person-following algorithm, including a gesture-based version. This package contains multiple sub-packages:
  - **adbscan_ros2_follow_me** - Person following algorithm with gesture-based control support
  - **follow_me_interfaces** - Custom ROS messages for gesture category and audio commands
  - **gesture_recognition_pkg** - Hand gesture recognition from camera RGB images
  - **speech_recognition_pkg** - Audio command recognition and conversion to ROS messages
  - **text_to_speech_pkg** - Text-to-speech conversion package
  - **turtlebot3_simulations** - Gazebo simulation environment for testing follow-me applications. Supported only for ROS Humble.
- **package/tutorial_follow_me** - ROS2 tutorial for running the follow-me application on a custom AAEON robot
- **package/tutorial_follow_me_w_gesture** - ROS2 tutorial for running the gesture-based follow-me application on a custom AAEON robot
- **package/tutorial_aaeon_adbscan** - ROS2 tutorial for running the ADBSCAN algorithm on a custom AAEON robot

All ROS2 packages support the following platforms:
- OS: Ubuntu 22.04 (ROS2 Humble) and Ubuntu 24.04 (ROS2 Jazzy)

## Get Started

### System Requirements

Prepare the target system following the [official documentation](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/prepare-system.html).

### Build

To build Debian packages, export the `ROS_DISTRO` environment variable to the desired platform and run the `make package` command. After the build process successfully finishes, built packages will be available in the root directory. The following command is an example for the `Jazzy` distribution:

```bash
ROS_DISTRO=jazzy make package
```

You can list all built packages:

```bash
$ ls | grep -i .deb
ros-jazzy-adbscan-ros2_2.3-1_amd64.deb
ros-jazzy-follow-me-interfaces_2.3-1_amd64.deb
ros-jazzy-adbscan-follow-me-rs2d_2.3-1_amd64.deb
...
```

The `*build-deps*.deb` packages are generated during the build process and installation of such packages can be skipped on the target platform.

To clean all build artifacts:

```bash
make clean
```

### Install

If Ubuntu 22.04 with Humble is used, then run:

```bash
source /opt/ros/humble/setup.bash
```

If Ubuntu 24.04 with Jazzy is used, then run:

```bash
source /opt/ros/jazzy/setup.bash
```

Finally, install the Debian package that was built via `make package`:

```bash
sudo apt update
find . -type f -name '*.deb' -not -name '*-build-deps_*' -not -name '*-dbgsym_*' -not -name '*.changes' -exec sudo apt-get install -f -y {} \;
```

### Test

To run unit tests (implemented with `colcon`) execute the below command with target `ROS_DISTRO` (example for Jazzy):

```bash
ROS_DISTRO=jazzy make test
```

### Development

There is a set of prepared Makefile targets to speed up the development.

In particular, use the following Makefile target to run code linters:

```bash
make lint
```

Alternatively, you can run linters individually:

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
clean                Clean up all build artifacts
clean-colcon         Clean up Colcon build and test artifacts
clean-debian         Clean up Debian packaging artifacts
help                 Display this help message
license-check        Perform a REUSE license check using docker container
lint                 Run all sub-linters using super-linter
lint-all             Run super-linter over entire repository
lint-bash            Run Bash linter using super-linter
lint-clang           Run clang linter using super-linter
lint-githubactions   Run Github Actions linter using super-linter
lint-json            Run JSON linter using super-linter
lint-markdown        Run Markdown linter using super-linter
lint-python          Run Python linter using super-linter
lint-yaml            Run YAML linter using super-linter
package              Build Debian packages
test                 Test code using colcon
```

## Usage

### ROS2_node

This ROS2 package for the ADBSCAN algorithm contains a ROS2 node which subscribes to pointcloud sensors (LIDAR/RealSense camera) and publishes a list of objects in ObstacleArray message format.

Find instructions for this package: [package instructions](ROS2_node/Readme.md)

### Standalone

This directory contains standalone C++ source code for the ADBSCAN algorithm. Sample pointcloud input files to run the executable are available in the [input files](./input) directory.

### Visualization

This directory contains necessary Python scripts to visualize the bounding boxes of the object clusters in the pointcloud data.

### Follow_me_RS_2D

This is a ROS2 package for an AMR algorithm where a robot follows a target person. It contains a ROS2 node which subscribes to pointcloud sensors (LIDAR/RealSense camera), uses the ADBSCAN algorithm to cluster the data and detect the location of the target person, and subsequently publishes the velocity commands for a differential drive robot.

This package contains another version of the follow-me application: gesture-based follow-me. This version integrates a gesture recognition model to the existing implementation to control the movement of the robot with hand gestures of the target person.

The `Follow_me_RS_2D` directory contains the following ROS2 packages in the `src` subdirectory:

- **adbscan_ros2_follow_me** - Core follow-me algorithm implementation with gesture-based control capabilities. Subscribes to pointcloud data, performs ADBSCAN clustering for person detection, and publishes velocity commands for differential drive robots.

- **follow_me_interfaces** - Custom ROS message definitions for inter-package communication, including gesture categories and audio command messages used by the gesture and speech recognition packages.

- **gesture_recognition_pkg** - Hand gesture recognition system using camera RGB images. Leverages the Mediapipe Hands Framework to detect and classify hand gestures, enabling gesture-based control of robot movement.

- **speech_recognition_pkg** - Audio command recognition package that captures audio input, recognizes voice commands, and converts them into ROS messages for robot control.

- **text_to_speech_pkg** - Text-to-speech conversion package that provides audio feedback to users by converting text messages into spoken audio output.

- **turtlebot3_simulations** - Gazebo simulation environment for testing and demonstrating the follow-me applications with both 2D LIDAR and RealSense camera configurations. **NOTE:** ``turtlebot3_simulations`` is only supported for ROS Humble. 

Find additional instructions for this package: [Follow_me_RS_2D package instructions](Follow_me_RS_2D/Readme.md).

### package/tutorial_follow_me

This package provides a ROS2 tutorial for the **basic follow-me application** on a custom AAEON robot. It demonstrates how to deploy the person-following pipeline based on ADBSCAN clustering, without gesture control.

### package/tutorial_follow_me_w_gesture

This package provides a ROS2 tutorial for the **gesture-based follow-me application** on a custom AAEON robot. It extends the basic follow-me pipeline with a gesture recognition model so that the robot motion can be controlled using hand gestures of the target person.

### package/tutorial_aaeon_adbscan

This package provides a ROS2 tutorial focused on **running the ADBSCAN algorithm itself** on a custom AAEON robot. It shows how to deploy and configure the ADBSCAN ROS2 node for obstacle clustering and object detection, without the full follow-me behavior.

## Documentation

Comprehensive documentation on this component is available here: [dev guide](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/navigation/adbscan/index.html)

## License

`ADBSCAN` is licensed under [Apache 2.0 License](./LICENSES/Apache-2.0.txt).
