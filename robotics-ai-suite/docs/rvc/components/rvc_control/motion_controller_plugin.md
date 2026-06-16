(motion_controller_plugin)=

# Motion Controller Plugin

The [RVCMotionControllerInterface](../../development/rvc_control/rvc_interface_apis/interface_apis.md#rvc-control-plugin-interface-apis) defines the interfaces Motion controller plugins are based off.

The strategy the robot is complying when assigned a target Pose is defined in custom plugins following
the above interface.

The development interface is defined in [Motion Controller Interface Development](../../development/rvc_control/motion_controller_interface.md)

## Moveit2 Servo Motion Controller

RVC is providing a relatively simple motion controller based on the Moveit2 servo:

The strategy is to compute an in space linear velocity trajectory (althought in time follows an atan profile) to
the target and to feed it [MoveIt 2](https://moveit.picknik.ai/main/index.html) [Servo](https://moveit.picknik.ai/humble/doc/examples/realtime_servo/realtime_servo_tutorial.html) node.

Additional features exposed by servo are collision maps, customizable in the associated yaml file, and
singularity detection.

Although the controller will **NOT** compute alternate trajectories around these maps/singularities,
it will slow down the robot to complete stop to avoid robot damage or other entities (cameras, conveyor
belts, supports, etc).

The configuration of this plugin is explained in [Moveit2 Servo pose tracking](../../use_cases/dynamic_use_case/state_machine_node.md#motion-controller-exemplary-plugin).
The reason is that the plugin isn't running its own ROS 2 node, but it runs in the main use case node, so the
configuration of the motion controller and the grasp plugin is provided to the main node.

## Direct Universal Robot Pendant Controller

The Universal Robot drivers are present in ROS2 and fully supported, but in case another robot
is employed, and the ROS2 drivers are missing, we provided a strategy to implement a RVC Plugin
able to interface with the specific robot using their custom interfaces. And as reference, we
chose Universal Robot pretending we didn't have a ROS2 driver.

The limitation of this plugin, is that the robot, once sent to a target, cant change destination,
and before changing destination, the previous one has to be successfully reached.

This limitation can of course be worked around, using fine tuned Universal specific interfaces (servoj as
opposed to movep), but we didn't want to particularize the solution too much towards a very specific model

### Direct Universal Robot Pendant Controller configuration

Default parameter value are mostly fine, but one mandatory has to be changed according to the network
topology: `server_ip`. This parameter specify the ip of the interface able to talk to the robot.

```yaml
robot_program: "robot_program.txt"
server_ip: "10.11.12.98"
server_port: 50005
robot_port: 30002
```
