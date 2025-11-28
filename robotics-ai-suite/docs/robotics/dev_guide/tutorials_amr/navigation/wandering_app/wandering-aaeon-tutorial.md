# Wandering Application on AAEON robot with Intel® RealSense™ Camera and RTAB-Map SLAM

This tutorial details the steps to install Wandering Application with
Intel® RealSense™ camera input and create a map using RTAB-Map Application.

## Getting Started

### Prerequisites

Complete the [get started guide](../../../../gsg_robot/index.rst) before continuing.

### Install Deb package

Install the `ros-jazzy-wandering-aaeon-tutorial` Deb package from the
Intel® Autonomous Mobile Robot APT repository.

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: tab1hide_directive-->

```bash
sudo apt update
sudo apt install ros-jazzy-wandering-aaeon-tutorial
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: tab2hide_directive-->

```bash
sudo apt update
sudo apt install ros-humble-wandering-aaeon-tutorial
```

<!--hide_directive:::
::::hide_directive-->

## Run Demo

Run the following commands to create a map using RTAB-Map and Wandering
Application tutorial on the Aaeon robot.

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: tab1hide_directive-->

```bash
source /opt/ros/jazzy/setup.bash
ros2 launch wandering_aaeon_tutorial wandering_aaeon.launch.py
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: tab2hide_directive-->

```bash
source /opt/ros/humble/setup.bash
ros2 launch wandering_aaeon_tutorial wandering_aaeon.launch.py
```

<!--hide_directive:::
::::hide_directive-->

Once the command is executed, the robot starts moving and creates a map with
RTAB-Map Application.

![Wandering_aaeon_tutorial](../../../../images/Wandering_aaeon_tutorial.png)

## Troubleshooting

- You can stop the demo anytime by pressing `ctrl-C`.
- For general robot issues, refer to
  [Troubleshooting](../../robot-tutorials-troubleshooting.rst).
