---
title: Execute the Wandering Application on the Jackal™ Robot
---

This tutorial details the steps to install and run the Wandering
Application with Intel® RealSense™ camera input on a Clearpath Robotics
Jackal™ robot. The Wandering Application will use the Nav2 navigation
stack and the RTAB-Map SLAM application to let the Jackal™ robot move
around and create a map of the environment.

# Prerequisites

- [Prepare the target system](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/robotics/gsg_robot/prepare-system.html)
- [Setup the Robotics AI Dev Kit APT Repositories](https://docs.openedgeplatform.intel.com/robotics-ai-suite/robotics-ai-suite/main/robotics/gsg_robot/apt-setup.html)
- [Install OpenVINO™ Packages](https://docs.openedgeplatform.intel.com/robotics-ai-suite/robotics-ai-suite/main/robotics/gsg_robot/install-openvino.html)
- [Install Robotics AI Dev Kit Deb packages](https://docs.openedgeplatform.intel.com/robotics-ai-suite/robotics-ai-suite/main/robotics/gsg_robot/install.html)
- [Install the Intel® NPU Driver on Intel® Core™ Ultra Processors (if applicable)](https://docs.openedgeplatform.intel.com/robotics-ai-suite/robotics-ai-suite/main/robotics/gsg_robot/install-npu-driver.html)

# Installation and Execution

Make sure that you have set up your Jackal™ robot as described on the
`./jackal-intel-robotics-sdk`{.interpreted-text role="doc"} page. In
addition, you can run the steps on page
`./jackal-keyboard-teleop`{.interpreted-text role="doc"} in order to
verify that your ROS 2 installation can communicate with the Motor
Control Unit (MCU).

To install the Deb package of the Wandering tutorial on Jackal™ robots,
run the following command:

``` bash
sudo apt update
sudo apt install ros-humble-wandering-jackal-tutorial
```

Make sure that you are logged in as the `administrator` user. Run the
following script, which will start the Wandering Application. After a
few seconds, the Jackal™ robot will start moving and the RTAB-Map SLAM
application will create the map.

``` bash
/opt/ros/humble/share/wandering_jackal_tutorial/scripts/wandering_jackal.sh
```

<figure class="align-center">
<img src="../../../../images/wandering-jackal-rviz2.png"
alt="../../../../images/wandering-jackal-rviz2.png" />
<figcaption>Wandering Application running on the Jackal™ robot: the
rviz2 tool shows the robot with the identified map and the image of the
Intel® RealSense™ camera.</figcaption>
</figure>

# Jackal™-Specific Adaptations

The shell script and the launch file of the Wandering tutorial have been
adapted to the ecosystem of the Jackal™ robot. In particular, they
include several remapping definitions, which align the camera and IMU
related topics with the topic names expected by the nodes of the
Wandering tutorial.

You don\'t have to read the following subsections if you just want to
run the tutorial. But they might provide relevant background information
if you want to adapt the tutorial to a robot with a different ecosystem.

## Adaptation of the Camera Namespace

As mentioned on the `./jackal-intel-robotics-sdk`{.interpreted-text
role="doc"} page, the names of the camera-related topics depend on the
version of the installed `ros-humble-realsense2-camera` package. The
camera-related topics start with:

- `/sensors/camera_0/camera/` if the `ros-humble-realsense2-camera`
  package is version 4.55
- `/sensors/camera_0/` if the `ros-humble-realsense2-camera` package is
  version 4.54

In order to support both versions of the `ros-humble-realsense2-camera`
package, the shell script
`/opt/ros/humble/share/wandering_jackal_tutorial/scripts/wandering_jackal.sh`
checks the name of the camera-related topics and assigns the variable
`${CAMERA_NAMESPACE}` according to the identified camera namespace.

## Adaptation of the depthimage_to_laserscan Node

This node converts the depth image of the Intel® RealSense™ camera into
a 2D laser scan. The node expects that it can subscribe to the topics
`depth` and `depth_camera_info`. This requirement is fulfilled by
remapping the following topics, which are published by the `camera` node
of the Jackal™ robot:

- if `ros-humble-realsense2-camera` version is 4.55:

    -----------------------------------------------------------------------------------------------------
    Topic name expected by the node                    True topic name on the Jackal™ robot
    -------------------------------------------------- --------------------------------------------------
    `depth`                                            `/sensors/camera_0/camera/depth/image_rect_raw`

    `depth_camera_info`                                `/sensors/camera_0/camera/depth/camera_info`
    -----------------------------------------------------------------------------------------------------

- if `ros-humble-realsense2-camera` version is 4.54:

    -----------------------------------------------------------------------------------------------------
    Topic name expected by the node                    True topic name on the Jackal™ robot
    -------------------------------------------------- --------------------------------------------------
    `depth`                                            `/sensors/camera_0/depth/image_rect_raw`

    `depth_camera_info`                                `/sensors/camera_0/depth/camera_info`
    -----------------------------------------------------------------------------------------------------

The script
`/opt/ros/humble/share/wandering_jackal_tutorial/scripts/wandering_jackal.sh`
considers the necessary remapping of both topics when it starts the
`depthimage_to_laserscan` node:

``` bash
ros2 run depthimage_to_laserscan depthimage_to_laserscan_node --ros-args \
         --remap depth:=${CAMERA_NAMESPACE}/depth/image_rect_raw \
         --remap depth_camera_info:=${CAMERA_NAMESPACE}/depth/camera_info \
         -p scan_time:=0.033 -p range_min:=0.1 -p range_max:=2.5 \
         -p output_frame:=camera_0_depth_frame &
```

The `depthimage_to_laserscan` node publishes the topic `/scan`, which is
subscribed by several other nodes. The laser scan messages, which are
broadcast via this topic, must include a frame id. This frame id, whose
default value is `camera_depth_frame`, must be adapted to the actual
link name on the robot. According to the TF2 tree of the Jackal™ robot,
which is shown on the `./jackal-intel-robotics-sdk`{.interpreted-text
role="doc"} page, the actual link name is `camera_0_depth_frame`.

The above `ros2 run` command specifies the appropriate output frame id
when it starts the `depthimage_to_laserscan` node. This is achieved by
means of the parameter `output_frame:=camera_0_depth_frame`.

## Adaptation of the imu_filter_madgwick Node

This filter node fuses angular velocities and accelerations from the
robot\'s IMU device into an orientation. The node expects that it can
subscribe to the topic `/imu/data_raw`. The topic `/imu/data_raw` is a
remapped representation of the topic `/sensors/imu_0/data_raw`, which is
published by the `jackal_mcu` node of the Jackal™ robot:

  -----------------------------------------------------------------------------------------------------
  Topic name expected by the node                    True topic name on the Jackal™ robot
  -------------------------------------------------- --------------------------------------------------
  `/imu/data_raw`                                    `/sensors/imu_0/data_raw`

  -----------------------------------------------------------------------------------------------------

The script
`/opt/ros/humble/share/wandering_jackal_tutorial/scripts/wandering_jackal.sh`
considers the necessary remapping when it starts the
`imu_filter_madgwick` node:

``` bash
ros2 run imu_filter_madgwick imu_filter_madgwick_node --ros-args \
         -p remove_gravity_vector:=true -p use_mag:=false -p publish_tf:=false \
         --remap /imu/data_raw:=/sensors/imu_0/data_raw &
```

## Adaptation of the rgbd_sync Node

This node synchronizes RGB, depth and camera_info messages into a single
message. The node expects that it can subscribe to the topics
`rgb/image`, `rgb/camera_info`, and `depth/image`. This requirement is
fulfilled by remapping the following topics, which are published by the
`camera` node of the Jackal™ robot:

- if `ros-humble-realsense2-camera` version is 4.55:

    ----------------------------------------------------------------------------------------------------------------
    Topic name expected by the node                    True topic name on the Jackal™ robot
    -------------------------------------------------- -------------------------------------------------------------
    `rgb/image`                                        `/sensors/camera_0/camera/color/image_raw`

    `rgb/camera_info`                                  `/sensors/camera_0/camera/color/camera_info`

    `depth/image`                                      `/sensors/camera_0/camera/aligned_depth_to_color/image_raw`
    ----------------------------------------------------------------------------------------------------------------

- if `ros-humble-realsense2-camera` version is 4.54:

    ---------------------------------------------------------------------------------------------------------
    Topic name expected by the node                    True topic name on the Jackal™ robot
    -------------------------------------------------- ------------------------------------------------------
    `rgb/image`                                        `/sensors/camera_0/color/image_raw`

    `rgb/camera_info`                                  `/sensors/camera_0/color/camera_info`

    `depth/image`                                      `/sensors/camera_0/aligned_depth_to_color/image_raw`
    ---------------------------------------------------------------------------------------------------------

The node publishes the topic `rgbd_image`, which is remapped to

- `/sensors/camera_0/camera/rgbd_image` if the
  `ros-humble-realsense2-camera` package is version 4.55,
- `/sensors/camera_0/rgbd_image` if the `ros-humble-realsense2-camera`
  package is version 4.54.

The definition of the remapping can be found in the launch files
`rtabmap_jackal.launch.py` and `rtabmap_jackal.rs454.launch.py`. Both
launch files can be found in the folder
`/opt/ros/humble/share/wandering_jackal_tutorial/launch/`.

## Adaptation of the rtabmap Node

This node implements the RTAB-Map SLAM approach. The node expects that
it can subscribe to the topic `rgbd_image`. The topic `rgbd_image` is a
remapped representation of the topic

- `/sensors/camera_0/camera/rgbd_image` if the
  `ros-humble-realsense2-camera` package is version 4.55,
- `/sensors/camera_0/rgbd_image` if the `ros-humble-realsense2-camera`
  package is version 4.54,

which is published by the `rgbd_sync` node.

The definition of the remapping can be found in the launch files
`rtabmap_jackal.launch.py` and `rtabmap_jackal.rs454.launch.py`. Both
launch files can be found in the folder
`/opt/ros/humble/share/wandering_jackal_tutorial/launch/`.
