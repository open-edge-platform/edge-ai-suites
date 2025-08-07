This package provides is a MoveIt! kinematics plugin that replaces the KDL IK
solver with the TRAC-IK solver.  Currently mimic joints are *not* supported.  

###As of v1.4.3, this package is part of the ROS Indigo/Jade binaries: `sudo apt-get install ros-jade-trac-ik-kinematics-plugin`

To use:

- Add this package and trac_ik_lib package to your catkin workspace.
- Find the MoveIt! [kinematics.yaml](http://docs.ros.org/indigo/api/pr2_moveit_tutorials/html/kinematics/src/doc/kinematics_configuration.html) file created for your robot.
- Replace
```kinematics_solver: kdl_kinematics_plugin/KDLKinematicsPlugin```
(or similar) with
```kinematics_solver: trac_ik_kinematics_plugin/TRAC_IKKinematicsPlugin```
- Set parameters as desired:
    - _kinematics\_solver\_timeout_ (timeout in seconds, e.g., 0.005) and _position\_only\_ik_ **ARE** supported.
    - _solve\_type_ can be Speed, Distance, Manipulation1, Manipulation2 (see trac\_ik\_lib documentation for details).  Default is Speed.
    - _kinematics\_solver\_attempts_ parameter is unneeded: unlike KDL, TRAC-IK solver already restarts when it gets stuck
    - _kinematics\_solver\_search\_resolution_ is not applicable here.
    - Note: The Cartesian error distance used to determine a valid solution is _1e-5_, as that is what is hard-coded into MoveIt's KDL plugin.


###NOTE: My understanding of how MoveIt! works from user experience and looking at the source code (though I am NOT a MoveIt! developer):

For normal operations, MoveIt! only really calls an IK solver for one pose
(maybe multiple times if the first result is invalid due to self collisions or
the like). This IK solution provides a joint configuration for the
goal. MoveIt!  already knows the _current_ joint configuration from encoder
info.  All planning at that point is done in _JOINT SPACE_. Collision
detection and constraint checking may use Forward Kinematics to determine the
pose of any subgoal joint configuration, but the planning _IS NOT_ being done
in Cartesian space. After a joint trajectory is found, MoveIt! tries to smooth
the trajectory to make it less "crazy looking", but this does not always
result in a path that is pleasing to human users.  

If you don't have obstacles in your space, you may want to try the Cartesian
planning API in MoveIt! to get "straight-line" motion.  MoveIt's Cartesian
planner _IS_ "planning" in Cartesian space (doing lots of IK calls). Though
really it is just performing linear interpolation in x,y,z,roll,pitch,yaw
between the current and desired poses -- it isn't really "searching" for a
solution. That is, MoveIt's Cartesian capability is not doing collision
avoidance or replanning -- if a collision is detected, the linear
interpolation "planning" immediately stops.  Unfortunately, in MoveIt! this
scenario still returns _True_ that a trajectory was found. This is not ideal,
and needs to be fixed -- I may write a new Cartesian capability plugin for
MoveIt! that addresses this, but that would be outside the scope of Inverse
Kinematics.
