
.. _motion_controller_plugin:

Motion Controller Plugin
==========================

The :cpp:class:`RVCMotionControllerInterface<RVCMotionController::RVCMotionControllerInterface>` 
defines the interfaces Motion controller plugins are based off.

The strategy the robot is complying when assigned a target Pose is defined in custom plugins following
the above interface.

The development interface is defined in :ref:`Motion Controller Interface Development<motioncontroller_plugins>`

Moveit2 Servo Motion Controller
-------------------------------


RVC is providing a `relatively` simple motion controller based off Moveit2 servo:

.. Moveit2 Servo: https://moveit.picknik.ai/humble/doc/examples/realtime_servo/realtime_servo_tutorial.html


The strategy is to compute an in space linear velocity trajectory (althought in time follows an atan profile) to 
the target and to feed it |moveit2| |servo| node.

Additional features exposed by servo are collision maps, customizable in the associated yaml file, and 
singularity detection.

Although the controller will `NOT` compute alternate trajectories around these maps/singularities,
it will slow down the robot to complete stop to avoid robot damage or other entities (cameras, conveyor
belts, supports, etc).

The configuration of this plugin is explained in :ref:`Moveit2 Servo pose tracking <moveit2_servo_pose_tracking>`.
The reason is that the plugin isn't running its own |ros2| node, but it runs in the main use case node, so the
configuration of the motion controller and the grasp plugin is provided to the main node.

Dobby Motion Controller
-------------------------------

RVC is providing a real-time motion planning framework for robot manipulators called Dobby.

Dobby is a real-time motion planning framework with a high success rate in complex environments:

- An efficient map representation that allows for a fast collision checking.

- A geometric path planner based on Rapidly-Exploring Random Trees with minimum distance as the cost function.

- An efficient trajectory generation method that allows selecting the optimization criteria, e.g., minimum acceleration, minimum jerk, etc.

- A novel cartesian trajectory generation algorithm that allows tracking time-dependent trajectories in cartesian space while avoiding self-collisions and avoiding obstacles mapped, providing dynamically feasible trajectories.


Direct Universal Robot Pendant Controller
-----------------------------------------

The Universal Robot drivers are present in |ROS2| and fully supported, but in case another robot
is employed, and the |ROS2| drivers are missing, we provided a strategy to implement a RVC Plugin
able to interface with the specific robot using their custom interfaces. And as reference, we 
chose Universal Robot pretending we didnt have a |ROS2| driver.

The limitation of this plugin, is that the robot, once sent to a target, cant change destination,

and before changing destination, the previous one has to be successfully reached.

This limitation can of course be worked around, using fine tuned Universal specific interfaces (servoj as 
opposed to movep), but we didnt want to particularize the solution too much towards a very specific model

Direct Universal Robot Pendant Controller configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Default parameter value are mostly fine, but one mandatory has to be changed according to the network
topology: ``server_ip``. This parameter specify the ip of the interface able to talk to the robot.

.. code-block:: yaml

    robot_program: "robot_program.txt"
    server_ip: "10.11.12.98"
    server_port: 50005
    robot_port: 30002
