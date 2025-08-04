---
title: Wandering App
---

The Wandering mobile robot application is a Robot Operating System 2
(ROS 2) sample application. It can be used with different SLAM
algorithms in combination with the ROS2 navigation stack, to move the
robot around in an unknown environment. The goal is to create a
navigation map of the environment.

Moving the robot around, the selected SLAM algorithm in combination with
the navigation stack will ensure that the robot avoids hitting
obstacles. The navigation map is updated continuously in real time and
exposed as the respective ROS 2 topic.

The objective of the Wandering App is to define the waypoints to
navigate the robot, to explore the environment. This is done based on
the real time navigation map data provided by the SLAM algorithm.

The Robotics AI Dev Kit provides several tutorials showing the Wandering
App running on robotic kits:

- [Wandering Application in a Waffle Gazebo Simulation](launch-wandering-application-gazebo-sim-waffle.md)
- [Wandering Application on AAEON robot with Intel® RealSense™ Camera and RTAB-Map SLAM](wandering-aaeon-tutorial.md)
- [Execute the Wandering Application on the Jackal™ Robot](jackal-wandering.md)
