ADBSCAN Algorithm with |realsense| Camera Input Demo
==========================================================================

This tutorial describes how to run the ADBSCAN algorithm from |realsense| camera input.

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


Run the demo with |realsense| camera
-------------------------------------

   .. code-block::

      ros2 launch adbscan_ros2 play_demo_realsense_launch.py

   Expected result: |ros| rviz2 starts, and you will see how ADBSCAN interprets
   |realsense| camera data coming from the |ros| bag (click on the video to play):


      .. video:: ../../../../videos/adbscan_demo_RS.mp4

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
