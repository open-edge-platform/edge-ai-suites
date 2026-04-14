

Grasp Plugin
=============

The :cpp:class:`RVCGraspInterface<RVCControl::RVCGraspInterface>` defines the interfaces grasp plugins
are based off.

The idea is that a plugin, which provide fast interface (calling functions instead of subscribing topics)
but still giving high modularity to the task, is to provide different grasping approaches to different
use cases.


For example, some objects might be all symmetrical and can be picked up by center of mass with
fixed orientation, others might need to allign to specific faces, others might need from the top
grabbing, as in the case of suction grippers.

The development interface is defined in :ref:`Grasp Interface Development<grasp_interface_plugin>`
