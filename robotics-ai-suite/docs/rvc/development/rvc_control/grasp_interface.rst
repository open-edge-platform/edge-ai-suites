
.. _grasp_interface_plugin:

Grasp Interface Plugin
----------------------

The messages from the vision component are subscribed by the
rvc_grasp_interface automatically when api
:cpp:func:`RVCControl::RVCGraspInterface::init` gets called.
Subscription of the rvc_message is inside the parent of every plugin and
called esplicitely in the init function. Example:

::

   bool NonOrientedGrasp::init(rclcpp::Node::SharedPtr node)
   {
       auto res = RVCGraspInterface::init(node);
       [...]
   }

Up a new message reception the interface will call the API function
:cpp:func:`OnMessageReceive<RVCControl::RVCGraspInterface::OnMessageReceive>` to give
the plugin the chance to add implementation

The Pre-Grap and Grasp pose will be retrieved in the implementation of
:cpp:func:`getPreGrasp<RVCControl::RVCGraspInterface::getPreGrasp>` and
:cpp:func:`getGrasp<RVCControl::RVCGraspInterface::getGrasp>` APIs, where these
poses could be computed there or on OnMessageReceive.

APIs for the Grap plugin can be found at
:cpp:class:`RVCGraspInterface<RVCControl::RVCGraspInterface>`

Grasp plugin config
-------------------

The interface init function will subscribe to the rvc_message topic,
that by default is `object_poses` but can be override by:

::

   /**:
       ros__parameters:
       object_pose_topic: "object_poses"

object_pose_topic
