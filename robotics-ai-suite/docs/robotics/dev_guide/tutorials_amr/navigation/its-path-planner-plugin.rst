.. use-its-path-planner-plugin:

ITS Path Planner |ros| Navigation Plugin
========================================

Intelligent Sampling and Two-Way Search (ITS) global path planner is an |intel| patented algorithm.

The ITS Plugin for the |ros| Navigation 2 application plugin is a global path
planner module that is based on Intelligent sampling and Two-way Search (ITS).


ITS is a new search approach based on two-way path planning and intelligent sampling, which reduces the compute time by about 20x-30x on a 1000 nodes map comparing with the A* search algorithm. The inputs are the 2D occupancy grid map, the robot position, and the goal position.

It does not support continuous replanning.

Prerequisites: Use a simple behavior tree with a compute path to pose and a
follow path.

ITS planner inputs:

-  global 2D costmap (``nav2_costmap_2d::Costmap2D``)

-  start and goal pose (``geometry_msgs::msg::PoseStamped``)

ITS planner outputs: 2D waypoints of the path

Path planning steps summary:

#. The ITS planner converts the 2D costmap to either a Probabilistic Road Map
   (PRM) or a Deterministic Road Map (DRM).

#. The generated roadmap is saved as a txt file which can be reused for multiple
   inquiries.

#. The ITS planner conducts a two-way search to find a path from the source to
   the destination. Either the smoothing filter or a catmull spline
   interpolation can be used to create a smooth and continuous path. The
   generated smooth path is in the form of a |ros| navigation message type
   (``nav_msgs::msg``).

For customization options, see :doc:`../../../dev_guide/tutorials_amr/navigation/its-customization`.

Source Code
-----------

The source code of this component can be found here: `ITS-Planner <https://github.com/open-edge-platform/edge-ai-suites/robotics-ai-suite/components/its-planner>`_

Getting Started
----------------

|p_amr| provides a |ros| |deb_pack| for the application, supported by the following platform:

- ROS version: humble

Install |deb_pack|
^^^^^^^^^^^^^^^^^^^^^^^

Install the ``ros-humble-its-planner`` |deb_pack| from the |intel| |p_amr| APT repository

   .. code-block:: bash

      sudo apt install ros-humble-its-planner

Run the following script to set environment variables:

   .. code-block:: bash

      source /opt/ros/humble/setup.bash
      export TURTLEBOT3_MODEL=waffle_pi
      export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:/opt/ros/humble/share/turtlebot3_gazebo/models

To launch the default ITS planner which is based on differential drive robot, run:

   .. code-block:: bash

      ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False params_file:=/opt/ros/humble/share/its_planner/nav2_params.yaml default_bt_xml_filename:=/opt/ros/humble/share/its_planner/navigate_w_recovery.xml

ITS Planner also supports Ackermann steering; to launch the Ackermann ITS planner run:

   .. code-block:: bash

      ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False params_file:=/opt/ros/humble/share/its_planner/nav2_params_dubins.yaml default_bt_xml_filename:=/opt/ros/humble/share/its_planner/navigate_w_recovery.xml

   .. note::

      The above command opens Gazebo* and rviz2 applications. Gazebo* takes a
      longer time to open (up to a minute) depending on the host's capabilities.
      Both applications contain the simulated waffle map, and a simulated robot.
      Initially, the applications are opened in the background, but you can
      bring them into the foreground, side-by-side, for a better visual.


   a. Set the robot **2D Pose Estimate** in rviz2:

      #. Set the initial robot pose by pressing **2D Pose Estimate** in rviz2.

      #. At the robot estimated location, down-click inside the 2D map. For
         reference, use the robot pose as it appears in Gazebo*.

      #. Set the orientation by dragging forward from the down-click. This also
         enables |ros| navigation.

      .. image:: ../../../images//2d_pose_estimate.png


   #. In rviz2, press **Navigation2 Goal**, and choose a destination for the
      robot. This calls the behavioral tree navigator to go to that goal through
      an action server.

      .. image:: ../../../images//set_navigation_goal.png

      .. image:: ../../../images//path_created.png


      Expected result: The robot moves along the path generated to its new
      destination.

   #. Set new destinations for the robot, one at a time.

      .. image:: ../../../images//goal_achived_gazebo_rviz.png


   #. To close this, do the following:

      -  Type ``Ctrl-c`` in the terminal where you did the up command.


.. include:: its-customization.rst

Troubleshooting
---------------


For general robot issues, go to :doc:`../../../dev_guide/tutorials_amr/robot-tutorials-troubleshooting`.
