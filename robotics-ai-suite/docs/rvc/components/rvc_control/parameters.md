# Example Configuration

The main node plugin configuration can be provided by yaml file, as per
following examples:

## Plugins

```yaml
/**:
    ros__parameters:
        motion_controller: "RVCMotionController::Moveit2ServoMotionController"
        grasp_plugin: "RVCControl::NonOrientedGrasp"
```
