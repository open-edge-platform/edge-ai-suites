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

No additional system packages required � Gazebo Harmonic ships with
`ros-jazzy-ros-gz*`.

### Python Packages (gesture only)

```bash
pip3 install numpy==1.26.4 mediapipe==0.10.31 opencv-python==4.8.0.76 pyyaml
```

### Python Packages (gesture + audio)

```bash
pip3 install numpy==1.26.4 mediapipe==0.10.31 opencv-python==4.8.0.76 pyyaml \
    librosa openvino==2025.3.0 simpleaudio sounddevice tqdm inflect
```

## ROS 2 Humble (Ubuntu 22.04)

### System_Packages

```bash
sudo apt install libprotobuf-lite23 ros-humble-gazebo-* \
    ros-humble-dynamixel-sdk ros-humble-turtlebot3-msgs \
    ros-humble-turtlebot3 ros-humble-xacro
```

### Python Packages (-gesture only)

```bash
pip3 install numpy==1.24.3 mediapipe==0.10.9 opencv-python==4.8.0.76 pyyaml tensorflow
```

### Python Packages (-gesture + audio)

```bash
pip3 install numpy==1.24.3 mediapipe==0.10.9 opencv-python==4.8.0.76 pyyaml tensorflow \
    librosa openvino==2025.3.0 simpleaudio sounddevice tqdm inflect
```
