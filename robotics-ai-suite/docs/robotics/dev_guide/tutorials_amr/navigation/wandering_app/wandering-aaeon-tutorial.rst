Wandering Application on AAEON robot with Intel® RealSense™ Camera and RTAB-Map SLAM
=====================================================================================

This tutorial details the steps to install Wandering Application with Intel® RealSense™ camera input and create a map using RTAB-Map Application.

Getting Started
----------------

Prerequisites
^^^^^^^^^^^^^

Complete the :doc:`../../../../gsg_robot/index` before continuing.

Install Deb package
^^^^^^^^^^^^^^^^^^^^^^^

Install the ``ros-humble-wandering-aaeon-tutorial`` Deb package from the Intel® Autonomous Mobile Robot APT repository.

   .. code-block::

      sudo apt update
      sudo apt install ros-humble-wandering-aaeon-tutorial

Run Demo
----------------

Run the following commands to create a map using RTAB-Map and Wandering Application tutorial on the Aaeon robot.

   .. code-block::

      source /opt/ros/humble/setup.bash
      ros2 launch wandering_aaeon_tutorial wandering_aaeon.launch.py

Once the command is executed, the robot starts moving and creates a map with RTAB-Map Application.

.. image:: ../../../../images/Wandering_aaeon_tutorial.png


Troubleshooting
----------------------------

- You can stop the demo anytime by pressing ``ctrl-C``.

- For general robot issues, go to: :doc:`../../../../dev_guide/tutorials_amr/robot-tutorials-troubleshooting`.
