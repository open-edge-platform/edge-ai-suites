# ITS Plugin for ROS2 Navigation
This plugin is a global path planner module which is based on the Intelligent Sampling and Two-Way Search (ITS).  Currently, the ITS plugin does not support continuous replanning. To use this plugin, a simple behavior tree with compute path to pose and follow path should be used.

The inputs for the ITS planner are global 2d_costmap (`nav2_costmap_2d::Costmap2D`), start and goal pose (`geometry_msgs::msg::PoseStamped`).  The outputs are 2D waypoints of the path.  The ITS planner gets the 2d_costmap and it converts it to either Probabilistic Road Map (PRM) or Deterministic Road Map (DRM). The generated roadmap will be saved in a txt file which could be reused in future for multiple inquiries.  Once a roadmap is generated, the ITS conducts a two-way search to find a path from the source to destination.   Either the smoothing filter or catmull spline interpolation can be used to create a smooth and continuous path.  The generated smooth path is in the form of ROS navigation message type (`nav_msgs::msg`).

## Component Documentation

Comprehensive documentation on this component is available here: [Link](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/dev_guide/tutorials_amr/navigation/its-path-planner-plugin.html)

## nav2_params.yaml
To use this plugin, the following parameters needs to be added to the nav2_params.yaml
```sh
planner_server:
  ros__parameters:
    expected_planner_frequency: 0.01
    use_sim_time: True
    planner_plugins: ["GridBased"]
    GridBased:
      plugin: "its_planner/ITSPlanner"
      interpolation_resolution: 0.05
      catmull_spline: False
      smoothing_window: 15
      buffer_size: 10
      build_road_map_once: True
      min_samples: 250
      roadmap: "PROBABLISTIC"
      w: 32
      h: 32
      n: 2
```

`catmull_spline`: if true, the generated path from the ITS will be interpolated with catmull spline method; otherwise smoothing filter will be used to smooth the path

`smoothing_window`:  window size for the smoothing filter; unit is grid size

`buffer_size`: during the roadmap generation, the samples are generated away from obstacles.  The buffer size dictates how far the roadmap samples should be away from obstacles

`build_road_map_once`:  If true, the roadmap will be loaded from the saved file, otherwise a new roadmap will be generated

`min_samples`: minimum number of samples required to to generate the roadmap

`roadmap`: can be either `PROBABLITIC` or `DETERMINISTIC`

`w`: the width of the window for intelligent sampling

`h`: the height of the window for intelligent sampling

`n`: the minimum number of samples that is required in an area defined by `w` and `h`

## Getting Started
Robotics AI Suite provides a ROS2 Debian package for the application, supported by the following platform:

- OS: Ubuntu 22.04

- ROS version: humble

## Prerequisites

- [Prepare the target system](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/prepare-system.html)
- [Setup the Robotics AI Dev Kit APT Repositories](https://docs.openedgeplatform.intel.com/robotics-ai-suite/robotics-ai-suite/main/robotics/gsg_robot/apt-setup.html)
- [Install OpenVINO™ Packages](https://docs.openedgeplatform.intel.com/robotics-ai-suite/robotics-ai-suite/main/robotics/gsg_robot/install-openvino.html)
- [Install Robotics AI Dev Kit Deb packages](https://docs.openedgeplatform.intel.com/robotics-ai-suite/robotics-ai-suite/main/robotics/gsg_robot/install.html)
- [Install the Intel® NPU Driver on Intel® Core™ Ultra Processors (if applicable)](https://docs.openedgeplatform.intel.com/robotics-ai-suite/robotics-ai-suite/main/robotics/gsg_robot/install-npu-driver.html)

## Install Debian Package

Install the ``ros-humble-its-planner`` Debian package from the Intel Robotics AI Suite APT repo

```sh
sudo apt install ros-humble-its-planner
```

Run the following script to set environment variables:

```sh
source /opt/ros/humble/setup.bash
export TURTLEBOT3_MODEL=waffle_pi
export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH:/opt/ros/humble/share/turtlebot3_gazebo/models
```

To launch the default ITS planner which is based on differential drive robot, run:

```sh
ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False params_file:=/opt/ros/humble/share/its_planner/nav2_params.yaml default_bt_xml_filename:=/opt/ros/humble/share/its_planner/navigate_w_recovery.xml
```

ITS Planner also supports ackermann steering; to launch the ackermann ITS planner run:

```sh
ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False params_file:=/opt/ros/humble/share/its_planner/nav2_params_dubins.yaml default_bt_xml_filename:=/opt/ros/humble/share/its_planner/navigate_w_recovery.xml
```
## To Build from source
For detailed instructions, follow the ROS2 Navigation Getting Started guide:
- [Getting Started](https://navigation.ros.org/getting_started/index.html)

To summarize:
1. Install the [ROS 2 humble binary packages](https://docs.ros.org/en/rolling/Installation/Ubuntu-Install-Debians.html) as described in the official docs
2. Install Nav2 packages using your operating system's package manager:
    ```sh
    sudo apt install ros-humble-navigation2
    sudo apt install ros-humble-nav2-bringup
    ```
3. Install the Turtlebot 3 packages:

    ```sh
    sudo apt install ros-humble-turtlebot3*
    ```
4. Build  ITS Planner
    ```sh
    colcon build --packages-select its_planner
    ```
## Navigation Usage
For detailed instructions, follow the ROS2 Navigation usage guide:
- [Navigation usage](https://navigation.ros.org/getting_started/index.html#navigating)

To summarize:

After launching the ROS2 navigation and the ITS planner plugin, look at where the robot is in the Gazebo world, and find that spot on the Rviz display.

1. from Rviz set the initial pose by clicking the "2D Pose Estimate" button
2. click on the map where the robot is
3. click the "Navigation2 Goal" button and choose goal position

Now a path will be generated and the robot will start following the path to navigate toward the goal position.

## Ackermann Steering Support
This plugin also supports a global path planner based on ITS for Ackermann steering vehicles, which maneuver with car-like controls and a limited turning radius. This version of the planner is based on the concept of [Dubins Paths](https://en.wikipedia.org/wiki/Dubins_path), and uses an adapted version of [AndrewWalker's Dubins Curves implementation](https://github.com/AndrewWalker/Dubins-Curves).


The Ackermann steering version of this plugin utilizes some additional parameters which can be found in `nav2_params_dubins.yaml`

<pre><code>planner_server:
  ros__parameters:
    expected_planner_frequency: 0.01
    use_sim_time: True
    planner_plugins: ["GridBased"]
    GridBased:
      plugin: "its_planner/ITSPlanner"
      interpolation_resolution: 0.05
      catmull_spline: False
      smoothing_window: 15
      buffer_size: 10
      build_road_map_once: True
      min_samples: 250
      roadmap: "PROBABLISTIC"
      w: 32
      h: 32
      n: 2
    <b>-- Dubins Specific -- 
      dubins_path: True
      turn_radius: .22
      robot_radius: .25
      yaw_tolerance: .125
      use_final_heading: True</b>
</code></pre>

`dubins_path`: If true, the ITS algorithm will utilize Dubins Paths to form a global path that can be followed by an Ackermann steering vehicle. 

`turn_radius`: The minimum turning radius of the robot, in world scale.

`robot_radius`: The radius of the robot, in world scale. 

`yaw_tolerance`: The amount (+/-) by which the heading angles of the end positions of the intermediate Dubins curves may vary, in radians. Does not apply to the final Goal heading. 

`use_final_heading`: Whether to use the goal heading specified by the `geometry_msgs::msg::PoseStamped` message or not.
