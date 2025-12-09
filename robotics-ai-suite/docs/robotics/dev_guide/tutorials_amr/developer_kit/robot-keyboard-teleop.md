# Robot Teleop Using a Keyboard

## Prerequisites

Complete the [GSG Robot Get Started guide](../../../gsg_robot/index.rst) before continuing.

## Hardware Prerequisites

You have a robot and a keyboard or an SSH/VNC connection to the robot.

## Example for the AAEON UP Xtreme i11 Robotic Development Kit

1. Connect to your robot via SSH/VNC or direct access. If you choose direct
   access, insert a monitor and a keyboard into the robot's compute system.

2. Set up your system by following the steps in the [Prepare System](../../../gsg_robot/prepare-system.md) guide.

3. Ensure the `ros2-amr-interface` Deb package is installed:

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

4. Open a terminal or establish a new SSH connection to your robot system in order to initiate your control node.

   * Check the device name of the motor controller

     ```bash
     sudo dmesg | grep ttyUSB
     ```

   * The output should contain the ``ch341-uart`` device providing the interface to the motor controller board.

     ```bash
     [1452443.462213] usb 1-9: ch341-uart converter now attached to ttyUSB0
     [1452444.061111] ch341-uart ttyUSB0: ch341-uart converter now disconnected from ttyUSB0
     ```

   * Ensure the AAEON node configuration file has the proper USB device configured as value of  ``port_name``.

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

   * Start the motor control node

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

5. [Only for ROS Jazzy] Install required packages if not yet installed:

   ```bash
   sudo apt-get install ros-jazzy-teleop-twist-keyboard
   ```

6. On another terminal or new SSH connection, start the teleop keyboard:

   <!--hide_directive::::{tab-set}hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   ros2 run teleop_twist_keyboard teleop_twist_keyboard
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive:::{tab-item}hide_directive--> **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   TURTLEBOT3_MODEL=aaeon ros2 run turtlebot3_teleop teleop_keyboard
   ```

   <!--hide_directive:::hide_directive-->
   <!--hide_directive::::hide_directive-->

   When the node starts running, it will display a list of the available keyboard commands to control the robot.
   The available commands depend on the selected robot model.

## Troubleshooting

You can stop the demo anytime by pressing ``ctrl-C``.

For general robot issues, go to: [Troubleshooting Guide](../robot-tutorials-troubleshooting.md).
