# Control the Jackal Motors Using a Keyboard

This section shows how to verify that the
Jackal robot is set up correctly, by confirming
that the ROS 2 middleware is working and the
Jackal robot's onboard computer can communicate with the Motor
Control Unit (MCU).

Ensure that you have set up your Jackal robot as described on the
[Jackal Intel Robotics](./jackal-intel-robotics-sdk.md) page.

Log in as the ``administrator`` to run the following steps:

1. Test whether the Clearpath Robotics services are running on your robot:

   ```bash
   ros2 topic info -v /cmd_vel
   ```

   You need the ``/cmd_vel`` topic for controlling the motors, therefore
   the output of this command must indicate that the ``/cmd_vel`` topic is
   subscribed by the ``twist_mux`` node:

   ```console
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
   ```

   If you do not see this output, there might be an issue with your
   Clearpath Robotics services installation.
   See the [Jackal Troubleshooting](./jackal-intel-robotics-sdk.md#jackal-troubleshooting)
   section for debugging hints.

1. Install the `teleop-twist-keyboard` ROS 2 package:

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   sudo apt-get update
   sudo apt-get install ros-jazzy-teleop-twist-keyboard
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   sudo apt-get update
   sudo apt-get install ros-humble-teleop-twist-keyboard
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

1. Start the ``teleop_twist_keyboard`` command-line tool:

   ```bash
   ros2 run teleop_twist_keyboard teleop_twist_keyboard
   ```

   Then you can control the robot using these keys:

   ||||
   |:-:|:-:|:-:|
   | u | i | o |
   | j | k | l |
   | m | , | . |

1. You can also manually publish to the ``/cmd_vel`` topic to move the robot.
   For example, to move to the x direction, run:

   ```bash
   ros2 topic pub /cmd_vel geometry_msgs/msg/Twist \
   "linear:
     x: 1.0
     y: 0.0
     z: 0.0
   angular:
     x: 0.0
     y: 0.0
     z: 0.0"
   ```
