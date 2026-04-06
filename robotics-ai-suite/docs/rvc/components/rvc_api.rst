
.. _rvc_api_messages:

API messages
================

The RVC API messages are a set of ROS2 messages designed to permit
communication between the vision components and the motion control components

Messages
---------

PoseStamped
~~~~~~~~~~~

-  *obj_id*: unique uint64 identifier for the associated class of the object. 
-  *string obj_type*: string associated to obj_id
-  *geometry_msgs/PoseStamped pose_stamped*: the actual pose
   (position/orientation) of the object, time stamped
-  *builtin_interfaces/Time last_observed*: the last time this object
   was directly observed. If this is before the current time, the object
   record may be extrapolated under the assumption that the camera’s
   visual field is partially occluded.
-  *geometry_msgs/PoseStamped last_observed_pose_stamped*: the
   world-space pose of the object when it was last observed


PoseStampedList
~~~~~~~~~~~~~~~

This is a container for and array of PoseStamped Messages

-  Array of rvc_messages::msg::PoseStamped
