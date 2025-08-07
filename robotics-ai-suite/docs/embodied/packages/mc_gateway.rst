:next_page: None
:prev_page: ../packages

.. _mc_gateway:

Industrial Motion-Control ROS2 Gateway
#########################################

The Industrial Motion-Control ROS2 Gateway is the communication bridge between DDS/RSTP wire-protocol ROS2 implementation and Motion Control (MC) IEC-61131-3 standard Intel implementation. It subscribes velocity commands (commonly from Navigation2 stack) and joint trajectories (commonly from MoveIt2 stack), communicates Real-Time (RT) Domain through Shared Ring Buffer, and gathers the robot's status (AMR's odometry or industrial arm's joint state) and publishes to ROS domain.

.. figure:: assets/images/mc_gateway_arch.png
   :align: center

.. _ros2-2axis-rrbot:

Launch RRBot 2-axis Robotic Arm ROS2 tutorial
***********************************************

This tutorial monitors and controls the RRBot (`Revolute-Revolute Manipulator Robot`), a double inverted pendulum robots-arm, within the ROS2 framework. It demonstrates motion-control concepts through the `ros2_control <https://control.ros.org/humble/index.html>`_ using a simple 3-linkage, 2-joint arm.

.. note:: This demo uses the Shared Memory Ring Buffer Library ``libshmringbuf``, and requires ``root`` permissions to set up the shared memory. As such, ``sudo -i`` will be used to get elevated permissions.

#. Install `ROS2 Desktop <https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html>`_ components, if not already completed.

#. Install PLCopen Motion Control, ROS2 RRBot databus messages with IEC-61131-3 motion-control demo, and ROS2 RRBot MoveIt2 launcher:

   .. code-block:: bash

      $ sudo apt install pciutils plcopen-motion plcopen-servo plcopen-databus libshmringbuf-dev libshmringbuf rt-data-agent ros-humble-controller-manager ros-humble-rrbot-bringup ros-humble-rrbot-moveit-demo

#. Open a terminal and run the PLCopen IEC-61131-3 motion-control driver:

   .. code-block:: bash

      $ isolcpus=$(cat /sys/devices/system/cpu/isolated)
      $ sudo taskset -c ${isolcpus:-1,3} /opt/plcopen/plc_rt_rrbot

   **Note**: By default, ECI isolates CPU cores 1 & 3 (see :doc:`Real-Time Linux <../installation_setup/installation/rt_linux>`).

   **Note**: Replace ``/opt/plcopen/plc_rt_rrbot`` with ``/opt/plcopen/plc_rt_rrbot_igh -n <path_to_ethercat_eni_file>`` to run this demo using two IEC-61158 EtherCAT servo-controlled joint.

#. Open a second terminal with elevated permissions:

   .. code-block:: bash

      $ sudo -i

#. In the second terminal, set up the ROS2 environment and run the RRBot ROS2 demo:

   .. code-block:: bash

      $ source /opt/ros/humble/setup.bash
      $ export ROS_DOMAIN_ID=31
      $ ros2 launch rrbot_bringup rrbot_moveit_demo.launch.py

   **Expected Result:**

   MoveIt2 starts correctly without exiting.

   .. figure:: assets/images/rrbot-rviz.png

   **Note**: The command is correctly executed if no “Error” messages are printed (some warnings might be printed due to missing data). The following is a sample result: 

   .. code-block:: console

      [INFO] [launch]: All log files can be found below /root/.ros/log/2022-03-09-18-35-23-491029-2c3d06ed879c-62
      [INFO] [launch]: Default logging verbosity is set to INFO
      [INFO] [robot_state_publisher-1]: process started with pid [64]
      [INFO] [rviz2-2]: process started with pid [66]
      [INFO] [run_moveit_cpp-3]: process started with pid [68]
      [INFO] [ros2_control_node-4]: process started with pid [79]
      [INFO] [ros2 run controller_manager spawner.py joint_trajectory_controller-5]: process started with pid [82]
      [INFO] [ros2 run controller_manager spawner.py joint_state_broadcaster-6]: process started with pid [85]
      [robot_state_publisher-1] Parsing robot urdf xml string.
      [robot_state_publisher-1] Link base_link had 1 children
      [robot_state_publisher-1] Link link1 had 1 children
      [robot_state_publisher-1] Link link2 had 3 children
      [robot_state_publisher-1] Link camera_link had 1 children
      [robot_state_publisher-1] Link camera_link_optical had 0 children
      [robot_state_publisher-1] Link hokuyo_link had 0 children
      [robot_state_publisher-1] Link tool_link had 0 children
      ……
      [run_moveit_cpp-3] [INFO] [1646850933.957900579] [moveit_cpp_demo]: arm.execute()
      [run_moveit_cpp-3] [INFO] [1646850933.958014839] [moveit_ros.trajectory_execution_manager]: Validating trajectory with allowed_start_tolerance 0.01
      [run_moveit_cpp-3] [INFO] [1646850933.961465153] [moveit_ros.trajectory_execution_manager]: Starting trajectory execution ...
      [run_moveit_cpp-3] [INFO] [1646850933.961516544] [moveit.simple_controller_manager.follow_joint_trajectory_controller_handle]: sending trajectory to joint_trajectory_controller
      [ros2_control_node-4] [INFO] [1646850933.961809177] [joint_trajectory_controller]: Received new action goal
      [ros2_control_node-4] [INFO] [1646850933.961854996] [joint_trajectory_controller]: Accepted new action goal
      [run_moveit_cpp-3] [INFO] [1646850933.972377391] [moveit.simple_controller_manager.follow_joint_trajectory_controller_handle]: joint_trajectory_controller started execution
      [run_moveit_cpp-3] [INFO] [1646850933.972410502] [moveit.simple_controller_manager.follow_joint_trajectory_controller_handle]: Goal request accepted!
      [ros2_control_node-4] [INFO] [1646850936.278047163] [joint_trajectory_controller]: Goal reached, success!
      [run_moveit_cpp-3] [INFO] [1646850936.279264357] [moveit.simple_controller_manager.follow_joint_trajectory_controller_handle]: Controller joint_trajectory_controller successfully finished
      [run_moveit_cpp-3] [INFO] [1646850936.308323717] [moveit_ros.trajectory_execution_manager]: Completed trajectory execution with status SUCCEEDED ...


.. _ros2-6axis-hiwin:

Launch HIWIN 6-axis Robotic Arm ROS2 tutorial
**********************************************

This demo allows you to monitor and control the `HIWIN industrial robots <https://hiwin.com/products/industrial-robotics/#IndustrialRobots>`_ within the ROS2 framework:

.. note:: 

   The HIWIN robot controller's HRSS software must be be updated to at least version 3.2.16

   This demo uses the Shared Memory Ring Buffer Library ``libshmringbuf``, and requires ``root`` permissions to set up the shared memory. As such, ``sudo -i`` will be used to get elevated permissions.

#. Install `ROS2 Desktop <https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html>`_ components, if not already completed.

#. Install PLCopen Motion Control, ROS2 HIWIN databus messages with IEC-61131-3 motion-control demo, and ROS2 HIWIN MoveIt2 launcher:

   .. code-block:: bash

      $ sudo apt install pciutils plcopen-motion plcopen-servo plcopen-databus libshmringbuf-dev libshmringbuf
      $ sudo apt install ros-humble-run-hiwin-plc 
      $ sudo apt install ros-humble-run-hiwin-moveit

#. Open a terminal and run the Robot-ARM PLCopen IEC-61131-3 motion-control driver:

   .. code-block:: bash

      $ isolcpus=$(cat /sys/devices/system/cpu/isolated)
      $ sudo taskset -c ${isolcpus:-1,3} /opt/plcopen/plc_rt_robot_arm_rtmotion

   **Note**: By default, ECI isolates CPU cores 1 & 3 (see :doc:`Real-Time Linux <../installation_setup/installation/rt_linux>`).

#. Open a second terminal with elevated permissions:

   .. code-block:: bash

      $ sudo -i

#. In the second terminal, set up the ROS2 environment and run the ROS2 HIWIN databus messages with IEC-61131-3 motion-control demo:

   .. code-block:: bash

      $ source /opt/ros/humble/setup.bash
      $ export ROS_DOMAIN_ID=31
      $ ros2 run run_hiwin_plc run_hiwin_plc

#. Open a third terminal with elevated permissions:

   .. code-block:: bash

      $ sudo -i

#. In the third terminal, set up the ROS2 environment and run the ROS2 HIWIN MoveIt2 launch file:

   .. code-block:: bash

      $ source /opt/ros/humble/setup.bash
      $ export ROS_DOMAIN_ID=31
      $ ros2 launch run_hiwin_plc run_hiwin_plc.launch.py

   The demo begins by computing a simple motion plan which is visualized via a transparent RobotState display. This step alone involves a large number of components, such as IK, collision checking, planning scene, robot model, OMPL planning plugin and planner adapters. Immediately after, the trajectory is executed on the HIWIN `ros2_control` hardware interface.

   **Expected Result:**

   MoveIt2 and other ROS2 nodes start correctly without errors if RViz GUI is active and shows a robot arm moving periodically.

   .. figure:: assets/images/hiwin-rviz.png

   .. tip:: 
         
         If no messages are displayed on the third terminal, verify that the environment variable ``ROS_DOMAIN_ID`` has been properly set to the same value in both terminal environments.

   **Note**: The command is correctly executed if no “Error” messages are printed (some warnings might be printed due to missing data). The following is a sample result: 

   .. code-block:: console

      [INFO] [launch]: All log files can be found below /home/root/.ros/log/2020-12-01-06-23-24-352240-ecs-intel-4273-3533
      [INFO] [launch]: Default logging verbosity is set to INFO
      /usr/share/hiwin_robot_moveit_config/xacros/hiwin_robot_and_gripper.urdf
      /usr/share/hiwin_robot_moveit_config/srdf/hiwin_robot.srdf
      /usr/share/hiwin_robot_moveit_config/config/kinematics.yaml
      /usr/share/run_hiwin_plc/launch/run_hiwin_plc.launch.py:25: YAMLLoadWarning: calling yaml.load() without Loader=... is deprecated, as the default Loader is unsafe. Please read https://msg.pyyaml.org/load for full details.
        return yaml.load(file)
      /usr/share/run_hiwin_moveit/config/controllers.yaml
      /usr/share/hiwin_robot_moveit_config/config/ompl_planning.yaml
      [INFO] [robot_state_publisher-1]: process started with pid [3535]
      [INFO] [static_transform_publisher-2]: process started with pid [3537]
      [INFO] [run_hiwin_moveit-3]: process started with pid [3539]
      ……
      [run_hiwin_moveit-3] [INFO] [1606803829.707921557] [moveit_cpp_demo]: Trajectory status: 1
      [run_hiwin_moveit-3] [INFO] [1606803831.708016640] [moveit_cpp_demo]: Set goal 2
      [run_hiwin_moveit-3] [INFO] [1606803831.708051094] [moveit_cpp_demo]: Plan to goal
      [run_hiwin_moveit-3] [INFO] [1606803831.708563914] [moveit.ompl_planning.model_based_planning_context]: Planner configuration 'manipulator' will use planner 'geometric::RRTConnect'. Additional configuration parameters will be set when the planner is constructed.
      [run_hiwin_moveit-3] [INFO] [1606803831.723452924] [ompl]: /usr/src/debug/ompl/1.5.0-1-r0/git/src/ompl/geometric/planners/rrt/src/RRTConnect.cpp:354 - manipulator/manipulator: Created 5 states (2 start + 3 goal)
      [run_hiwin_moveit-3] [INFO] [1606803831.723565262] [ompl]: /usr/src/debug/ompl/1.5.0-1-r0/git/src/ompl/tools/multiplan/src/ParallelPlan.cpp:135 - ParallelPlan::solve(): Solution found by one or more threads in 0.000756 seconds
      [run_hiwin_moveit-3] [INFO] [1606803831.726168559] [ompl]: /usr/src/debug/ompl/1.5.0-1-r0/git/src/ompl/geometric/src/SimpleSetup.cpp:179 - SimpleSetup: Path simplification took 0.002559 seconds and changed from 3 to 2 states
      [run_hiwin_moveit-3] [INFO] [1606803831.728662079] [moveit_cpp_demo]: Sending the trajectory for execution

.. _ros2-agvm:

Launch AGV ROS2 tutorial
*****************************

This tutorial allows monitors and controls an AGV (Automated Guided Vehicle) using the EtherCAT wired-protocol control on four Mecanum wheel-drive chassis within the ROS2 framework. `YDLidar Communication Protocol for ROS2 <https://github.com/YDLIDAR/YDLidar-SDK/blob/master/doc/YDLidar-SDK-Communication-Protocol.md>`_ is used for ``ydlidar`` devices to configure LiDAR in the ROS2 environment. 

.. note:: This demo uses the Shared Memory Ring Buffer Library ``libshmringbuf``, and requires ``root`` permissions to set up the shared memory. As such, ``sudo -i`` will be used to get elevated permissions.
   
#. Install `ROS2 Desktop <https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html>`_ components, if not already completed.

#. Install PLCopen Motion Control and the ROS2 AGVM databus messages with IEC-61131-3 motion-control demo: 

   .. code-block:: bash

      $ sudo apt install pciutils plcopen-motion plcopen-servo plcopen-databus libshmringbuf-dev libshmringbuf
      $ sudo apt install ros-humble-agvm

#. Run the Robot-ARM PLCopen IEC-61131-3 motion-control driver:

   .. code-block:: bash

      $ isolcpus=$(cat /sys/devices/system/cpu/isolated)
      $ sudo taskset -c ${isolcpus:-1,3} /opt/plcopen/plc_rt_amr_rtmotion

   **Note**: By default, ECI isolates CPU cores 1 & 3 (13th generation processors and older) or 2 & 4 (14th generation processors and newer) (see :doc:`Real-Time Linux <../installation_setup/installation/rt_linux>`).

   **Note**: ``/opt/plcopen/plc_rt_amr_rtmotion_symg`` is a sample application using EtherCAT to control the Mecanum Wheel Platform.

#. Open a second terminal with elevated permissions:

   .. code-block:: bash

      $ sudo -i

#. In the second terminal, set up the ROS2 environment and run the ROS2 AGVM databus messages with IEC-61131-3 motion-control demo:

   .. code-block:: bash

      $ source /opt/ros/humble/setup.bash
      $ export ROS_DOMAIN_ID=31
      $ ros2 launch agvm agvm_base.launch.py

   **Expected Result:**

   ROS2 nodes start correctly, without exiting.

   **Note**: Since the joystick is disconnected, it is normal to see the error ``[ERROR] [1657850097.527093048] [agvm_joystick_node]: Cannot open /dev/input/js0 -1!``.

   **Note**: The command is correctly executed if no “Error” messages are printed (some warnings might be printed due to missing data). The following is a sample result: 

   .. code-block:: console

      [INFO] [launch]: All log files can be found below /root/.ros/log/2022-07-15-01-54-57-311770-d2d206ef9a2c-117
      [INFO] [launch]: Default logging verbosity is set to INFO
      [INFO] [robot_state_publisher-1]: process started with pid [119]
      [INFO] [joint_state_publisher-2]: process started with pid [121]
      [INFO] [agvm_plcshm_node-3]: process started with pid [123]
      [INFO] [agvm_joystick_node-4]: process started with pid [125]
      [INFO] [ydlidar_node-5]: process started with pid [127]
      [robot_state_publisher-1] Parsing robot urdf xml string.
      [robot_state_publisher-1] Link base_link had 1 children
      [robot_state_publisher-1] Link base_scan had 0 children
      ……
      [agvm_plcshm_node-3] [INFO] [1657850097.490716583] [agvm_plcshm_node]: AgvmPlcShmNode initial complete.
      [agvm_plcshm_node-3] [INFO] [1657850097.500794279] [agvm_plcshm_node]: AGV cmd: 0.000000 0.000000 0.000000
      [agvm_plcshm_node-3] [INFO] [1657850097.500855464] [agvm_plcshm_node]: AGV pose: 0.000000 0.000000 345.860687
      [agvm_plcshm_node-3] [INFO] [1657850097.500876573] [agvm_plcshm_node]: AGV vel: 0.000000 0.000000 345860.687500
      [agvm_plcshm_node-3] [INFO] [1657850097.500895089] [agvm_plcshm_node]: AGV mOdom: 0.000000 0.000000 34586.068726
      [agvm_plcshm_node-3]

#. Open a third terminal with elevated permissions:

   .. code-block:: bash

      $ sudo -i

#. In the third terminal, set up the ROS2 environment and run the following command:

   .. code-block:: bash

      $ source /opt/ros/humble/setup.bash
      $ export ROS_DOMAIN_ID=31
      $ ros2 topic pub -1 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: -0.1}, angular: {z: -0.1}}"

   **Note**: ``linear: {x: -0.1}`` is the linear velocity(m/s) for AMR. ``angular: {x: -0.1}`` is the angular velocity(rad/s) for AMR.

   **Expected Result:**

   Variables ``AGV cmd/pose/vel/mOdom`` in the second terminal console will be refreshed.

