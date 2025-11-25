Clearpath Robotics Jackal Robot
===================================

The Clearpath Robotics Jackal robot is a rugged unmanned ground robot, which is
developed and distributed by Clearpath Robotics, a Rockwell Automation company.
Detailed information about this robot is provided by Clearpath Robotics:

* `Jackal Unmanned Ground Vehicle <https://clearpathrobotics.com/jackal-small-unmanned-ground-vehicle/>`_ product page
* `Jackal User Manual  <https://docs.clearpathrobotics.com/docs/robots/outdoor_robots/jackal/user_manual_jackal/>`_

The following pages describe how the Autonomous Mobile Robot can be used with a
Clearpath Robotics Jackal robot.

* :doc:`clearpath-jackal/jackal-intel-robotics-sdk` - This page depicts
  how to install and configure the Autonomous Mobile Robot on the Jackal robot.

* :doc:`clearpath-jackal/jackal-keyboard-teleop` - This page describes
  how to run a simple test with manual control of the Jackal motors.

* :doc:`clearpath-jackal/jackal-wandering` - This page demonstrates
  how the Jackal robot can make use of the algorithms and applications
  provided by the Autonomous Mobile Robot. This is done by executing the
  Wandering Application.

* :doc:`../navigation/follow_me/Tutorials/followme-on-clearpathjackal` - This
  tutorial provides instructions for running the ADBSCAN-based Follow-me
  algorithm using an input stream from an Intel® RealSense™ camera on a Jackal robot.

* :doc:`../navigation/follow_me/Tutorials/followme-with-gesture-on-clearpathjackal` - This
  tutorial demonstrates the Follow-me algorithm along with a gesture
  recognition network, where the Jackal robot follows a target person
  in real-time and responds to state commands through hand gestures.

.. toctree::
   :hidden:
   :maxdepth: 1

   clearpath-jackal/jackal-intel-robotics-sdk
   clearpath-jackal/jackal-keyboard-teleop
   clearpath-jackal/jackal-wandering
   ../navigation/follow_me/Tutorials/followme-on-clearpathjackal
   ../navigation/follow_me/Tutorials/followme-with-gesture-on-clearpathjackal
