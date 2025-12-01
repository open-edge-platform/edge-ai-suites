# Follow-me with ADBSCAN and Gesture-based Control on Clearpath Robotics Jackal Robot

This tutorial demonstrates the Follow-me algorithm along with a gesture
recognition network, where the robot follows a target person in real time and
responds to state commands through hand gestures.
This tutorial uses Clearpath Robotics Jackal robot and one Intel® RealSense™
camera D400 series. This camera provides the point cloud data as input for the
Intel®-patented object detection algorithm Adaptive DBSCAN to detect the
position of the target person. This camera also provides RGB images to the
object detection network responsible for detecting hand gestures for controlling
the robot's start and stop states. This RGB image is passed through a deep
learning-based gesture recognition pipeline, called
[Mediapipe Hands Framework](https://mediapipe.readthedocs.io/en/latest/solutions/hands.html),
to detect the gesture category. The motion commands for the robot are published
to `twist` topic based on these two outputs: person's position and
gesture category.

To start, the robot requires two conditions at the same time:

- The target person will be within the tracking radius of the robot.

  Radius is a reconfigurable parameter in:
  `/opt/ros/jazzy/share/tutorial-follow-me-w-gesture/params/followme_adbscan_RS_params.yaml`.

  In ROS 2 Humble, the file is located at the similar directory path.

- The detected gesture of the target is `thumbs up`.

Once the starting criteria are met, the robot keeps following the target unless
one of the below stopping conditions are triggered:

- The target moves to a distance greater than the tracking radius of the robot.

  Radius is a reconfigurable parameter in:
  `/opt/ros/jazzy/share/tutorial-follow-me-w-gesture/params/followme_adbscan_RS_params.yaml`.

- The detected gesture is `thumbs down`.

## Getting Started

### Prerequisites

Complete the [get started guide](../../../../../gsg_robot/index.rst)
before continuing.

### Install the Deb package

Install `ros-jazzy-follow-me-tutorial-w-gesture` Deb package from Autonomous
Mobile Robot APT repository.

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: tab1hide_directive-->

```bash
sudo apt update
sudo apt install ros-jazzy-follow-me-tutorial-w-gesture
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: tab2hide_directive-->

```bash
sudo apt update
sudo apt install ros-humble-follow-me-tutorial-w-gesture
```

<!--hide_directive:::
::::hide_directive-->

### Install Python Modules

This application uses
[Mediapipe Hands Framework](https://mediapipe.readthedocs.io/en/latest/solutions/hands.html)
for hand gesture recognition. Install the following modules as a prerequisite
for the framework:

```bash
pip3 install mediapipe
pip3 install numpy==1.24.3
```

## Identify serial number of Realsense Camera

Install the Intel® RealSense™ camera utilities package to easily read the
correct serial number:

```bash
sudo apt install librealsense2-utils
```

Check the Serial number:

```console
$rs-enumerate-devices | grep Serial
 Serial Number                 :     108322074411
 Asic Serial Number            :     108223052439
```

You will use this serial number (and not the ASIC Serial Number) when launching
the demo below.

## Run Demo with Intel® RealSense™ Camera

Execute the following script to launch Follow-Me with Gesture on the Clearpath
Robotics Jackal robot:

<!--hide_directive::::{tab-set}
:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: tab1hide_directive-->

```bash
source /opt/ros/jazzy/setup.bash
ros2 launch tutorial_follow_me_w_gesture jackal_gesture_launch.py <Camera Serial Number>
```

<!--hide_directive:::
:::{tab-item}hide_directive-->  **Humble**
<!--hide_directive:sync: tab2hide_directive-->

```bash
source /opt/ros/humble/setup.bash
ros2 launch tutorial_follow_me_w_gesture jackal_gesture_launch.py <Camera Serial Number>
```

<!--hide_directive:::
::::hide_directive-->

\<Camera Serial Number>: Use the serial number returned when using
`rs-enumerate-devices`. Note that the output of other programs like `lsusb`
might return an incorrect serial number.

After starting the script, the robot should begin searching for trackable
objects in its initial detection radius (defaulting to around 0.5m), and then
following acquired targets as soon as they provide a `thumbs up` to the
Intel® RealSense™ camera and move from the initial target location.

There are reconfigurable parameters in the
`/opt/ros/humble/share/tutorial_follow_me_w_gesture/params`
directory for the Intel® RealSense™ camera (`followme_adbscan_RS_params.yaml`).
You can modify parameters depending on the respective robot, sensor
configuration and environments (if required) before running the tutorial.
Find a brief description of the parameters in the following list:

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
  location = previous location +/- ``tracking_radius``.

## Troubleshooting

- Failed to run the tutorial mentioning permission denied on `/dev/dri/render128`

  ```bash
  usermod -a -G render $USER
  ```

  > **Note**: The machine may need to be restarted after adding the user
  > to a new group.

- Failed to install Deb package: Please make sure to run `sudo apt update`
  before installing the necessary Deb packages.

- You may stop the demo anytime by pressing `ctrl-C`.

- If the robot rotates more than intended at each step, try reducing the
  parameter `max_angular` in the parameter file.

- If the motor controller board does not start, restart the robot.

- For general robot issues, refer to
  [Troubleshooting](../../../robot-tutorials-troubleshooting.rst).
