<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# RVC

The **RVC** (Robot Vision and Control) package implements a single-arm
pick-and-place demo in which a UR5 manipulator continuously moves cubes
from a source conveyor belt onto a destination conveyor belt.

This directory contains:

- `rvc/` &mdash; the ROS 2 application package (launch files, world,
  controllers, custom Gazebo bridge configuration).
- `humble/debian/`, `jazzy/debian/` &mdash; Debian packaging for the
  `ros-{distro}-rvc-simulation` metapackage that depends on
  `ros-{distro}-robot-config`, `ros-{distro}-robot-config-plugins` and
  `ros-{distro}-rvc`.
- `gen_deb.sh` &mdash; helper script to build the `rvc` `.deb` locally.

See [../docs/rvc.md](../docs/rvc.md) for usage instructions.
