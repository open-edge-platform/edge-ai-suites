# Control the Jackal Motors Using a Keyboard

This page describes how to run a quick test, which verifies that the
Jackal robot has been set up appropriately.
It verifies that the ROS 2 middleware is working and that the
onboard computer of the Jackal robot can communicate with the Motor
Control Unit (MCU).

Make sure that you have set up your Jackal robot as described on the
[Jackal Intel Robotics](./jackal-intel-robotics-sdk.rst) page.

To execute the following steps, you must be logged in as the ``administrator``
user.

Run the following command to test whether the Clearpath Robotics
services are running on your robot:

```bash

   ros2 topic info -v /cmd_vel
```

Since you will need the ``/cmd_vel`` topic for controlling the motors, the
output of this command should indicate that the ``/cmd_vel`` topic is
subscribed by the ``twist_mux`` node, as shown here:

```txt

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

If you don't see this output, there might be an issue with your installation
of the Clearpath Robotics services. See the [Jackal Troubleshooting](./jackal-intel-robotics-sdk.md#jackal-troubleshooting)
section for debugging hints.

Now you can install the `teleop-twist-keyboard` ROS 2 package:

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: tab1hide_directive-->

```bash

   sudo apt-get update
   sudo apt-get install ros-jazzy-teleop-twist-keyboard
```

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: tab2hide_directive-->

```bash

   sudo apt-get update
   sudo apt-get install ros-humble-teleop-twist-keyboard
```

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

Start the ``teleop_twist_keyboard`` command-line tool by means of:

```bash

   ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

Then you can control the robot using these keys:

||||
|:-:|:-:|:-:|
| u | i | o |
| j | k | l |
| m | , | . |

You can also manually publish to the ``/cmd_vel`` topic to let the robot move.
For example, to trigger a movement to the x direction, you can run:

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
