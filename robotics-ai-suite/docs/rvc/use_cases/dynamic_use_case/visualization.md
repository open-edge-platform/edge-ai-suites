(rvc_visualization)=

# RVC Visualization

## Rviz2 Plugin

A rviz2 plugin has been implemented to give full control of the use case in the same HMI:

![RViz2 Control Panel Custom plugin](../../images/html/RvizDynamicUseCase1.png)

- **Enable/Disable motion button** — Start and stop motion.
- **Speed knob** — Change the speed of the robot.
- **TrackOnly/FullCycle** — Enable object tracking only, or full pick and place cycle.
- **Track on close** — Dynamic tracking is by default disabled while the gripper is closing. This behaviour
  can be overridden with this toggle, which will enable object movement
  tracking even while the gripper is closing. The reason of the existence of
  this toggle is that, depending on the AI in use, the object
  detection accuracy might lower while the gripper is closing.
- **Camera Live stream** — Default behaviour is to show the inference topic, which should
  show bounding box, class Id annotation on top of RGB stream. If this
  is missing, then show raw camera output.

## Rviz Execution

The dynamic use case rviz component can be executed by running:

```bash
ros2 launch rvc_dynamic_motion_controller_use_case rviz2_launch.py
```
