<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Gazebo Pick & Place Demo

A Pick-n-Place simulation using ROS 2 and Gazebo. The demo showcases
a conveyor belt, a TurtleBot3 Autonomous Mobile Robot (AMR), and two
UR5 robotic arms coordinated through the Nav2 and MoveIt2 stacks.

## Supported Platforms

| ROS 2 | Ubuntu | Gazebo |
| --- | --- | --- |
| Humble | 22.04 (Jammy) | Fortress (7.x) |
| Jazzy | 24.04 (Noble) | Harmonic (8.x) |

## Installation

Install the Debian package from the Intel® Robotics AI Dev Kit APT repository:

```bash
# Humble
sudo apt update && sudo apt install ros-humble-picknplace-simulation

# Jazzy
sudo apt update && sudo apt install ros-jazzy-picknplace-simulation
```

## Running the Demo

Cyclone DDS is recommended over FastDDS due to stability issues observed
with the large number of nodes spawned by the simulation.

```bash
source /opt/ros/$ROS_DISTRO/setup.bash
RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ros2 launch picknplace warehouse.launch.py
```

### Launch Arguments

| Argument | Default | Description |
| --- | --- | --- |
| `use_sim_time` | `true` | Use simulation clock |
| `launch_stack` | `true` | Enable Nav2 and MoveIt2 stacks |

## Building from Source

```bash
mkdir -p ~/robot_ws/src && cd ~/robot_ws/src
git clone <this-repository>

cd ~/robot_ws
source /opt/ros/$ROS_DISTRO/setup.bash
rosdep install -r --from-paths . --ignore-src --rosdistro $ROS_DISTRO -y
colcon build
source install/setup.bash
```

## Running Tests

```bash
colcon test --packages-select picknplace --return-code-on-test-failure
colcon test-result --verbose
```

## Overview

### Robots

- **ARM1 / ARM2**: UR5 robotic arms, each in their own namespace, controlled via MoveIt2.
- **AMR (amr1)**: Customized TurtleBot3 Waffle, navigated autonomously via Nav2.

### Demo Workflow

1. ARM1 picks an item from the moving conveyor belt.
2. The item is placed onto the AMR.
3. The AMR autonomously navigates to ARM2 using Nav2.
4. ARM2 picks the item from the AMR.

### Controllers

Each robot is driven by a dedicated Python script under `scripts/`:

| Script | Robot |
| --- | --- |
| `arm1_controller.py` | ARM1 pick-and-place state machine (Smach) |
| `arm2_controller.py` | ARM2 pick-and-place state machine (Smach) |
| `amr_controller.py` | AMR navigation state machine (Nav2) |
| `cube_controller.py` | Spawns cubes on the conveyor belt via Gazebo Transport |

MoveIt2 commands are issued through a modified version of
[pymoveit2](https://github.com/AndrejOrsula/pymoveit2) (`scripts/moveit2.py`).

## Advanced Usage

### Commanding ARM2 via CLI

```bash
source ~/robot_ws/install/setup.bash
ros2 run picknplace arm2_controller.py --ros-args -r __ns:=/arm2 \
  -p cartesian:=True -p position:=[0.39,-0.2799,0.1]
```

### Sending a Nav2 Goal to the AMR

```bash
ros2 action send_goal /amr1/navigate_to_pose nav2_msgs/action/NavigateToPose \
  "pose: {header: {frame_id: map}, pose: {position: {x: -3.2, y: -0.50, z: 0.0}, orientation: {w: 1.0}}}"
```

## Implementation Notes

**State machine**: Both ARM and AMR controllers use the
[Smach](http://wiki.ros.org/smach) library to implement hierarchical
state machines.

**Object location**: Perception is bypassed; object positions are read
directly from Gazebo. Conveyor cubes are marked with Aruco markers for
future vision-based integration.

**Sequential model spawning**: Gazebo models are spawned one at a time
to prevent ROS 2 namespace collisions caused by the controller manager
altering the global `gz-server` namespace during robot initialization.
A custom Gazebo plugin in `robot_config_plugins` handles the namespace reset.

**Cyclone DDS**: Recommended over FastDDS to avoid instability from the
high volume of DDS participants created by `gz-server`.

```bash
# Install Cyclone DDS (included via rosdep)
sudo apt-get install ros-$ROS_DISTRO-rmw-cyclonedds-cpp
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```
