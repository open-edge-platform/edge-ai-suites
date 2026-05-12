(grasp_interface_plugin)=

# Grasp Interface Plugin

The messages from the vision component are subscribed by the
`rvc_grasp_interface` automatically when API
`RVCControl::RVCGraspInterface::init` gets called.
Subscription of the rvc_message is inside the parent of every plugin and
called explicitly in the init function. Example:

```cpp
bool NonOrientedGrasp::init(rclcpp::Node::SharedPtr node)
{
    auto res = RVCGraspInterface::init(node);
    [...]
}
```

Upon a new message reception the interface will call the API function
`RVCControl::RVCGraspInterface::OnMessageReceive` to give
the plugin the chance to add implementation.

The Pre-Grasp and Grasp pose will be retrieved in the implementation of
`RVCControl::RVCGraspInterface::getPreGrasp` and
`RVCControl::RVCGraspInterface::getGrasp` APIs, where these
poses could be computed there or on `OnMessageReceive`.

APIs for the Grasp plugin can be found at
[RVCGraspInterface](rvc_interface_apis/interface_apis.md#rvc-control-plugin-interface-apis).

## Grasp plugin config

The interface init function will subscribe to the rvc_message topic,
that by default is `object_poses` but can be overridden by:

```yaml
/**:
    ros__parameters:
    object_pose_topic: "object_poses"
```

`object_pose_topic`
