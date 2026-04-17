<!--
Copyright (C) 2025 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# ADBSCAN ROS2 Node Documentation

## How to Build the ADBSCAN ROS2 Node Locally

To build the package, navigate to the `edge-ai-suites/robotics-ai-suite/components/adbscan/ROS2_node` directory and execute:

```bash
colcon build
```

## How to run the ADBSCAN ROS2 node
To set up the environment for running the ROS 2 nodes associated with the ADBSCAN package, please navigate to the following directory to source the `setup.bash` file: `edge-ai-suites/robotics-ai-suite/components/adbscan/ROS2_node/install/`

```bash
cd edge-ai-suites/robotics-ai-suite/components/adbscan/ROS2_node/install/
source setup.bash
```

For RealSense camera input, execute:
```bash
ros2 launch adbscan_ros2 play_demo_realsense_launch.py 
```

For Lidar input, execute:
```bash
ros2 launch adbscan_ros2 play_demo_lidar_launch.py 
```

## ADBSCAN ROS2 Node Input Description

The input data is passed into the ROS2 node through a ROS2 topic defined in the ROS2 configuration file by the parameter `Lidar_topic`. You can edit this parameter for a customized name.

The configuration files are located in the `edge-ai-suites/robotics-ai-suite/components/adbscan/ROS2_node/config` directory.

- **2D Lidar Input**:
  - **File name**: `adbscan_sub_2D.yaml`
  - **Message type**: `sensor_msgs::msg::LaserScan`

- **3D Lidar Input**:
  - **File name**: `adbscan_sub_3D.yaml`
  - **Message type**: `sensor_msgs::msg::PointCloud2`

- **Realsense Input**:
  - **File name**: `adbscan_sub_RS.yaml`
  - **Message type**: `sensor_msgs::msg::PointCloud2`

## ADBSCAN ROS2 node output description
The output is published to the ROS2 topic `obstacle_array`, and the message format is `nav2_dynamic_msgs::msg::ObstacleArray`.

To view the messages being published to the `obstacle_array` topic, you can use the following command:
``` bash
ros2 topic echo /obstacle_array
```
## How to Visualize the Output in RViz

1. **Launch RViz**:
   - Open a terminal and start RViz by typing:
     ```bash
     rviz2
     ```

2. **Subscribe to the Topic**:
   - In RViz, add a new display by clicking on `Add` in the `Displays` panel.
   - Select `MarkerArray` from the list of available display types.