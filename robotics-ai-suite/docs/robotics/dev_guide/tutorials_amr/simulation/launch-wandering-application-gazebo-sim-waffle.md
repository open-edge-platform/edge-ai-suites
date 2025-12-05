# Wandering Application in TurtleBot3 Waffle robot through Gazebo Simulation

This tutorial shows a TurtleBot3 Waffle robot performing autonomous mapping of
the TurtleBot3 robot world in the Gazebo simulation.
For more information about TurtleBot3 Waffle robot, refer to
[TurtleBot3 documentation](https://emanual.robotis.com/docs/en/platform/turtlebot3/simulation/#gazebo-simulation).

## Prerequisites

Complete the [get started guide](../../../gsg_robot/index.rst) before continuing.

## Run the Sample Application

1. If your system has an Intel® GPU, follow the steps in the
   [get started guide](../../../gsg_robot/index.rst) to enable the GPU for
   simulation. This step improves Gazebo simulation performance.

2. Install dependencies:

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   sudo apt-get install ros-jazzy-rtabmap-ros
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   sudo apt-get install ros-humble-rtabmap-ros
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

3. Install the Wandering Gazebo tutorial:

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   sudo apt-get install ros-jazzy-wandering-gazebo-tutorial
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   sudo apt-get install ros-humble-wandering-gazebo-tutorial
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

4. Execute the command below to start the tutorial:

   ```bash
   ros2 launch wandering_gazebo_tutorial wandering_gazebo.launch.py
   ```

   **Expected output:**

   Gazebo client, rviz2 and RTAB-Map applications start and the robot
   starts wandering inside the simulation. See the simulation
   snapshot:

   ![gazebo_waffle](../../../images/gazebo_waffle.png)

   Rviz2 shows the mapped area and the position of the robot:

   ![wandering-gazebo-rviz2](../../../images/wandering-gazebo-rviz2.png)

   To enhance performance, set the real-time update to 0 by following
   the steps below:

   1. In Gazebo's left panel, go to the **World** Tab, and click
      **Physics**.
   2. Change the real time update rate to 0.

5. To conclude, use ``Ctrl-c`` in the terminal where you are executing
   the command.

## Troubleshooting

For general robot issues, refer to
[Troubleshooting](../../../dev_guide/tutorials_amr/robot-tutorials-troubleshooting.md).
