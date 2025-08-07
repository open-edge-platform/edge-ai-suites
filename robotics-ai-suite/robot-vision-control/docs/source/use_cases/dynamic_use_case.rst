.. _dynamic_use_case:

Exemplary Dynamic Use case
##############################

.. toctree::
   :maxdepth: 1
   
   dynamic_use_case/system_config
   dynamic_use_case/visualization
   dynamic_use_case/state_machine_node
   dynamic_use_case/vision_main_node



This exemplary use case shows how the robot actively tracks a group of objects 
in real-time as they unpredictably navigate through three-dimensional space. 
Subsequently, the robot picks up these objects and accurately places them at their 
designated destination.


.. note:: 

    Every component has an option to change the default namespace:
    ``namespace:=<namspace>`` which by default is "ipc".
    
    If specified, the components will only see other components if they have same namespaces.

    Moreover, some components require additional configuration depending on this name, more specifically 
    the existence of a config file ``d415camera<namespace>.xacro``. in ``<installdir>/rvc_dynamic_motion_controller_use_case/cameraurdf/`` directory


.. note:: 

    After following at least once :ref:`Preliminary system configuration<preliminary_system_configuration>` guide, i.e.: calibrating camera and robot,
    Then the quick start guide to start RVC is to execute in three different terminals:

    .. code-block:: bash

        ros2 launch rvc_dynamic_motion_controller_use_case rviz2_launch.py
        ros2 launch rvc_vision_main vision.composition.launch.py
        ros2 launch rvc_dynamic_motion_controller_use_case dynamic_demo_launch.py robot_ip:=<robot_ip>

    Then press play on the |UR5e| teach pendant

    If Dobby planner plugin is intended to be used, after running the above, in three different terminals, run the followings:

    .. code-block:: bash

        ros2 launch hrc_perception_ros dobby_launch.py

    To put ground floor run:

    .. code-block:: bash

        python3 src/dobby_planner/applications.robotics.manipulation.perception-ros/scripts/dobby_service_test_floor.py

    Once all the nodes are running and the robot is ready, run the following service to enable the dobby planner:

    .. code-block:: bash

        ros2 service call /ipc/hrc_perception_ros/start_follow_service_service std_srvs/srv/Empty {}

checklist_robot.png
convertWaypoint.png
homeposition.png
RobotBackground.png
robotic-arm-graphic.png
RVCControl.png
RVC.png
RVCVisionHighLevel.png
RvizDynamicUseCase1.png
sethomeposition.png
setremotecontrol.png
TCPOffset.png
tftree.svg
URCreateProgram.png
URExternalControl.png
URRobotiqGripper.png
YoloDetection.png
