<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Simulations

## Overview

A collection of ROS 2 simulation packages and tutorials for robotics applications, including TurtleSim tutorials, RealSense camera simulations, and Pick & Place demonstrations using Gazebo. These simulations provide a comprehensive environment for testing and developing autonomous mobile robot (AMR) applications.

## Get Started

### System Requirements

Prepare the target system following the [official documentation](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/prepare-system.html).

### Build

To build debian packages, export `ROS_DISTRO` env variable to desired platform and run `make package` command. After build process successfully finishes, built packages will be available in the `output/` directory. The following command is an example for `Jazzy` distribution.

```bash
ROS_DISTRO=jazzy make package
```

You can list all built packages:

```bash
$ ls output/|grep -i .deb
ros-jazzy-gazebo-plugins_2.3-1_amd64.deb
ros-jazzy-picknplace_2.3-1_amd64.deb
ros-jazzy-realsense2-tutorial_2.3-1_amd64.deb
ros-jazzy-robot-config_2.3-1_amd64.deb
ros-jazzy-turtlesim-tutorial_2.3-1_amd64.deb
```

`*build-deps*.deb` packages are generated during build process and installation of such packages can be skipped on target platform.

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

Finally, install the Debian packages that were built via ``make package``:

```bash
sudo apt update
cd output/
sudo apt install ./*.deb
```

### Test

To run unit tests (implemented with ``colcon``) execute the below command with target ``ROS_DISTRO`` (example for Jazzy):

```bash
ROS_DISTRO=jazzy make test
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
clean                Clean up generated Debian packages and artifacts
help                 Help message
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
source-package       Create source package tarball
test                 Test with existing packages or build & test with Colcon
```

## Usage

The simulations component provides several simulation packages and tutorials:

### TurtleSim Tutorial

Basic ROS 2 tutorial using TurtleSim for learning ROS 2 concepts and testing simple robot behaviors.

### RealSense2 Tutorial

Simulation environment for Intel RealSense depth cameras, allowing testing of perception and vision-based applications without physical hardware.

### Pick & Place Simulation

Complete Pick & Place demonstration in Gazebo simulation environment, including:
- Robot configuration packages
- Custom Gazebo plugins for robotic manipulation
- Pick & Place task implementation

These simulations can be launched individually or combined depending on your testing requirements. Refer to the individual package documentation and launch files for specific usage instructions.

## Documentation

Comprehensive documentation on this component is available here: [dev guide](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/simulation/index.html).

## License

``simulations`` is licensed under [Apache 2.0 License](./LICENSES/Apache-2.0.txt).
