<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# PicknPlace

This directory contains all ROS 2 packages that make up the Pick & Place
simulation solution.

## Packages

| Package | Description |
| --- | --- |
| [`picknplace`](picknplace/README.md) | Main demo package — launch files, robot controllers, and state machines |
| [`robot_config`](robot_config/) | URDF models, MoveIt2 configs, and Nav2 parameters for the AMR and UR5 arms |
| [`gazebo_plugins`](gazebo_plugins/) | Custom Gazebo plugins: `VacuumToolPlugin` and `ConveyorBeltPlugin` |

## Supported Platforms

| ROS 2 | Ubuntu | Gazebo |
| --- | --- | --- |
| Humble | 22.04 (Jammy) | Fortress (7.x) |
| Jazzy | 24.04 (Noble) | Harmonic (8.x) |

## Quick Start

See [`picknplace/README.md`](picknplace/README.md) for full installation,
build, and run instructions.
