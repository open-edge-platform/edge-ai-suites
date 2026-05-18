(static_use_case)=

# Static Vision Use Case

This exemplary use case shows how the robot detecting an instance of an object pose, i.e.: position
and orientation in space with a 2.5D algorithm and the robot picks it up according to this position and orientation.

> **Note:** Every component has an option to change the default namespace:
> `namespace:=<namespace>` which by default is "ipc".
>
> If specified, the components will only see other components if they have same namespaces.
>
> Moreover, some components require additional configuration depending on this name, more specifically
> the existence of a config file `d415camera<namespace>.xacro` in `` `<installdir>/rvc_dynamic_motion_controller_use_case/cameraurdf/` `` directory.

The only configuration needed on the robot, is to put the teaching pendant in `remote control` as shown in following picture:

![Setting pendant to Remote control](../images/html/setremotecontrol.png)

```bash
ros2 launch rvc_static_motion_controller_use_case rviz2_launch.py
<TODO:>
ros2 launch rvc_static_motion_controller_use_case static_demo_launch.py robot_ip:=<robot_ip>
```
