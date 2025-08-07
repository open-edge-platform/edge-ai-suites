

State machine main node
***********************

The Exemplary dynamic use case shows the use case of an Universal robot
UR5e tracking a erratically moving object, optionally picking it up and placing at
customizable location.



Motion Controller Main node Execution
=====================================

The Dynamic use case comes with a set of preconfigured options to achieve the basic
show case. The only mandatory option is ``robot_ip`` which specifies where the real robot
or the UR simulator can be reached.

.. code-block:: bash

    ros2 launch rvc_dynamic_motion_controller_use_case dynamic_demo_launch.py robot_ip:=<robot_ip>

And then press play on the teaching pendant. 


.. _moveit2_servo_pose_tracking:

Motion controller exemplary plugin
===================================

A |moveit2| based motion controller has been implemented showing a dynamic
real-time tracking of the goal set in sendGoal. At all time, sendGoal
can be kept being called with different target, and the motion
controller will do its best to track the goal.

Features
-----------

- Collision maps
- Avoid conveyor belts, or in general any obstacles or sensors like cameras
- Avoid self collisions
- Singularity Avoidance
- Slows down to stop on singularities
- Smoother movements: 
  - Butterworth filtering
  - custom plugin filtering
- Supports Robots controllable in position and/or in velocity


.. _motion_controller_configuration:

Motion Controller Configuration
--------------------------------

For most of these parameters, we refer to the official moveit2 servo
documentation and to .. Moveit2 servo tutorial: https://moveit.picknik.ai/humble/doc/examples/realtime_servo/realtime_servo_tutorial.html

collision_boxes
^^^^^^^^^^^^^^^^^

array of strings with names of the collision boxes

Every entry has to be matched with a new parameter with the same name as
in the array and containing 6 floats in the format
``[posx, posy, posz, dimx, dimy, dimz]``

This collision boxes will be used if the parameter
``moveit_servo.check_collisions`` is set to ``true``, and the collision
checks will be performed at a frequency specified in
``collision_check_rate``


.. code-block:: yaml

   /ipc/StateMachineNode:
     ros__parameters:
       collision_boxes: ["SideConveyorBeltBox", "FrontConveyorBeltBox", "CameraBox"]
       SideConveyorBeltBox:  [0.3, 1.0, 0.09, -0.6, 0.11, 0.20]
       FrontConveyorBeltBox: [1.0, 0.3, 0.09, 0.02, 0.62, 0.04]
       CameraBox: [0.1, 0.1, 0.1, 0.36, 0.66, 0.755]

       moveit_servo:
         angular_tolerance: 0.1
         cartesian_command_in_topic: ~/delta_twist_cmds
         check_collisions: true
         collision_check_rate: 60.0
         command_in_type: speed_units
         command_out_topic: forward_position_controller/commands
         command_out_type: std_msgs/Float64MultiArray
         ee_frame_name: ee_link
         gripper_joint_name: finger_joint
         gripper_move_group_name: robotiq_group
         halt_all_joints_in_cartesian_mode: true
         halt_all_joints_in_joint_mode: true
         hard_stop_singularity_threshold: 200.0
         incoming_command_timeout: 0.1
         is_primary_planning_scene_monitor: true
         joint_command_in_topic: ~/delta_joint_cmds
         joint_limit_margin: 0.1
         joint_topic: joint_states
         leaving_singularity_threshold_multiplier: 2.0
         low_latency_mode: false
         lower_singularity_threshold: 100.0
         monitored_planning_scene_topic: planning_scene
         move_group_name: ur_manipulator
         num_outgoing_halt_msgs_to_publish: 4
         override_velocity_scaling_factor: 1.0
         planning_frame: base_link
         positional_tolerance:
           x: 0.01
           y: 0.01
           z: 0.01
         publish_joint_accelerations: false
         publish_joint_positions: true
         publish_joint_velocities: false
         publish_period: 0.002
         robot_link_command_frame: ee_link
         scale:
           joint: 0.01
           linear: 0.6
           rotational: 0.3
         scene_collision_proximity_threshold: 0.02
         self_collision_proximity_threshold: 0.01
         smoothing_filter_plugin_name: online_signal_smoothing::ButterworthFilterPlugin
         status_topic: status
         use_gazebo: false
         windup_limit: 0.05



.. _waypoint_configuration:

Waypoint configuration
-----------------------

The file waypoint.yaml exposes the waypoint the dynamic and static use cases uses to navigate the robot

.. code-block:: yaml

    /**:
        ros__parameters:
          #                    -x         -y          z          # -y          x         w        -z
            safe_point_pose: [-0.463098, 0.401034, 0.444935, -0.254744, 0.672562, 0.648287, -0.249979]
            drop_point_pose: [-0.340000, 0.540000, 0.248000,-0.1045351, 0.7831495, 0.6033964, -0.1079908]

How to derive this numbers:

|ROS2| is using a different coordinate system than the Univeral Robot teach pendant. To convert 
the two, here is the conversion:



.. image:: /images/html/convertWaypoint.png
    :alt: UR External Control

1. Assure that the drop down ``Feature`` is set to ``base``
2. Assure that the TCP offset takes in account how far the gripper picking position is (in this case our gripper closed fingertips is at 17.5 cm from End effector of UR5e)

.. image:: /images/html/TCPOffset.png
    :alt: UR External Control


3. Convert X Y Z  read in top rightmost box ``Tool Position``
by multiplying x and y by -1 .
4. Convert AxisAngle to quaternion and then swap x and -y, and -z, w. note the signs are changed for y and z.

The results are the pose in the yaml file [-x -y z, -qy, qx, qw, -qz]
