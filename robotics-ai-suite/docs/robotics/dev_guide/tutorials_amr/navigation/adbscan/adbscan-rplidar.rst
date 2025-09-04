ADBSCAN Algorithm with 2D RPLIDAR Input Demo
==========================================================================

This tutorial describes how to run the ADBSCAN algorithm from |p_amr|
using 2D RPLIDAR input.

Prerequisites
-------------

Complete the :doc:`../../../../gsg_robot/index` before continuing.

Install
--------------------------------

Install ``ros-humble-adbscan-ros2`` |deb_pack| from |intel| |p_amr| APT repository

   .. code-block::

      sudo apt update
      sudo apt install ros-humble-adbscan-ros2

Install the following package with |ros| bag files in order to publish point cloud data from 2D LIDAR or |realsense| camera

   .. code-block::

      sudo apt install ros-humble-bagfile-laser-pointcloud

Run the demo with 2D LIDAR input
--------------------------------

   .. code-block::

      ros2 launch adbscan_ros2 play_demo_lidar_launch.py

Expected output: ADBSCAN prints logs of its interpretation of the LIDAR data coming from the |ros| bag.

   .. image:: ../../../../images/adbscan_demo_lidar.jpg

One can view the list of running |ros| nodes by typing ``ros2 node list`` in a terminal.

   .. image:: ../../../../images/adbscan_node_list.jpg

ADBSCAN ROS2 Node Output description
---------------------------------------
The output is published to the ROS2 topic `obstacle_array`,
and the message format is `nav2_dynamic_msgs::msg::ObstacleArray`.

To view the messages being published to the `obstacle_array`
topic, you can use the following command:

   .. code-block::

      ros2 topic echo /obstacle_array

How to Visualize the Output in RViz

1. **Launch RViz**:
   - Open a terminal and start RViz by typing:

   .. code-block:: bash

      rviz2


2. **Subscribe to the Topic**:
   - In RViz, add a new display by clicking on `Add` in the `Displays` panel.
   - Select `MarkerArray` from the list of available display types.
