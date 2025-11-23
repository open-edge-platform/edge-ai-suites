Supported peripherals
*********************

Robot Vision & Control Framework is developed, tested and validated with a limited set of peripherals.



Supported Sensors
=================

Tier 1 Sensors
--------------

Preferred sensors, utilized for use-case examples, tested & validated

* Intel® RealSense™ `D400 Family <https://www.intelrealsense.com/introducing-intel-realsense-d400-product-family/>`__ cameras

Tier 2 Sensors
--------------

Sensors occasionally used and tested


Tier 3 Sensors
--------------

Sensors expected to function, not owned, not tested

* Every 2D camera with an existing ROS driver providing ``sensor_msgs/Image`` image stream **and** ``sensor_msgs/CameraInfo`` calibration data (for use cases only requiring 2D image data)
* Every 3D camera with existing ROS2 driver providing ``sensor_msgs/Image`` image stream **and** ``sensor_msgs::msg::PointCloud2`` pointcloud scene data


Supported Robots & Actuators
============================

Tier 1 Actuators
----------------

Preferred robot or actuator, utilized for use-case examples, and tested and validated :

* Universal Robots UR5e cobot (`ROS 2 Control <https://control.ros.org/master/index.html>`__ driver)


Tier 2 Actuators
----------------

Robot/Actuator occasionally used and tested



Tier 3 Actuators
----------------

Robot/Actuator expected to function, not owned, not tested

* Every manipulator with existing ROS2 drivers with `MoveIt 2 <https://moveit.picknik.ai/main/index.html>`__ support and urdf (or xacro) robot description

