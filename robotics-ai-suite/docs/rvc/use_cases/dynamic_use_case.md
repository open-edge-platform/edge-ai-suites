(dynamic_use_case)=

# Dynamic Vision Use Case

This exemplary use case shows how the robot actively tracks a group of objects
in real-time as they unpredictably navigate through three-dimensional space.
Subsequently, the robot picks up these objects and accurately places them at their
designated destination.

> **Note:** Every component has an option to change the default namespace:
> `namespace:=<namespace>` which by default is "ipc".
>
> If specified, the components will only see other components if they have same namespaces.
>
> Moreover, some components require additional configuration depending on this name, more specifically
> the existence of a config file `d415camera<namespace>.xacro` in `` `<installdir>/rvc_dynamic_motion_controller_use_case/cameraurdf/` `` directory.

> **Note:** After following at least once the [Preliminary system configuration](dynamic_use_case/system_config.md#preliminary-system-configuration) guide, i.e.: calibrating camera and robot,
> the quick start guide to start RVC is to execute in three different terminals:
>
> ```bash
> ros2 launch rvc_dynamic_motion_controller_use_case rviz2_launch.py
> ros2 launch rvc_vision_main vision.composition.launch.py
> ros2 launch rvc_dynamic_motion_controller_use_case dynamic_demo_launch.py robot_ip:=<robot_ip>
> ```
>
> Then press play on the Universal Robots UR5e teach pendant.
>
> > **Note:** The Dobby planner plugin is Intel IP available under NDA only. For customers interested in accessing this motion planning framework, please contact [eci.maintainer@intel.com](mailto:eci.maintainer@intel.com).

<!--hide_directive
:::{toctree}
:maxdepth: 1

dynamic_use_case/system_config
dynamic_use_case/visualization
dynamic_use_case/state_machine_node
dynamic_use_case/vision_main_node

:::
hide_directive-->
