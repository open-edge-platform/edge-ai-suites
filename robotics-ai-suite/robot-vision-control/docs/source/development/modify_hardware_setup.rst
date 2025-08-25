
.. _swapping_robots:

Modify Hardware Setup
=====================

RVC Framework has been designed with modularity and abstraction in mind. 
In theory, this means that every hardware component could be substituted. 
However, due to the diverse range of devices and control mechanisms, 
the specific modifications required for seamless operation may vary considerably.

Change Camera
-------------

This section explains the modifications required if you use different
cameras:

Use a camera of same model
~~~~~~~~~~~~~~~~~~~~~~~~~~

To use a camera of the same model, such as Intel\ |reg| RealSense\ |TM| D415, but a
different location, make the following change in the
*<usecaseinstallationpath>/urdf/d415camera<namespace>.xacro* file to reflect the real
position:

.. code-block:: xml

     <origin xyz="0.330 0.7210 0.755" rpy="-3.141592654 1.570796327 -1.570796327"/>

.. note::
    xyz are in meters and roll pitch and yaw angles are in radians.

.. note::

    To help the Vision component, measure the distance between the center of camera and the first 
    flat surface (in our case the conveyor belt surface) and modify the value of the ``z_threshold``
    (in meters) parameter in the *<visioncomponentsinstallpath>/rvc_pose_detector/config/parameters.yaml*. 
    If ``z_threshold`` is closer to the camera than the maximum distance an object could be, the 
    object will be cropped and never be detected.

Use Different Stereo Camera
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Note:** Only Intel\ |reg| RealSense\ |tm| cameras have been tested. To adapt
the |RVC| Framework to a different camera, note that the |ROS| node handling
the new camera must expose a pointcloud ordered (that is, the pointcloud
is not monodimensional array, but must be a 640x480 pointcloud and
ordered). This is necessary to extract the cropped pointcloud from the
bounding box coming from AI, which is done on a 2-D RGB channel.

To use a different stereo camera, edit the
*<usecaseinstallationpath>/launch/robot_demo_launch.py* file and replace the
following lines with the urdf and xacro from the gripper manufacturer:

.. code-block:: python

   camera_xacro_path = get_package_share_directory(<usecasepackagename>) + "/urdf/d415camera<namespace>.xacro"

This xacro generates a Universal Robot Descriptor File (URDF) that ROS2
uses to connect all elements together and perform necessary
transformations from one reference system to another.

In particular, the poses come in the camera reference system, and the
manipulator operates in world reference. So, the pose reference system
and the details of how and where the camera is physically connected in
the world is critical. The ROS2 node of the new camera will provide a
URDF file, which must be connected to the world reference link.

This linking is done in *d415camera1.xacro*, which can be used as a
reference. In the RVC demonstration, the base of the camera is at
``xyz="0.330 0.7210 0.755", rpy ="-PI,PI/2,-PI/2"`` to point to the
right camera xacro that the manufacturer provides.

Additionally, make modifications on the AI side, such as removing the
RealSense ros2 node and replacing with a |ROS| of the new camera.

The AI publishes the detected pose with:

.. code-block:: c++

    pose.header.frame_id = "camera_depth_optical_frame";

Modify this value according to the URDF of the new camera.

Use Different Non-stereo Camera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To use a different non-stereo camera or an entirely different object
detection technology, drop the RVC object recognition, keeping in mind
that the RVC Robot Motion Controller is tracking a topic configured in
*src/robot_demo_main/config/parameters.yaml* as
``object_pose_topic: "object_poses"`` of type
``rvc_messages::msg::PoseStamped`` as defined in
*src/shared_messages/rvc_messages/msg/PoseStamped.msg*.

Change Universal Robot Model
----------------------------

The default robot model is UR5e. If you are using a different robot
model from the same family, do either one of the following:

-  Modify ``ur_type_arg = LaunchConfiguration`` in the launch file

   ``<dynamicusecaseinstallationpath>/launch/dynamic_demo_launch.py.``
   
   The default value of ``ur_type`` is ``ur5e``.

-  Append ``ur_type`` in the launch command line:

   .. code-block:: bash

      ros2 launch rvc_dynamic_motion_controller_use_case dynamic_demo_launch.py robot_ip:=<ROBOT_IP> ur_type:=<URMODEL> &

Change Gripper and Manipulator
------------------------------

The current implementation handles a composite robot, which is a
manipulator connected to a gripper as it is a single robot with seven
joints: six joints from the UR5e and gripper actuator as seventh joint.

To do so, RVC needs a composite URDF file, which includes the original
UR5e URDF, the Robotiq URDF, and the joint connecting the UR5e end
effector link (``ee_link``) to the gripper base link.

Moreover, the Robotiq original ROS1 URDF used in the demonstration did
not include the ``ros2_control`` specification to expose the “joint” to
the ROS2 hardware driver abstraction. Hence, it was added.

You can find the complete URDF glue file at
*<dynamicusecaseinstallationpath>/urdf/composite_u5_robotiq_2f_gripper.xacro*. Use
this glue file as a reference to compose a new glue file when replacing
the robot and gripper.

Change the following:

-  The xacro ``ur.urdf.xacro`` include directive for the robot
-  The ``robotiq_arg2f_85_model_macro.xacro`` directive for the gripper.

If the ROS2 driver of the new gripper contains the ``ros2_control``, do
not add it here.

It is important to concatenate (link) the last link of the chain for the
manipulator and the first link of the gripper and connect them in the
new composition URDF. In this demonstration, for the ur5e model, the
last link is ``tool0`` and the first link of the gripper is
``robotiq_arg2f_base_link``. In the
``composite_u5_robotiq_2f_gripper.xacro``, a new link ``ee_link``
connecting the two was created.

**Note**: The center between the two fingers must be positioned on the
target pose to pick the object up. The Robotiq gripper URDF does not
specify any joint or link that can be used for computing the inverse
kinematics of this point. So, the ``ee_link`` is offset by the z
component at 0.174 meters from the parent, which is the end effector of
the UR5e. The value 0.174 is exactly the length of the gripper base and
the point where the fingertips are at when the gripper is closed.

The following figure shows the current global URDF representation as
seen by ROS2 RQt ``tf_tree`` tool.

.. figure:: ../images/html/tftree.svg
   :alt: TFTree

   Figure : TFTree

In the graph, blue indicates the URDF coming from Robotiq gripper, green
from Universal Robot, and red from RealSense ROS2 node.

This tool validates whether:

-  All links and joints are interconnected
-  The graph is not disconnected anywhere
-  The camera base connects to the world
-  The manipulator base connects to world
-  The gripper connects to the end effector of the manipulator.

If you physically connect the camera to any robot link instead of on a
fixed location, the graph will represent it as the camera tree being
connected to that link.


Change Manipulator without supported drivers
--------------------------------------------

RVC is based on |ros2| framework, hence its able to drive manupulators with |ros| support.
This means the manufacturer has to provide a |ros2| driver, fully implementing the |ros2_control|
interfaces and |moveit2| support.

If the robot is not supported, there is another way, albeit potentially not straight forward:

