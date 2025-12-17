# Create Your Own Robot Kit

This tutorial guides guides you through creating an autonomous mobile robot capable of
exploring and mapping an area. It involves adding an Intel® compute system, placing a
Intel® RealSense™ camera on top of any robot base, and using the Autonomous Mobile Robot software.

Use the [robot-keyboard-teleop](./robot-keyboard-teleop.md) ROS 2 node to validate that the robot kit's hardware
setup has been done correctly.

## Requirements

### Hardware Requirements

The robot base should contain:

- Intel® compute system with Autonomous Mobile Robot installed

- Intel® RealSense™ camera

- Robot base support (chassis) for the Intel® compute system and the
  Intel® RealSense™ camera

- Wheels

- Motor

- Motor controller

- Batteries for all components

### Software Requirements

The robot base should feature a ROS 2 node with the ability to:

- Publish information from the motor controller firmware into ROS 2 topics
  like wheel odometry.

- Receive information from other ROS 2 nodes and transmit this data to the
  motor controller firmware. For example, it should be capable of receiving movement commands from
  ROS 2 Navigation 2 stack on the cmd_vel topic.

- Provide robot specific information like the tf tree data with correct tf
  transformations. For example, ``odom`` and ``base_link`` and their
  transformations.

- When using multiple robots, the ability to change these names for
  each robot like ``robot1_odom`` and ``robot1_base_link`` (more information
  can be found `here
  <https://navigation.ros.org/setup_guides/transformation/setup_transforms.html>`__).

> **Note**: This ROS 2 node runs on the compute system and retrieving information from the
> motor robot's controller via a wired connection, usually a USB connection.

## Steps To Create Your Own Robot Kit

### Step 1: Prerequisites

To create a functional autonomous mobile robot, follow the instructions of the manufacturer.

The standard assembly involves the following steps:

1. Mount the motors onto the lower chassis board and then assemble the wheels.
2. Fix the motor controller on the chassis board and establish connections with the motors.
3. Attach the Intel® RealSense™ camera and the SSD drive to the upper chassis board.
4. Mount the Intel® compute system to the the upper chassis board.
5. Connect the two chassis boards.
6. Establish a connection between the Intel® compute system and both Intel® RealSense™ camera and motor controller via USB.
7. Connect both the the Intel® compute system and the motor controller to a power source.
8. Power the Intel® compute system using a power source.

### Step 2: Integration into Autonomous Mobile Robot

Start the robot base ROS 2 node on the native system OS or inside a Docker
container.
To ensure proper functionality, ensure that both the robot base node and the rest of
the Autonomous Mobile Robot pipeline are configured with the same ROS_DOMAIN_ID.

### Step 3: Robot Base Node ROS 2 Node

#### Introduction to Robotic Base Node

The Autonomous Mobile Robot pipeline assumes that the robot base ROS 2 node:

- Publishes ``odom`` and ``base_link``

  - ``odom`` is used by the Navigation 2 package and others to get information
    from sensors, especially the wheel encoders. For more information refer to `Navigation 2
    tutorial on Odometry
    <https://navigation.ros.org/setup_guides/odom/setup_odom.html>`__.

  - ``base_link`` represents the center of the robot to which all other links
    are connected.

- Creates the transform between ``odom`` and ``base_link``

- Is subscribed to ``cmd_vel`` which is used by the Navigation 2 package to
  give instructions to the robot like spin in place or move forward

The Autonomous Mobile Robot provides the following examples within Deb packages:

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
<!--hide_directive:sync: jazzyhide_directive-->

In ``ros-jazzy-aaeon-ros2-amr-interface`` Deb package:

- `/opt/ros/jazzy/share/ros2_amr_interface/params/aaeon_node_params_uncalibrated_imu.yaml`
- `/opt/ros/jazzy/share/ros2_amr_interface/params/aaeon_node_params.yaml`

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Humble**
<!--hide_directive:sync: humblehide_directive-->

In ``ros-humble-aaeon-ros2-amr-interface`` Deb package:

- `/opt/ros/humble/share/ros2_amr_interface/params/aaeon_node_params_uncalibrated_imu.yaml`
- `/opt/ros/humble/share/ros2_amr_interface/params/aaeon_node_params.yaml`

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

These samples are for the `AAEON UP Xtreme* i11 Robotic Development Kit <https://up-shop.org/up-xtreme-i11-robotic-kit.html>`__.

#### Robotic Base Node Deep Dive

This section details the commands required to startup the motor controller of an AAEON UP Xtreme i11 Robotic Development Kit.

To start the node on the AAEON UP Xtreme i11 Robotic Development Kit, you can reference and initiate it as follows:

- Ensure that the `ROS2 AMR Interface` Deb package is installed:

  <!--hide_directive::::{tab-set}hide_directive-->
  <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
  <!--hide_directive:sync: jazzyhide_directive-->

  ```bash
  sudo apt update
  sudo apt install ros-jazzy-aaeon-ros2-amr-interface
  ```

  <!--hide_directive:::hide_directive-->
  <!--hide_directive:::{tab-item}hide_directive--> **Humble**
  <!--hide_directive:sync: humblehide_directive-->

  ```bash
  sudo apt update
  sudo apt install ros-humble-aaeon-ros2-amr-interface
  ```

  <!--hide_directive:::hide_directive-->
  <!--hide_directive::::hide_directive-->

- Check the device name of the motor controller.

  ```bash
  sudo dmesg | grep ttyUSB
  ```

- The output should contain the ``ch341-uart`` device providing the interface to the motor controller board.

  ```bash
  [1452443.462213] usb 1-9: ch341-uart converter now attached to ttyUSB0
  [1452444.061111] ch341-uart ttyUSB0: ch341-uart converter now disconnected from ttyUSB0
  ```

- Ensure the AAEON UP Xtreme i11 Robotic Development Kit node configuration file has the proper USB device configured as value of  ``port_name``.

  <!--hide_directive::::{tab-set}hide_directive-->
  <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
  <!--hide_directive:sync: jazzyhide_directive-->

  ```bash
  vi /opt/ros/jazzy/share/ros2_amr_interface/params/aaeon_node_params.yaml
  ```

  <!--hide_directive:::hide_directive-->
  <!--hide_directive:::{tab-item}hide_directive--> **Humble**
  <!--hide_directive:sync: humblehide_directive-->

  ```bash
  vi /opt/ros/humble/share/ros2_amr_interface/params/aaeon_node_params.yaml
  ```

  <!--hide_directive:::hide_directive-->
  <!--hide_directive::::hide_directive-->

- Modify permissions to grant access for a user to USB device and run ROS2 commands without sudo privileges. Make sure to use proper ``ttyUSB`` device.

  ```bash
  sudo chown $(whoami):$(id -gn) /dev/<ttyUSB> # e.g., /dev/ttyUSB0
  sudo chmod a+rw /dev/<ttyUSB>
  ```

- Start the motor control node.

  <!--hide_directive::::{tab-set}hide_directive-->
  <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
  <!--hide_directive:sync: jazzyhide_directive-->

  ```bash
  AAEON_NODE_CONFIG_FILE=/opt/ros/jazzy/share/ros2_amr_interface/params/aaeon_node_params.yaml

  # Launch the AAEON Robot Motor Board Interface
  ros2 run ros2_amr_interface amr_interface_node --ros-args \
     --params-file $AAEON_NODE_CONFIG_FILE \
     --remap /amr/cmd_vel:=/cmd_vel \
     --remap /amr/battery:=/sensors/battery_state
  ```

  <!--hide_directive:::hide_directive-->
  <!--hide_directive:::{tab-item}hide_directive--> **Humble**
  <!--hide_directive:sync: humblehide_directive-->

  ```bash
  AAEON_NODE_CONFIG_FILE=/opt/ros/humble/share/ros2_amr_interface/params/aaeon_node_params.yaml

  # Launch the AAEON Robot Motor Board Interface
  ros2 run ros2_amr_interface amr_interface_node --ros-args \
     --params-file $AAEON_NODE_CONFIG_FILE \
     --remap /amr/cmd_vel:=/cmd_vel \
     --remap /amr/battery:=/sensors/battery_state
  ```

  <!--hide_directive:::hide_directive-->
  <!--hide_directive::::hide_directive-->

You can check the following:

- ROS 2 topics

  ```bash
  ros2 topic list
  # The result for UP Xtreme i11 Robotic Kit is similar to:
  # /amr/cmd_vel
  # /amr/imu/raw
  # /amr/initial_pose
  # /amr/odometry
  # /parameter_events
  # /rosout
  # /sensors/battery_state
  # /tf
  # The result for the Pengo robot contains multiple topics but the crucial to this pipeline are:
  # /cmd_vel
  # /joint_states
  # /rosout
  # /odom
  # /parameter_events
  # /tf
  ```

- ``odom`` and ``base_link`` frames

  ```bash
  ros2 run tf2_tools view_frames.py
  cp frames.pdf /home/<user>
  # Open the pdf through file explorer, it should look similar to:
  ```

  ![frames](../../../images/frames.png)

### Step 4: Robot Base Node ROS 2 Navigation Parameter File

#### Introduction to the ROS 2 Navigation Parameter File

The Autonomous Mobile Robot pipeline for AMRs uses the
[Navigation 2 package](https://navigation.ros.org) from ROS 2. Setting parameters specific to the
robot and the mapping area is essential for the Navigation 2 packages to function properly.

#### Robot Navigation Parameter File

To help understand the options in this parameter file, see ROS 2
[Navigation 2 Packages Configuration Guide](https://navigation.ros.org/configuration/index.html).

With numerous parameters to configure, Intel® recommends referring to
Navigation 2 documentation for a comprehensive understanding of the setup.

The most important parameters to set are:

- ``use_sim_time``:

  Ignore all differences. It is used in simulations. Set it to False when
  running in a real environment.

- ``base_frame_id``: robot frame ID being published by the robot base node.

  The default is ``base_footprint``, but ``base_link`` is another option. Use
  the one you choose to publish in the robot base node.

- ``robot_model_type``: robot type

  The options are omnidirectional, differential, or a custom motion model that
  you provide.

- ``tf_broadcast``: turns transform broadcast on or off.

  Set this to False to prevent amcl from publishing the transform between the
  global frame and the odometry frame.

- ``odom_topic``: source of instantaneous speed measurement.

- ``max_vel_x, max_vel_theta``: maximum speed on the X axis or angular (theta).

- ``robot_radius``: radius of the robot.

- ``inflation_radius``: radius to inflate costmap around lethal obstacles.

- ``min_obstacle_height``: minimum height to add return to occupancy grid.

- ``max_obstacle_height``: maximum height to add return to occupancy grid.

- ``obstacle_range``: determines the maximum range sensor reading that results
  in an obstacle being put into the costmap.

- ``max_rotational_vel, min_rotational_vel, rotational_acc_lim``: configure the
  rotational velocity allowed for the base in radians/second.

### Step 5: Navigation Full Stack

#### Introduction to the Navigation Full Stack

The Autonomous Mobile Robot navigation full stack contains numerous components designed to assist the robot in navigation, obstacle avoidance, and mapping an area. For example:

- Intel® RealSense™ Camera Node: receives input from the camera and publishes topics used by
  the vSLAM algorithm.

- Robot Base Node: receives input from the motor controller (for example, from
  wheel encoders) and sends commands to the motor controller to move the robot.

- ``ros-base-camera-tf``: Uses ``static_transform_publisher`` to create
  transforms between ``base_link`` and ``camera_link``.

- ``static_transform_publisher`` publishes a static coordinate transform to tf
  using an x/y/z offset in meters and yaw/pitch/roll in radians. The period, in
  milliseconds, specifies how often to send a transform.

  - yaw = rotation on the x axis.

  - pitch = rotation on the y axis.

  - roll = rotation on the z axis.

- ``collab-slam``: `A Collaborative Visual SLAM Framework for Service
  Robots paper <https://arxiv.org/abs/2102.03228>`__.

- FastMapping: It is an algorithm to create a 3D voxelmap of a robot's surroundings,
  based on Intel® RealSense™ camera's depth sensor data and provide the 2D map needed by the Navigation 2 stack.

- ``nav2``: the navigation package.

- Wandering Application: demonstrates the integration of middleware, algorithms, and the
  ROS 2 navigation stack to navigate a robot within an unknown environment without hitting
  obstacles.

#### Create a Parameter File for Your Robotic Kit

The [wandering-aaeon-tutorial](../../../dev_guide/tutorials_amr/navigation/wandering_app/wandering-aaeon-tutorial.md) tutorial provides a parameter file for the AAEON UP Xtreme i11 Robotic Development Kit, that file can be used as a template to create a parameter file for your robotic kit.

- First install the tutorial.

  <!--hide_directive::::{tab-set}hide_directive-->
  <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
  <!--hide_directive:sync: jazzyhide_directive-->

  ```bash
  sudo apt update
  sudo apt install ros-jazzy-wandering-aaeon-tutorial
  ```

  <!--hide_directive:::hide_directive-->
  <!--hide_directive:::{tab-item}hide_directive--> **Humble**
  <!--hide_directive:sync: humblehide_directive-->

  ```bash
  sudo apt update
  sudo apt install ros-humble-wandering-aaeon-tutorial
  ```

  <!--hide_directive:::hide_directive-->
  <!--hide_directive::::hide_directive-->

- Use the AAEON UP Xtreme i11 Robotic Development Kit navigation parameter file as a template, make a copy of it, and adapt the content to match your robot.

  <!--hide_directive::::{tab-set}hide_directive-->
  <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
  <!--hide_directive:sync: jazzyhide_directive-->

  ```bash
  # Replace <your_robot>_robot_nav to a name that makes sense to your robotic kit.
  cp /opt/ros/jazzy/share/wandering_aaeon_tutorial/params/aaeon_nav.param.yaml /opt/ros/jazzy/share/wandering_aaeon_tutorial/params/<your_robot>_nav.param.yaml
  ```

  <!--hide_directive:::hide_directive-->
  <!--hide_directive:::{tab-item}hide_directive--> **Humble**
  <!--hide_directive:sync: humblehide_directive-->

  ```bash
  # Replace <your_robot>_robot_nav to a name that makes sense to your robotic kit.
  cp /opt/ros/humble/share/wandering_aaeon_tutorial/params/aaeon_nav.param.yaml /opt/ros/humble/share/wandering_aaeon_tutorial/params/<your_robot>_nav.param.yaml
  ```

  <!--hide_directive:::hide_directive-->
  <!--hide_directive::::hide_directive-->

- Make all of the changes that are specific to your robotic kit:

  <!--hide_directive::::{tab-set}hide_directive-->
  <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
  <!--hide_directive:sync: jazzyhide_directive-->

  ```bash
  vi /opt/ros/jazzy/share/wandering_aaeon_tutorial/params/<your_robot>_nav.param.yaml
  ```

  <!--hide_directive:::hide_directive-->
  <!--hide_directive:::{tab-item}hide_directive--> **Humble**
  <!--hide_directive:sync: humblehide_directive-->

  ```bash
  vi /opt/ros/humble/share/wandering_aaeon_tutorial/params/<your_robot>_nav.param.yaml
  ```

  <!--hide_directive:::hide_directive-->
  <!--hide_directive::::hide_directive-->

1. Replace the ``aaeon-amr-interface`` target with the generic robot node you created in
   [Step 3](#step-3-robot-base-node-ros-2-node).

2. In the ROS 2 command file, change the Navigation 2 target so that
   ``params_file`` targets the parameter file you created in
   [Step 4](#step-4-robot-base-node-ros-2-navigation-parameter-file).

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   from: ``params_file:=/opt/ros/jazzy/share/ros2_amr_interface/params/<your_robot>_node_params.yaml``

   to: ``params_file:=/opt/ros/jazzy/share/wandering_aaeon_tutorial/params/<your_robot>_nav.param.yaml``

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   from: ``params_file:=/opt/ros/humble/share/ros2_amr_interface/params/<your_robot>_node_params.yaml``

   to: ``params_file:=/opt/ros/humble/share/wandering_aaeon_tutorial/params/<your_robot>_nav.param.yaml``

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

3. In the ``ros-base-camera-tf`` target, change the transform values from
   ``static_transform_publisher``. The values for x, y, and z depend on where
   your Intel® RealSense™ camera is set.

#### Start Mapping an Area with Your Robot

1. Place the robot in an area with multiple objects around it.

2. Check that Autonomous Mobile Robot environment is set:

   Run the following script to create a map by using the
   [wandering-aaeon-tutorial](../../../dev_guide/tutorials_amr/navigation/wandering_app/wandering-aaeon-tutorial.md).

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   source /opt/ros/jazzy/setup.bash
   export ROS_DOMAIN_ID=<value>
   /opt/ros/humble/share/wandering_aaeon_tutorial/scripts/wandering_aaeon.sh
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   source /opt/ros/humble/setup.bash
   export ROS_DOMAIN_ID=<value>
   /opt/ros/humble/share/wandering_aaeon_tutorial/scripts/wandering_aaeon.sh
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

3. Follow the [wandering-aaeon-tutorial](../../../dev_guide/tutorials_amr/navigation/wandering_app/wandering-aaeon-tutorial.md).

#### Troubleshooting

You can stop the demo anytime by pressing ``ctrl-C``.

For general robot issues, refer to [Troubleshooting](../robot-tutorials-troubleshooting.md).
