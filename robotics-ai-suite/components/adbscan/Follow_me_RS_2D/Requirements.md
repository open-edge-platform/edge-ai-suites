<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Installed packages

```bash
sudo apt install python3-colcon-common-extensions python3-pip
```

## ROS 2 Jazzy (Ubuntu 24.04)

### System Packages

No additional system packages required — Gazebo Harmonic ships with
`ros-jazzy-ros-gz*`.

### Python Packages (gesture only)

```bash
pip3 install -r src/turtlebot3_simulations/followme_turtlebot3_gazebo/scripts/requirements_jazzy.txt
```

### Python Packages (gesture + audio)

```bash
pip3 install -r src/turtlebot3_simulations/followme_turtlebot3_gazebo/scripts/requirements_jazzy.txt
pip3 install librosa openvino==2025.3.0 simpleaudio sounddevice tqdm inflect
```

## ROS 2 Humble (Ubuntu 22.04)

### System Packages

```bash
sudo apt install libprotobuf-lite23 ros-humble-gazebo-* \
    ros-humble-dynamixel-sdk ros-humble-turtlebot3-msgs \
    ros-humble-turtlebot3 ros-humble-xacro
```

### Python Packages (gesture only)

```bash
pip3 install -r src/turtlebot3_simulations/followme_turtlebot3_gazebo/scripts/requirements_humble.txt
```

### Python Packages (gesture + audio)

```bash
pip3 install -r src/turtlebot3_simulations/followme_turtlebot3_gazebo/scripts/requirements_humble.txt
pip3 install librosa openvino==2025.3.0 simpleaudio sounddevice tqdm inflect
```
