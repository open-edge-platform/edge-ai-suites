# Grasp Plugin

The [RVCGraspInterface](../../development/rvc_control/rvc_interface_apis/interface_apis.md#rvc-control-plugin-interface-apis) defines the interfaces grasp plugins
are based off.

The idea is that a plugin, which provide fast interface (calling functions instead of subscribing topics)
but still giving high modularity to the task, is to provide different grasping approaches to different
use cases.

For example, some objects might be all symmetrical and can be picked up by center of mass with
fixed orientation, others might need to allign to specific faces, others might need from the top
grabbing, as in the case of suction grippers.

The development interface is defined in [Grasp Interface Development](../../development/rvc_control/grasp_interface.md)
