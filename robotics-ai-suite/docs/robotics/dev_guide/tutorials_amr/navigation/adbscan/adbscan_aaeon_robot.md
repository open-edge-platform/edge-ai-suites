# ADBSCAN on AAEON Robot Kit

This tutorial describes how to run the ADBSCAN algorithm on the real robot
[UP Xtreme i11 AAEON Robot Kit](https://up-shop.org/up-xtreme-i11-robotic-kit.html) using the Intel® RealSense™ camera input.
During the execution of the program the ADBSCAN algorithm detects objects, and draws them in rviz. Then, the FastMapping algorithm uses data from the ADBSCAN to generate a 2D Map of the environment around.
User can use the default setup to move robot via gamepad or keyboard, so the 3D-camera on the robot can scan surroundings around.

## Prerequisites

- Assemble your robotic kit following the instructions provided by AAEON.
- To control the robot remotely, you may need a Logitech\* F710 gamepad (to be purchased separately).
- Complete the [get started guide](../../../../gsg_robot/index.rst) before continuing.

## Run the ADBSCAN Algorithm Using the AAEON Robot Kit

1. To download and install the tutorial run the command below:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   sudo apt-get install ros-jazzy-aaeon-adbscan-tutorial
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   sudo apt-get install ros-humble-aaeon-adbscan-tutorial
   ```

   <!--hide_directive:::
   ::::hide_directive-->

2. Please perform IMU calibration of the robot, launch script below:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   source /opt/ros/jazzy/setup.bash
   /opt/ros/jazzy/share/ros2_amr_interface/scripts/calibration.sh
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   source /opt/ros/humble/setup.bash
   /opt/ros/humble/share/ros2_amr_interface/scripts/calibration.sh
   ```

   <!--hide_directive:::
   ::::hide_directive-->

3. Place the robot in front of an object and use one of the two methods
   described below to control the robot:

   ![adbscan_aaeon_object_s](../../../../images/adbscan_aaeon_object_s.png)

## Gamepad Robot Control Method

1. If you use joystick, remeber that joystick outputs to /joy_vel and you might have to remap it to cmd_vel.
   You have to either remove ``remappings=[('cmd_vel', '/joy_vel')]`` from ``/opt/ros/$ROS_DISTRO/share/tutorial_aaeon_adbscan/launch/aaeon_adbscan_gamepad_launch.py`` or run ``ros2_interface`` with remap to `joy_vel`.

2. Launch the ADBSCAN AAEON Robot gamepad control program:

   ```bash
   sudo chmod a+rw /dev/input/js0
   sudo chmod a+rw /dev/input/event*
   ```

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   source /opt/ros/jazzy/setup.bash
   ros2 launch tutorial_aaeon_adbscan aaeon_adbscan_gamepad_launch.py
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   source /opt/ros/humble/setup.bash
   ros2 launch tutorial_aaeon_adbscan aaeon_adbscan_gamepad_launch.py
   ```

   <!--hide_directive:::
   ::::hide_directive-->

3. Move the robot around using the gamepad:

   ![gamepad_Logitech_F710_v2](../../../../images/gamepad_Logitech_F710_v2.png)

   - Hold the **RB** button, then press the **Mode** button on the joystick.
   - The green LED near this button should illuminate.
   - Use the **D-pad** to control the robot's movement.

   ![adbscan_aaeon_gamepad_control](../../../../images/adbscan_aaeon_gamepad_control.gif)

## Keyboard Robot Control Method

1. Launch the ADBSCAN AAEON Robot keyboard control program:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   source /opt/ros/jazzy/setup.bash
   ros2 launch tutorial_aaeon_adbscan aaeon_adbscan_keyboard_launch.py
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   source /opt/ros/humble/setup.bash
   ros2 launch tutorial_aaeon_adbscan aaeon_adbscan_keyboard_launch.py
   ```

   <!--hide_directive:::
   ::::hide_directive-->

2. In a separate Terminal window launch keyboard control handler:

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **Jazzy**
   <!--hide_directive:sync: jazzyhide_directive-->

   ```bash
   source /opt/ros/jazzy/setup.bash
   ros2 run teleop_twist_keyboard teleop_twist_keyboard
   ```

   <!--hide_directive:::
   :::{tab-item}hide_directive-->  **Humble**
   <!--hide_directive:sync: humblehide_directive-->

   ```bash
   source /opt/ros/humble/setup.bash
   ros2 run teleop_twist_keyboard teleop_twist_keyboard
   ```

   <!--hide_directive:::
   ::::hide_directive-->

   The robot responds to your keyboard commands in these ways:

   - **i**: Move forward
   - **k**: Stop
   - **,**: Move backward
   - **j**: Turn right
   - **l**: Turn left
   - **q/z**: Increase/decrease max speeds by 10%
   - **w/x**: Increase/decrease only linear speed by 10%
   - **e/c**: Increase/decrease only angular speed by 10%
   - **L** or **J** (only for omnidirectional robots): Strafe (move sideways)
   - anything else: Stop
   - `Ctrl-c`: Quit

3. Move the robot around using the keyboard buttons:

   ![adbscan_aaeon_keyboard_control](../../../../images/adbscan_aaeon_keyboard_control.gif)

   > **Note**: To keep keyboard controls working keep second terminal window above other windows.

   ![adbscan_aaeon_pic4](../../../../images/adbscan_aaeon_pic4.png)

## Expected Results

1. On the server rviz, you will see how ADBSCAN interprets
   the Intel® RealSense™ camera data based on real objects around the robot:

   - Green blocks indicate objects around.

     ![adbscan_aaeon_pic1](../../../../images/adbscan_aaeon_pic1.png)

   - Turn off MarkerArray in rviz to see a 2D Map generated by FastMapping.

     ![adbscan_aaeon_pic2](../../../../images/adbscan_aaeon_pic2.png)

2. Default ADBSCAN view in the rviz window:

   ![adbscan_aaeon_3d_map](../../../../images/adbscan_aaeon_3d_map.gif)

3. Enable FastMapping 2D map view by turning off MakerArray check-box:

   ![adbscan_aaeon_2d_map](../../../../images/adbscan_aaeon_2d_map.gif)

## Troubleshooting

For general robot issues, refer to [Troubleshooting](../robot-tutorials-troubleshooting.md).
