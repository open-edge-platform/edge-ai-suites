# The unique string type of this object. No two distinct objects will ever have the same
# ID.
string obj_type

# The (possibly extrapolated) world-space pose of the object
geometry_msgs/PoseStamped pose_stamped

# The last time this object was directly observed. If this is before the current
# time, the object record may be extrapolated under the assumption that the
# camera's visual field is partially occluded.
builtin_interfaces/Time last_observed

# The world-space pose of the object when it was last observed
geometry_msgs/PoseStamped last_observed_pose_stamped
