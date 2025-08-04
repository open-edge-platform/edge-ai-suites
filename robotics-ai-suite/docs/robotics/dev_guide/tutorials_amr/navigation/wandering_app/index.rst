Wandering App
==================

The Wandering mobile robot application is a Robot Operating System 2 (|ros|) sample application.
It can be used with different SLAM algorithms in combination with the ROS2 navigation stack,
to move the robot around in an unknown environment.
The goal is to create a navigation map of the environment.

Moving the robot around, the selected SLAM algorithm in combination with the navigation stack
will ensure that the robot avoids hitting obstacles. The navigation map is updated continuously in real time and exposed as the respective |ros| topic.

The objective of the Wandering App is to define the waypoints to navigate the robot, to explore the environment.
This is done based on the real time navigation map data provided by the SLAM algorithm.

The |lp_amr| provides several tutorials showing the Wandering App running on robotic kits:

.. toctree::
   :maxdepth: 1

   wandering-aaeon-tutorial
   ../../developer_kit/clearpath-jackal/jackal-wandering


Source Code
-----------

The source code of this component can be found here: `Wandering <https://github.com/open-edge-platform/edge-ai-suites/robotics-ai-suite/components/wandering>`_
