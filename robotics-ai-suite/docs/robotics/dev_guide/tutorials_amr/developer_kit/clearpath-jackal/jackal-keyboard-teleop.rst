Control the |jackal| Motors Using a Keyboard
============================================

This page describes how to run a quick test, which verifies that the
|jackal| robot has been set up appropriately. 
It verifies that the |ros| middleware is working and that the
onboard computer of the |jackal| robot can communicate with the Motor
Control Unit (MCU).

Make sure that you have set up your |jackal| robot as described on the
:doc:`./jackal-intel-robotics-sdk` page.

To execute the following steps, you must be logged in as the ``administrator``
user.

Run the following command to test whether the |clearpath_robotics|
services are running on your robot:

.. code-block:: bash

   ros2 topic info -v /cmd_vel

Since you will need the ``/cmd_vel`` topic for controlling the motors, the
output of this command should indicate that the ``/cmd_vel`` topic is
subscribed by the ``twist_mux`` node, as shown here:

.. code-block:: text

   Type: geometry_msgs/msg/Twist

   Publisher count: 0

   Subscription count: 1

   Node name: twist_mux
   Node namespace: /
   Topic type: geometry_msgs/msg/Twist
   Endpoint type: SUBSCRIPTION
   GID: 01.0f.7f.01.8f.08.4b.ac.01.00.00.00.00.00.12.04.00.00.00.00.00.00.00.00
   QoS profile:
     Reliability: BEST_EFFORT
     History (Depth): UNKNOWN
     Durability: VOLATILE
     Lifespan: Infinite
     Deadline: Infinite
     Liveliness: AUTOMATIC
     Liveliness lease duration: Infinite

If you don't see this output, there might be an issue with your installation
of the |clearpath_robotics| services. See the :ref:`jackal-troubleshooting`
section for debugging hints.

Now you can install the ``ros-humble-teleop-twist-keyboard`` |ros| package:

.. code-block:: bash

   sudo apt-get update
   sudo apt-get install ros-humble-teleop-twist-keyboard

Start the ``teleop_twist_keyboard`` command-line tool by means of:

.. code-block:: bash

   ros2 run teleop_twist_keyboard teleop_twist_keyboard

Then you can control the robot using these keys:

+-----+-----+-----+
|  u  |  i  |  o  |
+-----+-----+-----+
|  j  |  k  |  l  |
+-----+-----+-----+
|  m  |  ,  |  .  |
+-----+-----+-----+

You can also manually publish to the ``/cmd_vel`` topic to let the robot move.
For example, to trigger a movement to the x direction, you can run:

.. code-block:: bash

   ros2 topic pub /cmd_vel geometry_msgs/msg/Twist \
   "linear:
     x: 1.0
     y: 0.0
     z: 0.0
   angular:
     x: 0.0
     y: 0.0
     z: 0.0"
