<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# RVC: Robot Vision and Control
## Single-Arm Two-Conveyor Demo

---

The RVC (Robot Vision and Control) demo is a Gazebo® simulation built on
ROS 2 and delivered as part of the **Intel® Robotics AI Suite**. It
showcases a tightly-coupled single-arm, two-conveyor transfer loop: a
UR5 robotic arm (ARM1) continuously picks cubes spawned on a source
conveyor belt and places them onto a second conveyor belt on the
opposite side. Cubes that leave either belt are recycled, making the
loop self-sustaining and well-suited for long-running soak tests and
performance benchmarking.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [Installation — Debian Package](#installation--debian-package)
4. [Installation — Build from Source](#installation--build-from-source)
5. [Running the Demo](#running-the-demo)
6. [Configuration](#configuration)

---

## Architecture

The simulation is composed of the following elements:

### Robot Hardware

| Element | Description |
|---------|-------------|
| **ARM1 (UR5e)** | Universal Robots® UR5e six-DOF manipulator mounted on a fixed pedestal between the two conveyor belts. Defined via URDF/Xacro inside the `rvc` package. |
| **Belt 1 — Cube Input** | Conveyor belt on ARM1's +X side. Freshly spawned cubes travel along +Y until they enter the arm's reachable workspace. |
| **Belt 2 — Cube Output** | Conveyor belt on ARM1's −X side. Placed cubes travel away from the arm; cubes that exit the belt footprint are despawned and recycled. |

### Software Stack

| Component | Role |
|-----------|------|
| **Gazebo** | Physics and rendering engine. The `rvc.world` SDF file defines the warehouse environment, lighting, and static geometry. |
| **ROS 2** | Middleware layer providing topics, services, and actions that connect all software components. Supports both **Humble** (Ubuntu 22.04) and **Jazzy** (Ubuntu 24.04). |
| **MoveIt 2** | Motion planning framework used to compute collision-free trajectories for ARM1. Plans are executed via `FollowJointTrajectory` actions. Includes the Python API. |
| **SMACH** | Python state-machine library that drives ARM1 through a continuous `PICK → PLACE → HOME` loop. Each state is a self-contained class; transitions are triggered by success or failure signals. |
| **ros_gz bridge** | Bidirectional bridge between Gazebo topics and ROS 2 topics, configured via `params/rvc_bridge.yaml`. |
| **robot_config** | Shared package (also used by the Pick & Place demo) that provides the UR5 URDF/Xacro descriptions, MoveIt 2 configurations, RViz layouts, and the Gazebo launch entrypoint. |
| **robot_config_plugins** | Shared Gazebo plugin package that supplies the `ConveyorBeltPlugin` and the `ConveyorBeltControl` ROS 2 service interface used to set belt speed at runtime. |
| **Cyclone DDS** | Recommended DDS implementation (`rmw_cyclonedds_cpp`). A bundled `cyclonedds.xml` raises participant limits to accommodate the many ROS 2 nodes created by Gazebo and MoveIt 2. |

### Control Flow

```bash
Gazebo sim
  │  dynamic pose updates (cube position)
  ▼
cube_controller.py  ──spawn/despawn cubes──►  Gazebo
  │  cube_detected topic
  ▼
arm1_controller.py (SMACH state machine)
  │  PICK state: move to pre-grasp → grasp → lift
  │  PLACE state: move to drop pose → release
  │  HOME state: return to standby configuration
  ▼
pymoveit2  ──MoveIt 2 action goals──►  MoveGroup (ARM1)
  ▼
ros2_controllers  ──joint trajectories──►  Gazebo ARM1 joints
```

---

## Prerequisites

Before installing or building the RVC demo, ensure the following steps
have been completed on the target system:

- [Prepare the target system](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html)
- [Set up the Intel® Robotics AI Suite APT repositories](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html#set-up-the-autonomous-mobile-robot-apt-repositories)
- [Install OpenVINO™ packages](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html#install-openvino-packages)
- [Install Intel® Robotics AI Suite Debian packages](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html#install-autonomous-mobile-robot-deb-packages)

### Supported Platforms

| ROS 2 Distro | Ubuntu Release | Gazebo Version |
|--------------|---------------|----------------|
| Humble | 22.04 (Jammy) | Fortress (7.x) |
| Jazzy | 24.04 (Noble) | Harmonic (8.x) |

---

## Installation — Debian Package

The simplest way to install the RVC demo is via the pre-built Debian
package from the Intel® Robotics AI Suite APT repository. The
`rvc-simulation` metapackage automatically pulls in `robot_config`,
`robot_config_plugins`, and `rvc` as dependencies.

### ROS 2 Humble

```bash
sudo apt update
sudo apt install ros-humble-rvc-simulation
```

### ROS 2 Jazzy

```bash
sudo apt update
sudo apt install ros-jazzy-rvc-simulation
```

---

## Installation — Build from Source

Use this method to modify the source code or to work with the latest
unreleased changes.

### 1. Clone the repository

```bash
git clone <repository-url>
cd applications.robotics.mobile.simulations
```

### 2. Source the ROS 2 environment

```bash
# Humble
source /opt/ros/humble/setup.bash

# Jazzy
source /opt/ros/jazzy/setup.bash
```

### 3. Install system dependencies

```bash
sudo apt update
sudo apt install -y \
    ros-${ROS_DISTRO}-moveit \
    ros-${ROS_DISTRO}-ros-gz \
    ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
    python3-smach
```

### 4. Build with colcon

Build only the packages needed for the RVC demo:

```bash
colcon build --packages-select robot_config robot_config_plugins rvc
```

To build all packages in the workspace:

```bash
colcon build
```

### 5. Source the install overlay

```bash
source install/setup.bash
```

---

## Running the Demo

### Recommended — Cyclone DDS

FastDDS can cause stability issues with the large number of ROS 2
nodes that Gazebo and MoveIt 2 create. It is strongly recommended to
run the demo with Cyclone DDS:

```bash
source /opt/ros/${ROS_DISTRO}/setup.bash
# If built from source, also run:
# source install/setup.bash

RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ros2 launch rvc rvc.launch.py
```

### Default (FastDDS)

```bash
source /opt/ros/${ROS_DISTRO}/setup.bash
ros2 launch rvc rvc.launch.py
```

### Launch Arguments

The `rvc.launch.py` file exposes the following arguments:

| Argument | Default | Description |
|----------|---------|-------------|
| `launch_stack` | `true` | Enable or disable the robot stack (MoveIt 2, controllers, arm controller node). Set to `false` to bring up only Gazebo for world inspection. |
| `use_sim_time` | `true` | Use Gazebo simulation time for all ROS 2 nodes. Will remain `true` when running in simulation. |

Example — launch without the robot stack:

```bash
RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ros2 launch rvc rvc.launch.py launch_stack:=false
```

---

## Configuration

### DDS Tuning

The bundled `cyclonedds.xml` file raises the maximum number of
participants allowed on the local network interface, which is necessary
for the many simultaneous DDS entities created by Gazebo and MoveIt 2.
When `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` is set, the launch file
automatically applies this configuration via the `CYCLONEDDS_URI`
environment variable.

### Gazebo Bridge

The `params/rvc_bridge.yaml` file configures the `ros_gz_bridge` node,
declaring which Gazebo topics are bridged to ROS 2 and in which
direction. Edit this file to expose additional Gazebo signals (e.g.
contact sensors, IMU data) to the ROS 2 graph.

### Conveyor Belt Speed

Belt speed is controlled at startup by the `ConveyorBeltPlugin`. The
plugin reads an initial power value from the SDF world file. No
runtime service call is required for normal operation; however, the
`robot_config_plugins/srv/ConveyorBeltControl` service can be called
at runtime to change belt speed dynamically.

### RViz

A pre-configured RViz layout for visualising ARM1's planning scene,
joint states, and trajectory is provided by the `robot_config` package.
It is launched automatically as part of the robot stack.
