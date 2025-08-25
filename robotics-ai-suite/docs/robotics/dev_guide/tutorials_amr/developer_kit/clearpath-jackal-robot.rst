|clearpath_robotics| |jackal| Robot
===================================

The |clearpath_robotics| |jackal| robot is a rugged unmanned ground robot, which is
developed and distributed by |clearpath_robotics|, a Rockwell Automation company.
Detailed information about this robot is provided by |clearpath_robotics|:

* `Jackal Unmanned Ground Vehicle <https://clearpathrobotics.com/jackal-small-unmanned-ground-vehicle/>`_ product page
* `Jackal User Manual  <https://docs.clearpathrobotics.com/docs/robots/outdoor_robots/jackal/user_manual_jackal/>`_

The following pages describe how the |lp_amr| can be used with a
|clearpath_robotics| |jackal| robot.

* :doc:`clearpath-jackal/jackal-intel-robotics-sdk` - This page depicts
  how to install and configure the |lp_amr| on the |jackal| robot.

* :doc:`clearpath-jackal/jackal-keyboard-teleop` - This page describes
  how to run a simple test with manual control of the |jackal| motors.

* :doc:`clearpath-jackal/jackal-wandering` - This page demonstrates
  how the |jackal| robot can make use of the algorithms and applications
  provided by the |lp_amr|. This is done by executing the
  Wandering Application.

* :doc:`../navigation/follow_me/Tutorials/followme-on-clearpathjackal` - This
  tutorial provides instructions for running the ADBSCAN-based Follow-me
  algorithm using an input stream from an |realsense| camera on a |jackal| robot.

* :doc:`../navigation/follow_me/Tutorials/followme-with-gesture-on-clearpathjackal` - This
  tutorial demonstrates the Follow-me algorithm along with a gesture
  recognition network, where the |jackal| robot follows a target person
  in real-time and responds to state commands through hand gestures.

.. toctree::
   :hidden:
   :maxdepth: 1

   clearpath-jackal/jackal-intel-robotics-sdk
   clearpath-jackal/jackal-keyboard-teleop
   clearpath-jackal/jackal-wandering
   ../navigation/follow_me/Tutorials/followme-on-clearpathjackal
   ../navigation/follow_me/Tutorials/followme-with-gesture-on-clearpathjackal
