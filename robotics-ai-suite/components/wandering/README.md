<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Wandering - The Wandering Mobile Robot Application

## Overview

The Wandering mobile robot application is a Robot Operating System 2 (ROS 2) sample application that moves the robot around the room avoiding hitting obstacles, updating a map in real time that is exposed as the ROS topic.

The application consists of two ROS nodes, developed by Intel. In order to function properly, those two nodes depend on other ROS nodes/packages: RealSense ROS wrapper, Nav2 ROS package, RTABMAP with its ROS Wrapper and robot drivers.

This is represented on the diagram below:

![Screenshot](images/wandering_arch.png)

In the diagram above, kobuki robot was used, and its kobuki ROS node is used for issuing movement commands coming from Nav2 ROS node.

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
ros-jazzy-wandering_2.3-1_amd64.deb
ros-jazzy-wandering-aaeon-tutorial_2.3-1_amd64.deb
ros-jazzy-wandering-irobot-tutorial_2.3-1_amd64.deb
ros-jazzy-wandering-jackal-tutorial_2.3-1_amd64.deb
ros-jazzy-wandering-gazebo-tutorial_2.3-1_amd64.deb
ros-jazzy-wandering-tutorials_2.3-1_amd64.deb
```

`*build-deps*.deb` package is generated during build process and installation of such packages could be skipped on target platform.

To clean up all build artifacts:

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
sudo apt install ./ros-$(ROS_DISTRO)-wandering_*_amd64.deb
```

### Test

To run unit tests (implemented with ``colcon``) execute the below command with target ``ROS_DISTRO`` (example for Jazzy):

```bash
ROS_DISTRO=jazzy make test
```

To run E2E functional tests that validate Wandering in a practical setup, execute:

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
package              Build Debian packages
test                 Build & test with Colcon
test-e2e             Run E2E functional tests
```

## Usage

### Tutorials

This repository provides several tutorials showing the Wandering App running on robotic kits:

- [Wandering Application in a Waffle Gazebo Simulation](./docs/launch-wandering-application-gazebo-sim-waffle.md)
- [Wandering Application on AAEON robot with Intel® RealSense™ Camera and RTAB-Map SLAM](./docs/wandering-aaeon-tutorial.md)
- [Execute the Wandering Application on the Jackal™ Robot](./docs/jackal-wandering.md)

### Visualization

In the `rviz` folder, the Rviz2 config file can be found with Wandering app relevant ROS topics.

```bash
rviz2 -d rviz/config.rviz
```

![Screenshot](rviz/Rviz_config.jpg)

## Documentation

Comprehensive documentation on this component is available here: [dev guide](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/navigation/wandering_app/index.html).

## License

``wandering`` is licensed under [Apache 2.0 License](./LICENSES/Apache-2.0.txt).
