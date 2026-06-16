(rvc_control)=

# Control

![High Level Design](images/html/RVCControl.png)

The above diagram displays the communication paths between
the motion controller components.
This interaction is left to be implemented in a ROS 2 node. Our use cases utilize a state machine. The ROS 2 node
will initialize the ROS 2 framework, initialize the intended plugins and delegate the use case handling to the state machine:

1. The state machine will instantiate a reference to a plugin of interface "GraspInterface" and one
of interface "MotionController" according to the specified configuration as in [Example Configuration](rvc_control/parameters.md)

2. The Grasp Plugin will subscribe to the [RVC API messages](rvc_api.md) RotatedBBList and compute the
target pose for the robot.

3. According to the state of the state machine, this is used
to ask the instance of the [MotionController plugin](rvc_control/motion_controller_plugin.md) to go the target and/or achieve different
tasks.

## Control Framework Resources

- [Example Configuration](rvc_control/parameters.md)

- [Motion Controller Plugin](rvc_control/motion_controller_plugin.md)

- [Grasp Plugin](rvc_control/grasp_plugin.md)

<!--hide_directive
:::{toctree}
:maxdepth: 1
:hidden:

rvc_control/parameters
rvc_control/motion_controller_plugin
rvc_control/grasp_plugin

:::
hide_directive-->
