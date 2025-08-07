
.. _motioncontroller_plugins:

MotionController Plugins
------------------------

MotionController interface based plugins are needed to implement a robot
specific way to move the robot itself as long as the end effector or
gripper

Motion Controller interface API
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


- :cpp:func:`init <RVCMotionController::RVCMotionControllerInterface::init()>`


Called upon initialization of the plugin, with a valid rclcpp::node
reference. 
The super has to be called with the same node, for example:

::

    bool URPendantMotionController::init(rclcpp::Node::SharedPtr node)
    {
        node_ = node;
        auto res = RVCMotionControllerInterface::init(node_);


- :cpp:func:`setControllerSpeed <RVCMotionController::RVCMotionControllerInterface::setControllerSpeed()>`


Change the controller speed, can be manipulator, gripper or both.

- :cpp:func:`sendGoal <RVCMotionController::RVCMotionControllerInterface::sendGoal>` in cartesian space


Set the target destination of the end effector, the controller decided
trajectory, timings (taking controllerSpeed in considaration) and,
ideally, collision maps. The argument is a `const geometry_msgs::msg::Pose`



- :cpp:func:`sendGoal <RVCMotionController::RVCMotionControllerInterface::sendGoal()>` in joint space

Deprecated API to send target directly in joint space

- :cpp:func:`sendGripperPosition <RVCMotionController::RVCMotionControllerInterface::sendGripperPosition()>`


set the new end effector position, can be finger closing degree, or
suction activation for suction gripper

- :cpp:func:`isGoalNear <RVCMotionController::RVCMotionControllerInterface::isGoalNear()>`

Controller gives an indication if the target is close enough to the
target


APIs for the Motion Controller plugin can be found at 

:cpp:class:`RVCMotionControllerInterface <RVCMotionController::RVCMotionControllerInterface>`


URPendant exemplary plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. _ros2_control: https://control.ros.org/humble/index.html

A motion controller plugin showing how an unsupported robot (i.e.: without ros2_control_ drivers)




.. toctree::
   :maxdepth: 3

   rvc_interface_apis/interface_apis
