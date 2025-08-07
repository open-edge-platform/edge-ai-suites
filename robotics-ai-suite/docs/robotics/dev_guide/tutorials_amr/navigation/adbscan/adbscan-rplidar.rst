ADBSCAN Algorithm with RPLIDAR Input Demo
==========================================================================


This tutorial describes how to run the ADBSCAN algorithm from |p_amr|
using 2D  RPLIDAR input.

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


Run the demo with 2D LIDAR
--------------------------------


   .. code-block::

      sudo chmod +x /opt/ros/humble/share/adbscan_ros2/scripts/demo_lidar.sh
      /opt/ros/humble/share/adbscan_ros2/scripts/demo_lidar.sh

Expected output: ADBSCAN prints logs of its interpretation of the LIDAR data coming from the |ros| bag.

   .. image:: ../../../../images/adbscan_demo_lidar.jpg

One can view the list of running |ros| nodes by typing ``ros2 node list`` in a terminal.

   .. image:: ../../../../images/adbscan_node_list.jpg

