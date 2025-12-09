# ITS Path Planner ROS 2 Navigation Plugin

Intelligent Sampling and Two-Way Search (ITS) global path planner is an Intel®
patented algorithm.

The ITS Plugin for the ROS 2 Navigation 2 application plugin is a global path
planner module that is based on Intelligent sampling and Two-way Search (ITS).

ITS is a new search approach based on two-way path planning and intelligent
sampling, which reduces the compute time by about 20x-30x on a 1000 nodes map
comparing with the A\* search algorithm. The inputs are the 2D occupancy grid
map, the robot position, and the goal position.

It does not support continuous replanning.

Prerequisites: Use a simple behavior tree with a compute path to pose and a
follow path.

ITS planner inputs:

- global 2D costmap (`nav2_costmap_2d::Costmap2D`)
- start and goal pose (`geometry_msgs::msg::PoseStamped`)

ITS planner outputs: 2D waypoints of the path

Path planning steps summary:

1. The ITS planner converts the 2D costmap to either a Probabilistic Road Map
   (PRM) or a Deterministic Road Map (DRM).
2. The generated roadmap is saved as a txt file which can be reused for multiple
   inquiries.
3. The ITS planner conducts a two-way search to find a path from the source to
   the destination. Either the smoothing filter or a catmull spline
   interpolation can be used to create a smooth and continuous path. The
   generated smooth path is in the form of a ROS 2 navigation message type
   (`nav_msgs::msg`).

For customization options, see
[ITS Path Planner Plugin Customization](./its-customization.md).

## Source Code

The source code of this component can be found here:
[ITS-Planner](https://github.com/open-edge-platform/edge-ai-suites/tree/main/robotics-ai-suite/components/its-planner)

## Getting Started

Autonomous Mobile Robot provides a ROS 2 Deb package for the application,
supported by the following platform:

- ROS version: Jazzy, Humble

### Prerequisites

Complete the [get started guide](../../../gsg_robot/index.rst) before continuing.

### Install Deb package

Install dependencies required to run simulations:

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
sudo apt install ros-jazzy-turtlesim ros-jazzy-turtlebot3-simulations ros-jazzy-turtlebot3-gazebo ros-jazzy-turtlebot3
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
sudo apt install ros-humble-turtlesim ros-humble-turtlebot3-simulations ros-humble-turtlebot3-gazebo ros-humble-turtlebot3
```

<!--hide_directive:::
::::hide_directive-->

Install the ITS Path Planner Deb package from the
Intel® Autonomous Mobile Robot APT repository

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
sudo apt install ros-jazzy-its-planner
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
sudo apt install ros-humble-its-planner
```

<!--hide_directive:::
::::hide_directive-->

Run the following script to set environment variables:

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
source /opt/ros/jazzy/setup.bash
export TURTLEBOT3_MODEL=waffle_pi
export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:/opt/ros/jazzy/share/turtlebot3_gazebo/models
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=waffle_pi
export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:/opt/ros/humble/share/turtlebot3_gazebo/models
```

<!--hide_directive:::
::::hide_directive-->

To launch the default ITS planner which is based on differential drive robot, run:

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False params_file:=/opt/ros/jazzy/share/its_planner/nav2_params.yaml default_bt_xml_filename:=/opt/ros/jazzy/share/its_planner/navigate_w_recovery.xml
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False params_file:=/opt/ros/humble/share/its_planner/nav2_params.yaml default_bt_xml_filename:=/opt/ros/humble/share/its_planner/navigate_w_recovery.xml
```

<!--hide_directive:::
::::hide_directive-->

ITS Planner also supports Ackermann steering; to launch the Ackermann
ITS planner run:

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

```bash
ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False params_file:=/opt/ros/jazzy/share/its_planner/nav2_params_dubins.yaml default_bt_xml_filename:=/opt/ros/jazzy/share/its_planner/navigate_w_recovery.xml
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: humblehide_directive-->

```bash
ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False params_file:=/opt/ros/humble/share/its_planner/nav2_params_dubins.yaml default_bt_xml_filename:=/opt/ros/humble/share/its_planner/navigate_w_recovery.xml
```

<!--hide_directive:::
::::hide_directive-->

> **Note**:
>
> The above command opens Gazebo\* and rviz2 applications. Gazebo\* takes a
> longer time to open (up to a minute) depending on the host's capabilities.
> Both applications contain the simulated waffle map, and a simulated robot.
> Initially, the applications are opened in the background, but you can
> bring them into the foreground, side-by-side, for a better visual.

1. Set the robot **2D Pose Estimate** in rviz2:

   1. Set the initial robot pose by pressing **2D Pose Estimate** in rviz2.
   2. At the robot estimated location, down-click inside the 2D map. For
      reference, use the robot pose as it appears in Gazebo\*.
   3. Set the orientation by dragging forward from the down-click. This also
      enables ROS 2 navigation.

   ![2d_pose_estimate](../../../images/2d_pose_estimate.png)

2. In rviz2, press **Navigation2 Goal**, and choose a destination for the
   robot. This calls the behavioral tree navigator to go to that goal through
   an action server.

   ![set_navigation_goal](../../../images/set_navigation_goal.png)

   ![path_created](../../../images/path_created.png)

   Expected result: The robot moves along the path generated to its new
   destination.

3. Set new destinations for the robot, one at a time.

   ![goal_achived_gazebo_rviz](../../../images/goal_achived_gazebo_rviz.png)

4. To close this, do the following:

   - Type `Ctrl-c` in the terminal where you did the up command.

<!--hide_directive
```{eval-rst}
.. include:: its-customization.md
```
hide_directive-->

## Troubleshooting

For general robot issues, refer to
[Troubleshooting](../robot-tutorials-troubleshooting.md).
