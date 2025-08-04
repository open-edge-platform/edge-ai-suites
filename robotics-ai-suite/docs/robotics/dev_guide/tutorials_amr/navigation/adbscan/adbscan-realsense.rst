ADBSCAN Algorithm with |realsense| Camera Input Demo
==========================================================================


This tutorial describes how to run the ADBSCAN algorithm from |realsense| camera input.

It outputs to the ``obstacle_array`` topic of type
``nav2_dynamic_msgs/ObstacleArray``.


Install
--------------------------------

Install ``ros-humble-adbscan-ros2`` |deb_pack| from |intel| |p_amr| APT repository

   .. code-block::

      sudo apt update
      sudo apt install ros-humble-adbscan-ros2

Install the following package with |ros| bag files in order to publish point cloud data from 2D LIDAR or |realsense| camera

   .. code-block::

      sudo apt install ros-humble-bagfile-laser-pointcloud



Run the demo with |realsense|
--------------------------------

   .. code-block::

      sudo chmod +x /opt/ros/humble/share/adbscan_ros2/scripts/demo_RS.sh
      /opt/ros/humble/share/adbscan_ros2/scripts/demo_RS.sh

   Expected result: |ros| rviz2 starts, and you will see how ADBSCAN interprets
   |realsense| data coming from the |ros| bag:


      .. video:: ../../../../videos/adbscan_demo_RS.mp4
