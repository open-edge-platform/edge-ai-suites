# ADBSCAN Algorithm with 2D RPLIDAR Input Demo

This tutorial describes how to run the ADBSCAN algorithm from Autonomous Mobile Robot
using 2D RPLIDAR input.

## Prerequisites

Complete the [get started guide](../../../../gsg_robot/index.rst) before continuing.

## Install

Install `ros-jazzy-adbscan-ros2` Deb package from Intel® Autonomous Mobile Robot APT repository

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: tab1hide_directive-->

```bash
sudo apt update
sudo apt install ros-jazzy-adbscan-ros2
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: tab2hide_directive-->

```bash
sudo apt update
sudo apt install ros-humble-adbscan-ros2
```

<!--hide_directive:::
::::hide_directive-->

Install the following package with ROS 2 bag files in order to publish point
cloud data from 2D LIDAR or Intel® RealSense™ camera

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: tab1hide_directive-->

```bash
sudo apt install ros-jazzy-bagfile-laser-pointcloud
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: tab2hide_directive-->

```bash
sudo apt install ros-humble-bagfile-laser-pointcloud
```

<!--hide_directive:::
::::hide_directive-->

## Run the demo with 2D LIDAR input

```bash
ros2 launch adbscan_ros2 play_demo_lidar_launch.py
```

Expected output: ADBSCAN prints logs of its interpretation of the LIDAR data
coming from the ROS 2 bag.

![adbscan_demo_lidar](../../../../images/adbscan_demo_lidar.jpg)

One can view the list of running ROS 2 nodes by typing `ros2 node list` in a terminal.

![adbscan_node_list](../../../../images/adbscan_node_list.jpg)

## ADBSCAN ROS2 Node Output description

The output is published to the ROS2 topic `obstacle_array`,
and the message format is `nav2_dynamic_msgs::msg::ObstacleArray`.

To view the messages being published to the `obstacle_array`
topic, you can use the following command:

```bash
ros2 topic echo /obstacle_array
```

How to Visualize the Output in RViz

1. **Launch RViz**:

   - Open a terminal and start RViz by typing:

     ```bash
     rviz2
     ```

2. **Subscribe to the Topic**:

   - In RViz, add a new display by clicking on `Add` in the `Displays` panel.
   - Select `MarkerArray` from the list of available display types.
