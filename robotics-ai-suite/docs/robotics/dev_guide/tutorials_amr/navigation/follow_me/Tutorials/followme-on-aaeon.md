# Follow-me with ADBSCAN on Aaeon Robot

This tutorial provides instructions for running the ADBSCAN-based Follow-me
algorithm from Autonomous Mobile Robot using Intel® RealSense™ camera input.
Validation of the the algorithm was performed on a custom Aaeon robot.
The Intel® RealSense™ camera publishes to `/camera/depth/color/points` topic.
The `adbscan_sub_node` subscribes to the corresponding topic,
detects the obstacle array, computes the robot's velocity and publishes to the
 `/cmd_vel` topic of type `geometry_msg/msg/Twist`.
This `twist` message consists of the updated angular and linear velocity of the
robot to follow the target, which can be subsequently subscribed
by a robot-driver.

## Getting Started

### Prerequisites

- Assemble your robotic kit following the instructions provided by AAEON.
- Complete the [get started guide](../../../../../gsg_robot/index.rst) before
  continuing.

### Install the Deb package

Install the `ros-jazzy-follow-me-tutorial` Deb package from the Intel®
Autonomous Mobile Robot APT repository.

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: tab1hide_directive-->

```bash
sudo apt update
sudo apt install ros-jazzy-follow-me-tutorial
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: tab2hide_directive-->

```bash
sudo apt update
sudo apt install ros-humble-follow-me-tutorial
```

<!--hide_directive:::
::::hide_directive-->

### Calibrate the robot

Please perform IMU calibration of the robot, launch script below:

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: tab1hide_directive-->

```bash
source /opt/ros/jazzy/setup.bash
/opt/ros/jazzy/share/ros2_amr_interface/scripts/calibration.sh
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: tab2hide_directive-->

```bash
source /opt/ros/humble/setup.bash
/opt/ros/humble/share/ros2_amr_interface/scripts/calibration.sh
```

<!--hide_directive:::
::::hide_directive-->

## Run Demo

To launch the Follow-me application tutorial on the Aaeon robot, use the
following ROS 2 launch file.

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: tab1hide_directive-->

```bash
source /opt/ros/jazzy/setup.bash
ros2 launch tutorial_follow_me aaeon_followme_launch.py
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: tab2hide_directive-->

```bash
source /opt/ros/humble/setup.bash
ros2 launch tutorial_follow_me aaeon_followme_launch.py
```

<!--hide_directive:::
::::hide_directive-->

After executing the above command, you can observe that the robot detecting the
target within a tracking radius (~0.5 - 1.5 m; `min_dist` and `max_dist` are set in
`/opt/ros/jazzy/share/tutorial_follow_me/params/followme_adbscan_RS_params.yaml`)
and subsequently following the moving target person.

There are reconfigurable parameters in the
`/opt/ros/jazzy/share/tutorial_follow_me/params/followme_adbscan_RS_params.yaml`
file. The user can modify the parameters depending on the respective robot, sensor
configuration and environments (if required) before running the tutorial.
Find a brief description of the parameters in the following list.

- ``Lidar_type``

  Type of the point cloud sensor. For Intel® RealSense™ camera and LIDAR inputs,
  the default value is set to ``RS`` and ``2D``, respectively.

- ``Lidar_topic``

  Name of the topic publishing point cloud data.

- ``Verbose``

  If this flag is set to ``True``, the locations of the detected target objects
  will be printed as the screen log.

- ``subsample_ratio``

  This is the downsampling rate of the original point cloud data. Default value
  = 15 (i.e. every 15-th data in the original point cloud is sampled and passed
  to the core ADBSCAN algorithm).

- ``x_filter_back``

  Point cloud data with x-coordinate > ``x_filter_back`` are filtered out
  (positive x direction lies in front of the robot).

- ``y_filter_left``, ``y_filter_right``

  Point cloud data with y-coordinate > ``y_filter_left`` and y-coordinate <
  ``y_filter_right`` are filtered out (positive y-direction is to the left of
  robot and vice versa).

- ``z_filter``

  Point cloud data with z-coordinate < ``z_filter`` will be filtered out. This
  option will be ignored in case of 2D Lidar.

- ``Z_based_ground_removal``

  Filtering in the z-direction will be applied only if this value is non-zero.
  This option will be ignored in case of 2D Lidar.

- ``base``, ``coeff_1``, ``coeff_2``, ``scale_factor``

  These are the coefficients used to calculate adaptive parameters of the
  ADBSCAN algorithm. These values are pre-computed and recommended
  to keep unchanged.

- ``init_tgt_loc``

  This value describes the initial target location. The person needs to be at a
  distance of ``init_tgt_loc`` in front of the robot to initiate the motor.

- ``max_dist``

  This is the maximum distance that the robot can follow. If the person moves at
  a distance > ``max_dist``, the robot will stop following.

- ``min_dist``

  This value describes the safe distance the robot will always maintain with the
  target person. If the person moves closer than ``min_dist``,
  the robot stops following.

- ``max_linear``

  Maximum linear velocity of the robot.

- ``max_angular``

  Maximum angular velocity of the robot.

- ``max_frame_blocked``

  The robot will keep following the target for ``max_frame_blocked`` number of
  frames in the event of a temporary occlusion.

- ``tracking_radius``

  The robot will keep following the target as long as the current target
  location = previous location +/- ``tracking_radius``

## Troubleshooting

- Failed to install Deb package: Please make sure to run `sudo apt update`
  before installing the necessary Deb packages.
- You may stop the demo anytime by pressing `ctrl-C`.
- If the robot rotates more than intended at each step, try reducing the
  parameter `max_angular` in the parameter file.
- For general robot issues, refer to
  [Troubleshooting](../../../robot-tutorials-troubleshooting.rst).
- If the motor controller board does not start, restart the robot.
