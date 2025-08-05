.. _teleop-keyboard:

Robot Teleop Using a Keyboard
=====================================================

Hardware Prerequisites
------------------------

You have a robot and a keyboard or an SSH/VNC connection to the robot.

Example for the |up_xtreme|
------------------------------------------

#. Connect to your robot via SSH/VNC or direct access. If you choose direct
   access, insert a monitor and a keyboard into the robot's compute system.

#. Set up your system by following the steps in :doc:`../../../gsg_robot/prepare-system`.

#. Ensure the ``ros-humble-aaeon-ros2-amr-interface`` |deb_pack| is installed.

   .. code-block:: bash

      sudo apt update
      sudo apt install ros-humble-aaeon-ros2-amr-interface

#. Open a terminal or establish a new SSH connection to your robot system in order to initiate your control node.

   * Check the device name of the motor controller

     .. code-block:: bash

        sudo dmesg | grep ttyUSB

   * The output should contain the ``ch341-uart`` device providing the interface to the motor controller board.

     .. code-block:: bash

        [1452443.462213] usb 1-9: ch341-uart converter now attached to ttyUSB0
        [1452444.061111] ch341-uart ttyUSB0: ch341-uart converter now disconnected from ttyUSB0

   * Ensure the AAEON node configuration file has the proper USB device configured as value of  ``port_name``.

     .. code-block:: bash

        vi /opt/ros/humble/share/ros2_amr_interface/params/aaeon_node_params.yaml

   * Start the motor control node

     .. code-block:: bash

        AAEON_NODE_CONFIG_FILE=/opt/ros/humble/share/ros2_amr_interface/params/aaeon_node_params.yaml

        # Launch the AAEON Robot Motor Board Interface
        ros2 run ros2_amr_interface amr_interface_node --ros-args \
           --params-file $AAEON_NODE_CONFIG_FILE \
           --remap /amr/cmd_vel:=/cmd_vel \
           --remap /amr/battery:=/sensors/battery_state

#. On another terminal or new SSH connection, start the teleop keyboard:

   .. code-block:: bash

      TURTLEBOT3_MODEL=aaeon ros2 run turtlebot3_teleop teleop_keyboard

   When the node starts running, it will display a list of the available keyboard commands to control the robot.
   The available commands depend on the selected robot model.

Troubleshooting
----------------

You can stop the demo anytime by pressing ``ctrl-C``.

For general robot issues, go to: :doc:`../robot-tutorials-troubleshooting`.
